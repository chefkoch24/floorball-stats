import argparse
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from src.run_stats_engine import run_stats_pipeline


EVENT_FILE_PREFIX = "data_"
EVENT_FILE_SUFFIXES = ("_regular_season.csv", "_playoffs.csv")


def _infer_sqlite_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "INTEGER"
    if pd.api.types.is_integer_dtype(series):
        return "INTEGER"
    if pd.api.types.is_float_dtype(series):
        return "REAL"
    return "TEXT"


def _ensure_table_schema(conn: sqlite3.Connection, table_name: str, frame: pd.DataFrame) -> None:
    existing = {
        row[1]: row[2]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if not existing:
        columns_sql = []
        for column in frame.columns:
            sqlite_type = _infer_sqlite_type(frame[column])
            columns_sql.append(f'"{column}" {sqlite_type}')
        conn.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(columns_sql)})')
        return

    for column in frame.columns:
        if column in existing:
            continue
        sqlite_type = _infer_sqlite_type(frame[column])
        conn.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{column}" {sqlite_type}')


def _replace_table_slice(
    conn: sqlite3.Connection,
    table_name: str,
    frame: pd.DataFrame,
    where_clause: str,
    where_params: tuple[Any, ...],
) -> int:
    if frame.empty:
        _ensure_table_schema(conn, table_name, frame)
        conn.execute(f'DELETE FROM "{table_name}" WHERE {where_clause}', where_params)
        return 0

    _ensure_table_schema(conn, table_name, frame)
    conn.execute(f'DELETE FROM "{table_name}" WHERE {where_clause}', where_params)
    frame.to_sql(table_name, conn, if_exists="append", index=False)
    return len(frame)


def _json_payload_frame(
    rows: list[dict[str, Any]],
    *,
    source_key: str,
    season: str,
    phase: str,
    record_type: str | None = None,
    title: str | None = None,
) -> pd.DataFrame:
    if not rows:
        columns = ["source_key", "season", "phase", "payload_json"]
        if record_type is not None:
            columns.append("record_type")
        if title is not None:
            columns.append("title")
        return pd.DataFrame(columns=columns)

    frame = pd.json_normalize(rows, sep="__")
    frame.insert(0, "source_key", source_key)
    frame.insert(1, "season", season)
    frame.insert(2, "phase", phase)
    if record_type is not None:
        frame.insert(3, "record_type", record_type)
    if title is not None:
        insert_at = 4 if record_type is not None else 3
        frame.insert(insert_at, "title", title)
    frame["payload_json"] = [json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows]
    return frame


def sync_pipeline_outputs(
    *,
    db_path: str,
    input_csv_path: str,
    season: str,
    phase: str,
    stats_payload: dict[str, Any],
) -> dict[str, int]:
    source_key = Path(input_csv_path).stem
    events_frame = pd.read_csv(input_csv_path)
    events_frame.insert(0, "source_key", source_key)
    events_frame.insert(1, "season", season)
    events_frame.insert(2, "phase", phase)

    game_rows = stats_payload.get("game_stats", [])
    team_rows = []
    for team_name, payload in (stats_payload.get("team_stats_enhanced", {}) or {}).items():
        row = {"team": team_name}
        row.update(payload)
        team_rows.append(row)

    league_rows = []
    for record_type, title in [
        ("league_averages", "League Average"),
        ("playoff_averages", "Playoffs"),
        ("playdown_averages", "Playdown"),
        ("top4_averages", "Top 4 Teams"),
    ]:
        payload = stats_payload.get(record_type)
        if not payload:
            continue
        league_rows.append(
            {
                "record_type": record_type,
                "title": title,
                **payload,
            }
        )

    playoff_team_rows = stats_payload.get("playoff_stats", []) or []
    playdown_team_rows = stats_payload.get("playdown_stats", []) or []
    top4_team_rows = stats_payload.get("top4_stats", []) or []

    db_target = Path(db_path)
    db_target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_target) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        event_rows = _replace_table_slice(
            conn,
            "events",
            events_frame,
            "source_key = ?",
            (source_key,),
        )
        game_rows_written = _replace_table_slice(
            conn,
            "game_stats",
            _json_payload_frame(game_rows, source_key=source_key, season=season, phase=phase),
            "source_key = ?",
            (source_key,),
        )
        team_rows_written = _replace_table_slice(
            conn,
            "team_stats",
            _json_payload_frame(team_rows, source_key=source_key, season=season, phase=phase),
            "source_key = ?",
            (source_key,),
        )
        playoff_team_rows_written = _replace_table_slice(
            conn,
            "playoff_team_stats",
            _json_payload_frame(playoff_team_rows, source_key=source_key, season=season, phase=phase),
            "source_key = ?",
            (source_key,),
        )
        playdown_team_rows_written = _replace_table_slice(
            conn,
            "playdown_team_stats",
            _json_payload_frame(playdown_team_rows, source_key=source_key, season=season, phase=phase),
            "source_key = ?",
            (source_key,),
        )
        top4_team_rows_written = _replace_table_slice(
            conn,
            "top4_team_stats",
            _json_payload_frame(top4_team_rows, source_key=source_key, season=season, phase=phase),
            "source_key = ?",
            (source_key,),
        )
        league_rows_written = _replace_table_slice(
            conn,
            "league_stats",
            _json_payload_frame(league_rows, source_key=source_key, season=season, phase=phase),
            "source_key = ?",
            (source_key,),
        )
        conn.commit()

    return {
        "events": event_rows,
        "game_stats": game_rows_written,
        "team_stats": team_rows_written,
        "playoff_team_stats": playoff_team_rows_written,
        "playdown_team_stats": playdown_team_rows_written,
        "top4_team_stats": top4_team_rows_written,
        "league_stats": league_rows_written,
    }


def rebuild_from_event_csvs(*, db_path: str, data_dir: str) -> dict[str, int]:
    directory = Path(data_dir)
    totals = {
        "events": 0,
        "game_stats": 0,
        "team_stats": 0,
        "playoff_team_stats": 0,
        "playdown_team_stats": 0,
        "top4_team_stats": 0,
        "league_stats": 0,
    }
    for candidate in sorted(directory.glob(f"{EVENT_FILE_PREFIX}*.csv")):
        if candidate.name == "player_stats.csv" or candidate.name.startswith("player_stats_"):
            continue
        if not candidate.name.startswith(EVENT_FILE_PREFIX) or not candidate.name.endswith(EVENT_FILE_SUFFIXES):
            continue
        stem = candidate.stem[len(EVENT_FILE_PREFIX):]
        if stem.endswith("_regular_season"):
            season = stem[: -len("_regular_season")]
            phase = "regular-season"
        elif stem.endswith("_playoffs"):
            season = stem[: -len("_playoffs")]
            phase = "playoffs"
        else:
            continue
        with tempfile.TemporaryDirectory(prefix="floorball-stats-sqlite-") as temp_dir:
            stats_payload = run_stats_pipeline(
                input_csv_path=str(candidate),
                output_dir=temp_dir,
                season=season,
                phase=phase,
            )
        counts = sync_pipeline_outputs(
            db_path=db_path,
            input_csv_path=str(candidate),
            season=season,
            phase=phase,
            stats_payload=stats_payload,
        )
        for key, value in counts.items():
            totals[key] += value
    return totals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Maintain derived SQLite tables for floorball stats.")
    parser.add_argument("--db-path", default="data/stats.db")
    parser.add_argument("--data-dir", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rebuilt_counts = {
        "events": 0,
        "game_stats": 0,
        "team_stats": 0,
        "playoff_team_stats": 0,
        "playdown_team_stats": 0,
        "top4_team_stats": 0,
        "league_stats": 0,
    }
    if args.data_dir:
        rebuilt_counts = rebuild_from_event_csvs(db_path=args.db_path, data_dir=args.data_dir)
    summary = " ".join(f"{key}={value}" for key, value in rebuilt_counts.items())
    print(f"sqlite-sync: {summary} db={args.db_path}")


if __name__ == "__main__":
    main()
