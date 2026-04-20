"""Populate WFC CSV files with goal/penalty events from the DB events table.

The WFC game pages were originally generated without auth so only 'result' events
were scraped. This script reads goal/penalty events from the DB and merges them
into the existing CSV files so that re-running the pipeline generates complete
game pages with scorer/assist information.
"""
import argparse
import csv
from pathlib import Path

import psycopg


CSV_COLUMNS = [
    "event_type", "event_team", "period", "sortkey", "game_id",
    "home_team_name", "away_team_name", "home_goals", "guest_goals",
    "goal_type", "penalty_type", "game_date", "game_start_time", "attendance",
    "game_status", "ingame_status", "result_string", "scorer_name", "assist_name",
    "scorer_number", "assist_number", "penalty_player_name", "venue", "venue_address",
    "competition_name", "league_name", "tournament_stage_type", "tournament_stage_label",
    "tournament_group", "tournament_round", "tournament_round_order",
]

DB_TO_CSV = {col: col for col in CSV_COLUMNS}


def _load_db_events(database_url: str, season: str, phase: str) -> list[dict]:
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT event_type, event_team, period, sortkey, game_id,
                   home_team_name, away_team_name, home_goals, guest_goals,
                   goal_type, penalty_type, game_date, game_start_time, attendance,
                   game_status, ingame_status, result_string, scorer_name, assist_name,
                   scorer_number, assist_number, penalty_player_name, venue, venue_address,
                   competition_name, league_name, tournament_stage_type, tournament_stage_label,
                   tournament_group, tournament_round, tournament_round_order
            FROM events
            WHERE season = %s AND phase = %s AND event_type IN ('goal', 'penalty')
            """,
            (season, phase),
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _read_csv_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export_wfc_events_to_csv(
    database_url: str,
    regular_csv: str = "data/data_wfc-2024_regular_season.csv",
    playoffs_csv: str = "data/data_wfc-2024_playoffs.csv",
) -> None:
    for csv_path_str, season, phase in [
        (regular_csv, "wfc-2024", "regular-season"),
        (playoffs_csv, "wfc-2024", "playoffs"),
    ]:
        csv_path = Path(csv_path_str)
        if not csv_path.exists():
            print(f"  SKIP {csv_path} — file not found")
            continue

        existing = _read_csv_rows(csv_path)
        existing_game_event_keys = {
            (r["game_id"], r["event_type"], r.get("sortkey", ""))
            for r in existing
            if r["event_type"] in ("goal", "penalty")
        }

        db_rows = _load_db_events(database_url, season, phase)
        new_rows = [
            r for r in db_rows
            if (str(r["game_id"]), r["event_type"], r.get("sortkey") or "") not in existing_game_event_keys
        ]

        for r in new_rows:
            for k, v in r.items():
                if v is None:
                    r[k] = ""

        merged = existing + new_rows
        _write_csv(csv_path, merged)
        print(f"  {csv_path}: added {len(new_rows)} goal/penalty events ({len(merged)} total rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export WFC goal/penalty events from DB into CSV files.")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--regular-csv", default="data/data_wfc-2024_regular_season.csv")
    parser.add_argument("--playoffs-csv", default="data/data_wfc-2024_playoffs.csv")
    args = parser.parse_args()
    export_wfc_events_to_csv(
        database_url=args.database_url,
        regular_csv=args.regular_csv,
        playoffs_csv=args.playoffs_csv,
    )


if __name__ == "__main__":
    main()
