import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple

import psycopg

from src.utils import dict_to_markdown_game_stats, dict_to_markdown_league_stats, dict_to_markdown_team_stats, normalize_slug_fragment


def _write_if_changed(path: Path, content: str) -> bool:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return False
    path.write_text(content, encoding="utf-8")
    return True


def _extract_slug(content: str) -> Optional[str]:
    for line in content.splitlines():
        if line.startswith("Slug:"):
            value = line.split(":", 1)[1].strip()
            return value or None
    return None


def _remove_slug_aliases(directory: Path, canonical_path: Path, slug: Optional[str]) -> int:
    if not slug:
        return 0
    removed = 0
    for candidate in directory.glob("*.md"):
        if candidate == canonical_path:
            continue
        try:
            candidate_content = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        if _extract_slug(candidate_content) != slug:
            continue
        candidate.unlink()
        removed += 1
    return removed


def _remove_game_id_aliases(directory: Path, canonical_path: Path, game_id: object) -> int:
    game_id_text = str(game_id or "").strip()
    if not game_id_text:
        return 0
    prefix = normalize_slug_fragment(game_id_text)
    if not prefix:
        return 0
    removed = 0
    for candidate in directory.glob(f"{prefix}*.md"):
        if candidate == canonical_path:
            continue
        candidate.unlink()
        removed += 1
    return removed


def _prune_stale_markdown(directory: Path, expected_filenames: set[str]) -> int:
    removed = 0
    for candidate in directory.glob("*.md"):
        if candidate.name in expected_filenames:
            continue
        candidate.unlink()
        removed += 1
    return removed


def _resolve_metadata_date(game_stats: list[dict]) -> str:
    valid_dates = []
    for game in game_stats:
        value = game.get("date")
        if not value:
            continue
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            continue
        valid_dates.append(value)
    if valid_dates:
        return max(valid_dates)
    return datetime.now().strftime("%Y-%m-%d")


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_db_path(
    sqlite_path: str | None,
    game_stats_path: str,
    team_stats_path: str,
    league_stats_path: str,
) -> Path:
    if sqlite_path:
        return Path(sqlite_path)
    parents = [
        Path(game_stats_path).parent,
        Path(team_stats_path).parent,
        Path(league_stats_path).parent,
    ]
    for parent in parents:
        candidate = parent / "stats.db"
        if candidate.exists():
            return candidate
    return parents[0] / "stats.db"


def _parse_payload_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    parsed = []
    for row in rows:
        payload_json = row["payload_json"]
        if not payload_json:
            continue
        parsed.append(json.loads(payload_json))
    return parsed


def _parse_postgres_payload_rows(rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    parsed = []
    for row in rows:
        payload_json = row[0] if row else None
        if not payload_json:
            continue
        parsed.append(json.loads(payload_json))
    return parsed


def _load_game_stats_from_sqlite(db_path: Path, source_key: str) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT payload_json
            FROM game_stats
            WHERE source_key = ?
            ORDER BY COALESCE(date, ''), COALESCE(start_time, ''), COALESCE(game_id, 0)
            """,
            (source_key,),
        ).fetchall()
    return _parse_payload_rows(rows)


def _load_game_stats_from_postgres(database_url: str, source_key: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload_json
                FROM game_stats
                WHERE source_key = %s
                """,
                (source_key,),
            )
            rows = cur.fetchall()
    payloads = _parse_postgres_payload_rows(rows)
    payloads.sort(
        key=lambda item: (
            str(item.get("date", "") or ""),
            str(item.get("start_time", "") or ""),
            str(item.get("game_id", "") or ""),
        )
    )
    return payloads


def _load_team_stats_from_sqlite(db_path: Path, source_key: str, phase: str) -> dict[str, dict[str, Any]] | None:
    table_name = "playoff_team_stats" if phase == "playoffs" else "team_stats"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f'SELECT payload_json FROM "{table_name}" WHERE source_key = ?',
            (source_key,),
        ).fetchall()
    payloads = _parse_payload_rows(rows)
    if not payloads:
        return None

    if table_name == "playoff_team_stats":
        return {
            str(entry.get("team", "")): dict(entry.get("stats", {}))
            for entry in payloads
            if isinstance(entry, dict) and entry.get("team")
        }

    result: dict[str, dict[str, Any]] = {}
    for entry in payloads:
        if not isinstance(entry, dict):
            continue
        team_name = str(entry.get("team", "")).strip()
        if not team_name:
            continue
        stats = dict(entry)
        stats.pop("team", None)
        result[team_name] = stats
    return result


def _load_team_stats_from_postgres(database_url: str, source_key: str, phase: str) -> dict[str, dict[str, Any]] | None:
    table_name = "playoff_team_stats" if phase == "playoffs" else "team_stats"
    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT payload_json FROM {table_name} WHERE source_key = %s", (source_key,))
            rows = cur.fetchall()
    payloads = _parse_postgres_payload_rows(rows)
    if not payloads:
        return None

    if table_name == "playoff_team_stats":
        return {
            str(entry.get("team", "")): dict(entry.get("stats", {}))
            for entry in payloads
            if isinstance(entry, dict) and entry.get("team")
        }

    result: dict[str, dict[str, Any]] = {}
    for entry in payloads:
        if not isinstance(entry, dict):
            continue
        team_name = str(entry.get("team", "")).strip()
        if not team_name:
            continue
        stats = dict(entry)
        stats.pop("team", None)
        result[team_name] = stats
    return result


def _load_league_stat_by_record_type(db_path: Path, source_key: str, record_type: str) -> dict[str, Any] | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT payload_json
            FROM league_stats
            WHERE source_key = ? AND record_type = ?
            LIMIT 1
            """,
            (source_key, record_type),
        ).fetchone()
    if not row or not row["payload_json"]:
        return None
    return json.loads(row["payload_json"])


def _load_league_stat_by_record_type_from_postgres(database_url: str, source_key: str, record_type: str) -> dict[str, Any] | None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload_json
                FROM league_stats
                WHERE source_key = %s AND record_type = %s
                LIMIT 1
                """,
                (source_key, record_type),
            )
            row = cur.fetchone()
    if not row or not row[0]:
        return None
    return json.loads(row[0])


def _load_markdown_inputs(
    *,
    game_stats_path: str,
    team_stats_path: str,
    league_stats_path: str,
    season: str,
    phase: str,
    sqlite_path: str | None,
    database_url: str | None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any], Path | None, str]:
    source_key = Path(game_stats_path).stem.replace("game_stats", f"data_{season}_{phase.replace('-', '_')}")
    if database_url:
        game_stats = _load_game_stats_from_postgres(database_url, source_key)
        team_stats = _load_team_stats_from_postgres(database_url, source_key, phase)
        league_stats = _load_league_stat_by_record_type_from_postgres(database_url, source_key, "league_averages")
        if game_stats and team_stats and league_stats:
            return game_stats, team_stats, league_stats, None, source_key
        raise RuntimeError(
            f"Missing required markdown payload in Postgres for source_key={source_key}. "
            "Run pipeline sync to Neon before markdown generation."
        )

    db_path = _resolve_db_path(sqlite_path, game_stats_path, team_stats_path, league_stats_path)
    if db_path.exists():
        game_stats = _load_game_stats_from_sqlite(db_path, source_key)
        team_stats = _load_team_stats_from_sqlite(db_path, source_key, phase)
        league_stats = _load_league_stat_by_record_type(db_path, source_key, "league_averages")
        if game_stats and team_stats and league_stats:
            return game_stats, team_stats, league_stats, db_path, source_key

    game_stats = _load_json(game_stats_path)
    team_stats_raw = _load_json(team_stats_path)
    if isinstance(team_stats_raw, list):
        team_stats = {
            str(entry.get("team", "")): dict(entry.get("stats", {}))
            for entry in team_stats_raw
            if isinstance(entry, dict) and entry.get("team")
        }
    else:
        team_stats = team_stats_raw
    league_stats = _load_json(league_stats_path)
    return game_stats, team_stats, league_stats, db_path if db_path.exists() else None, source_key


def generate_markdown_files(
    game_stats_path: str,
    team_stats_path: str,
    league_stats_path: str,
    output_games_dir: str,
    output_teams_dir: str,
    output_liga_dir: str,
    season: str,
    phase: str,
    playoff_averages_path: Optional[str] = None,
    playdown_averages_path: Optional[str] = None,
    top4_averages_path: Optional[str] = None,
    sqlite_path: Optional[str] = None,
    database_url: Optional[str] = None,
) -> Tuple[int, int, int]:
    games_out = Path(output_games_dir)
    teams_out = Path(output_teams_dir)
    liga_out = Path(output_liga_dir)
    games_out.mkdir(parents=True, exist_ok=True)
    teams_out.mkdir(parents=True, exist_ok=True)
    liga_out.mkdir(parents=True, exist_ok=True)

    game_stats, team_stats, league_stats, db_path, source_key = _load_markdown_inputs(
        game_stats_path=game_stats_path,
        team_stats_path=team_stats_path,
        league_stats_path=league_stats_path,
        season=season,
        phase=phase,
        sqlite_path=sqlite_path,
        database_url=database_url,
    )
    metadata_date = _resolve_metadata_date(game_stats)

    games_written = 0
    expected_game_files: set[str] = set()
    for gs in game_stats:
        title = normalize_slug_fragment(f"{gs['game_id']} {gs['home_team']} vs {gs['away_team']}")
        md = dict_to_markdown_game_stats(gs, title, season, phase, metadata_date=metadata_date)
        target_path = games_out / f"{title}.md"
        expected_game_files.add(target_path.name)
        _remove_game_id_aliases(games_out, target_path, gs.get("game_id"))
        _remove_slug_aliases(games_out, target_path, _extract_slug(md))
        if _write_if_changed(target_path, md):
            games_written += 1
    _prune_stale_markdown(games_out, expected_game_files)

    teams_written = 0
    expected_team_files: set[str] = set()
    for team, stats in team_stats.items():
        title = normalize_slug_fragment(f"{team}-{season}-{phase}")
        md = dict_to_markdown_team_stats(stats, team, season, phase, metadata_date=metadata_date)
        target_path = teams_out / f"{title}.md"
        expected_team_files.add(target_path.name)
        _remove_slug_aliases(teams_out, target_path, _extract_slug(md))
        if _write_if_changed(target_path, md):
            teams_written += 1
    _prune_stale_markdown(teams_out, expected_team_files)

    league_written = 0
    expected_liga_files: set[str] = set()
    league_title = "League Average"
    league_md = dict_to_markdown_league_stats(league_stats, league_title, season, phase, metadata_date=metadata_date)
    league_slug = normalize_slug_fragment(f"{league_title}-{season}-{phase}")
    league_target_path = liga_out / f"{league_slug}.md"
    expected_liga_files.add(league_target_path.name)
    _remove_slug_aliases(liga_out, league_target_path, _extract_slug(league_md))
    if _write_if_changed(league_target_path, league_md):
        league_written += 1

    def _load_extra(record_type: str, json_path: str | None) -> dict[str, Any] | None:
        if database_url:
            payload = _load_league_stat_by_record_type_from_postgres(database_url, source_key, record_type)
            if payload:
                return payload
        if db_path is not None:
            payload = _load_league_stat_by_record_type(db_path, source_key, record_type)
            if payload:
                return payload
        if not json_path:
            return None
        extra_path = Path(json_path)
        if not extra_path.exists():
            return None
        return _load_json(str(extra_path))

    def _write_extra(record_type: str, json_path: str | None, title: str) -> None:
        nonlocal league_written
        extra_stats = _load_extra(record_type, json_path)
        if not extra_stats:
            return
        extra_md = dict_to_markdown_league_stats(extra_stats, title, season, phase, metadata_date=metadata_date)
        extra_slug = normalize_slug_fragment(f"{title}-{season}-{phase}")
        target_path = liga_out / f"{extra_slug}.md"
        expected_liga_files.add(target_path.name)
        _remove_slug_aliases(liga_out, target_path, _extract_slug(extra_md))
        if _write_if_changed(target_path, extra_md):
            league_written += 1

    _write_extra("playoff_averages", playoff_averages_path, "Playoffs")
    _write_extra("top4_averages", top4_averages_path, "Top 4 Teams")
    _prune_stale_markdown(liga_out, expected_liga_files)

    return games_written, teams_written, league_written


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game_stats_path", default="data/game_stats.json")
    parser.add_argument("--team_stats_path", default="data/team_stats_enhanced.json")
    parser.add_argument("--league_stats_path", default="data/league_averages.json")
    parser.add_argument("--sqlite_path", default=None)
    parser.add_argument("--database_url", default=None)
    parser.add_argument("--output_games_dir", default="content/25-26-regular-season/games")
    parser.add_argument("--output_teams_dir", default="content/25-26-regular-season/teams")
    parser.add_argument("--output_liga_dir", default="content/25-26-regular-season/liga")
    parser.add_argument("--season", default="25-26")
    parser.add_argument("--phase", default="regular-season")
    return parser.parse_args()


def main():
    args = parse_args()
    generate_markdown_files(
        game_stats_path=args.game_stats_path,
        team_stats_path=args.team_stats_path,
        league_stats_path=args.league_stats_path,
        sqlite_path=args.sqlite_path,
        database_url=args.database_url,
        output_games_dir=args.output_games_dir,
        output_teams_dir=args.output_teams_dir,
        output_liga_dir=args.output_liga_dir,
        season=args.season,
        phase=args.phase,
    )


if __name__ == "__main__":
    main()
