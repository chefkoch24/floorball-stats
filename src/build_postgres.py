import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
from psycopg import sql
from unidecode import unidecode

from src.run_stats_engine import run_stats_pipeline


EVENT_FILE_PREFIX = "data_"
EVENT_FILE_SUFFIXES = ("_regular_season.csv", "_playoffs.csv")
POSTGRES_IDENTIFIER_MAX_LEN = 63
MANAGED_TABLES = [
    "events",
    "game_stats",
    "team_stats",
    "playoff_team_stats",
    "playdown_team_stats",
    "top4_team_stats",
    "league_stats",
    "player_stats",
]


def _infer_postgres_type(series: pd.Series) -> str:
    # Keep the derived store schema permissive across leagues/seasons where
    # the same logical field can arrive as numeric or string in different files.
    return "TEXT"


def _table_exists(conn: psycopg.Connection, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (table_name,))
        row = cur.fetchone()
        return bool(row and row[0])


def _existing_columns(conn: psycopg.Connection, table_name: str) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
            """,
            (table_name,),
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def _ensure_table_schema(conn: psycopg.Connection, table_name: str, frame: pd.DataFrame) -> None:
    existing = _existing_columns(conn, table_name) if _table_exists(conn, table_name) else {}
    if not existing:
        columns_sql = []
        for column in frame.columns:
            pg_type = _infer_postgres_type(frame[column])
            columns_sql.append(sql.SQL("{} {}").format(sql.Identifier(column), sql.SQL(pg_type)))
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
                    sql.Identifier(table_name), sql.SQL(", ").join(columns_sql)
                )
            )
        return

    with conn.cursor() as cur:
        for column in frame.columns:
            if column in existing:
                continue
            pg_type = _infer_postgres_type(frame[column])
            cur.execute(
                sql.SQL("ALTER TABLE {} ADD COLUMN {} {}").format(
                    sql.Identifier(table_name), sql.Identifier(column), sql.SQL(pg_type)
                )
            )


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.where(pd.notna(frame), None)


def _shorten_identifier(identifier: str, *, reserve_suffix: int = 0) -> str:
    allowed = POSTGRES_IDENTIFIER_MAX_LEN - reserve_suffix
    if len(identifier) <= allowed:
        return identifier
    digest = hashlib.sha1(identifier.encode("utf-8")).hexdigest()[:8]
    prefix_len = max(1, allowed - 9)
    return f"{identifier[:prefix_len]}_{digest}"


def _base_identifier(raw: str) -> str:
    normalized = unidecode(str(raw))
    normalized = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in normalized)
    normalized = "_".join(part for part in normalized.split("_") if part)
    if not normalized:
        normalized = "col"
    if normalized[0].isdigit():
        normalized = f"c_{normalized}"
    return normalized


def _make_unique_identifiers(columns: list[str]) -> list[str]:
    used: set[str] = set()
    result: list[str] = []
    for raw in columns:
        base = _shorten_identifier(_base_identifier(raw))
        candidate = base
        idx = 2
        while candidate in used:
            suffix = f"_{idx}"
            candidate = _shorten_identifier(base, reserve_suffix=len(suffix)) + suffix
            idx += 1
        used.add(candidate)
        result.append(candidate)
    return result


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = frame.copy()
    renamed.columns = _make_unique_identifiers([str(c) for c in renamed.columns])
    return renamed


def _drop_managed_tables(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            for table in MANAGED_TABLES:
                cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table)))
        conn.commit()


def _replace_table_slice(
    conn: psycopg.Connection,
    table_name: str,
    frame: pd.DataFrame,
    where_clause: sql.SQL,
    where_params: tuple[Any, ...],
) -> int:
    frame = _prepare_frame(frame)
    _ensure_table_schema(conn, table_name, frame)
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("DELETE FROM {} WHERE ").format(sql.Identifier(table_name)) + where_clause,
            where_params,
        )

        if frame.empty:
            return 0

        prepared = _normalize_frame(frame)
        columns = list(prepared.columns)
        insert_stmt = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table_name),
            sql.SQL(", ").join(sql.Identifier(c) for c in columns),
            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )
        rows = [tuple(row) for row in prepared.itertuples(index=False, name=None)]
        cur.executemany(insert_stmt, rows)
        return len(rows)


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
    database_url: str,
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

    with psycopg.connect(database_url, autocommit=False) as conn:
        event_rows = _replace_table_slice(
            conn,
            "events",
            events_frame,
            sql.SQL("source_key = {}").format(sql.Placeholder()),
            (source_key,),
        )
        game_rows_written = _replace_table_slice(
            conn,
            "game_stats",
            _json_payload_frame(game_rows, source_key=source_key, season=season, phase=phase),
            sql.SQL("source_key = {}").format(sql.Placeholder()),
            (source_key,),
        )
        team_rows_written = _replace_table_slice(
            conn,
            "team_stats",
            _json_payload_frame(team_rows, source_key=source_key, season=season, phase=phase),
            sql.SQL("source_key = {}").format(sql.Placeholder()),
            (source_key,),
        )
        playoff_team_rows_written = _replace_table_slice(
            conn,
            "playoff_team_stats",
            _json_payload_frame(playoff_team_rows, source_key=source_key, season=season, phase=phase),
            sql.SQL("source_key = {}").format(sql.Placeholder()),
            (source_key,),
        )
        playdown_team_rows_written = _replace_table_slice(
            conn,
            "playdown_team_stats",
            _json_payload_frame(playdown_team_rows, source_key=source_key, season=season, phase=phase),
            sql.SQL("source_key = {}").format(sql.Placeholder()),
            (source_key,),
        )
        top4_team_rows_written = _replace_table_slice(
            conn,
            "top4_team_stats",
            _json_payload_frame(top4_team_rows, source_key=source_key, season=season, phase=phase),
            sql.SQL("source_key = {}").format(sql.Placeholder()),
            (source_key,),
        )
        league_rows_written = _replace_table_slice(
            conn,
            "league_stats",
            _json_payload_frame(league_rows, source_key=source_key, season=season, phase=phase),
            sql.SQL("source_key = {}").format(sql.Placeholder()),
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


def rebuild_from_event_csvs(*, database_url: str, data_dir: str) -> dict[str, int]:
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
        stem = candidate.stem[len(EVENT_FILE_PREFIX) :]
        if stem.endswith("_regular_season"):
            season = stem[: -len("_regular_season")]
            phase = "regular-season"
        elif stem.endswith("_playoffs"):
            season = stem[: -len("_playoffs")]
            phase = "playoffs"
        else:
            continue
        with tempfile.TemporaryDirectory(prefix="floorball-stats-postgres-") as temp_dir:
            stats_payload = run_stats_pipeline(
                input_csv_path=str(candidate),
                output_dir=temp_dir,
                season=season,
                phase=phase,
            )
        counts = sync_pipeline_outputs(
            database_url=database_url,
            input_csv_path=str(candidate),
            season=season,
            phase=phase,
            stats_payload=stats_payload,
        )
        for key, value in counts.items():
            totals[key] += value
    return totals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Maintain derived PostgreSQL tables for floorball stats.")
    parser.add_argument("--database-url", default=os.environ.get("NEON_DATABASE_URL") or os.environ.get("DATABASE_URL") or "")
    parser.add_argument("--data-dir", default="")
    parser.add_argument("--reset-existing", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.database_url:
        raise SystemExit("Missing --database-url (or NEON_DATABASE_URL / DATABASE_URL env var).")
    if args.reset_existing:
        _drop_managed_tables(args.database_url)

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
        rebuilt_counts = rebuild_from_event_csvs(database_url=args.database_url, data_dir=args.data_dir)
    summary = " ".join(f"{key}={value}" for key, value in rebuilt_counts.items())
    print(f"postgres-sync: {summary}")


if __name__ == "__main__":
    main()
