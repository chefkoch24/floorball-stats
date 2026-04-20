"""One-shot script: fetch WFC game overview events (goals/penalties) and upsert into events table."""
import argparse
import time

import psycopg

from src.scrape_wfc import (
    WfcAuth,
    _build_player_lookup,
    _fetch_game_overview,
    _overview_event_to_row,
    _stage_metadata,
    _build_game_row,
    _parse_int,
    _normalize_team_name,
)


def _fetch_goal_penalty_rows(game_id: int, game: dict, auth: WfcAuth) -> list[dict]:
    try:
        overview = _fetch_game_overview(game_id, auth)
    except Exception as exc:
        print(f"  WARNING: failed to fetch overview for game {game_id}: {exc}")
        return []

    blurbs = overview.get("Blurbs") or []
    if not isinstance(blurbs, list):
        return []

    meta = _stage_metadata(game)
    player_lookup = _build_player_lookup(overview)
    rows = []
    for blurb in blurbs:
        row = _overview_event_to_row(blurb, game, meta, player_lookup)
        if row is not None:
            rows.append(row)
    return rows


def _game_metadata_from_db(database_url: str) -> list[tuple]:
    """Return (game_id_str, season, phase, home_team, away_team) for all WFC games."""
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT game_id, season, phase, home_team_name, away_team_name
            FROM events
            WHERE season LIKE 'wfc%%' AND event_type = 'result'
            ORDER BY game_id
            """
        )
        return cur.fetchall()


def ingest_wfc_events(database_url: str, token: str) -> int:
    auth = WfcAuth(access_token=token, refresh_token="")
    games_meta = _game_metadata_from_db(database_url)
    if not games_meta:
        print("No WFC result events found in DB. Run the WFC pipeline first.")
        return 0

    # Build a minimal game dict for each game_id by pulling from the public API
    # We don't need the full game list — we just need game_id + team names for context.
    all_event_rows: list[dict] = []
    for game_id_str, season, phase, home_team, away_team in games_meta:
        game_id = int(game_id_str)
        print(f"  fetching overview game {game_id} ({home_team} vs {away_team})…", end=" ", flush=True)
        # Minimal game dict with the fields _overview_event_to_row needs
        game = {
            "GameID": game_id,
            "HomeTeamDisplayName": home_team,
            "AwayTeamDisplayName": away_team,
            "HomeTeamScore": None,
            "AwayTeamScore": None,
            "GameTime": None,
            "Spectators": None,
            "ArenaName": None,
            "FederationOrCupName": "IFF WFC 2024",
            "LeagueDisplayName": f"IFF WFC 2024 · {phase}",
            "LeagueName": f"wfc-{phase}",
        }
        rows = _fetch_goal_penalty_rows(game_id, game, auth)
        # Tag each row with season/phase
        for row in rows:
            row["season"] = season
            row["phase"] = phase
        print(f"{len(rows)} events")
        all_event_rows.extend(rows)
        time.sleep(0.3)

    if not all_event_rows:
        print("No goal/penalty events found.")
        return 0

    # Map to events table columns; use source_key to identify this data slice
    EVENT_COLUMNS = [
        "source_key", "season", "phase", "event_type", "event_team", "period", "sortkey",
        "game_id", "home_team_name", "away_team_name", "home_goals", "guest_goals",
        "game_date", "game_start_time", "attendance", "game_status",
        "scorer_name", "assist_name", "scorer_number", "assist_number",
        "penalty_player_name", "goal_type", "penalty_type",
        "venue", "competition_name", "league_name",
        "tournament_stage_type", "tournament_stage_label",
    ]

    def _source_key(season: str, phase: str) -> str:
        return f"data_{season}_{phase.replace('-', '_')}"

    rows_to_insert = []
    for row in all_event_rows:
        sk = _source_key(row["season"], row["phase"])
        rows_to_insert.append(tuple(
            row.get(col) if col != "source_key" else sk
            for col in EVENT_COLUMNS
        ))

    with psycopg.connect(database_url, autocommit=False) as conn, conn.cursor() as cur:
        # Delete existing goal/penalty rows for WFC (keep result rows)
        cur.execute(
            "DELETE FROM events WHERE season LIKE 'wfc%%' AND event_type IN ('goal', 'penalty')"
        )
        deleted = cur.rowcount
        if deleted:
            print(f"Deleted {deleted} existing WFC goal/penalty events.")

        placeholders = ", ".join(["%s"] * len(EVENT_COLUMNS))
        col_names = ", ".join(EVENT_COLUMNS)
        cur.executemany(
            f"INSERT INTO events ({col_names}) VALUES ({placeholders})",
            rows_to_insert,
        )
        conn.commit()

    return len(rows_to_insert)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest WFC goal/penalty events from IFF API into events table.")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--token", required=True, help="IFF API Bearer token (access token only)")
    args = parser.parse_args()
    total = ingest_wfc_events(database_url=args.database_url, token=args.token)
    print(f"wfc-events: stored {total} goal/penalty event rows")


if __name__ == "__main__":
    main()
