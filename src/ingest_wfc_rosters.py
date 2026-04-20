"""One-shot script: fetch WFC game lineups from IFF API and store in game_rosters table."""
import argparse
import time

import psycopg
import requests


LINEUP_URL = "https://iff-api.azurewebsites.net/api/magazinegameviewapi/initgamelineups"


def _fetch_lineup(game_id: int, token: str) -> dict:
    for attempt in range(3):
        try:
            response = requests.get(
                LINEUP_URL,
                params={"GameID": game_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            response.raise_for_status()
            return response.json() if isinstance(response.json(), dict) else {}
        except Exception as exc:
            if attempt < 2:
                time.sleep(2 + attempt)
                continue
            raise
    return {}


def _extract_players(payload: dict, team_name: str, side: str) -> list[dict]:
    roster_key = f"{side}TeamGameTeamRoster"
    lineup_key = f"{side}TeamLineUp"
    roster = payload.get(roster_key) or {}
    lineup = payload.get(lineup_key) or {}

    seen: set[str] = set()
    players = []
    for player in [
        *(roster.get("Players") or []),
        *(roster.get("Substitutes") or []),
        *(lineup.get("GameLineUpPlayers") or []),
    ]:
        if not isinstance(player, dict):
            continue
        full_name = str(player.get("FullName") or "").strip()
        if not full_name or full_name in seen:
            continue
        seen.add(full_name)
        players.append(
            {
                "player_name": full_name,
                "source_player_id": str(player.get("PlayerID") or player.get("MemberID") or "").strip(),
                "source_person_id": str(player.get("PersonID") or "").strip(),
                "team_name": team_name,
            }
        )
    return players


def ingest_wfc_rosters(database_url: str, token: str) -> int:
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS game_rosters (
                game_id INTEGER NOT NULL,
                season TEXT NOT NULL,
                phase TEXT NOT NULL,
                home_team_name TEXT NOT NULL,
                away_team_name TEXT NOT NULL,
                team_name TEXT NOT NULL,
                player_name TEXT NOT NULL,
                source_player_id TEXT NOT NULL DEFAULT '',
                source_person_id TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (game_id, player_name, team_name)
            )
            """
        )
        cur.execute(
            "SELECT DISTINCT game_id, season, phase, home_team_name, away_team_name FROM events WHERE season LIKE 'wfc%%' ORDER BY game_id"
        )
        games = cur.fetchall()
    conn.close()

    rows: list[tuple] = []
    for game_id_str, season, phase, home_team, away_team in games:
        game_id = int(game_id_str)
        print(f"  fetching game {game_id} ({home_team} vs {away_team})…", end=" ", flush=True)
        try:
            payload = _fetch_lineup(game_id, token)
            home_players = _extract_players(payload, home_team, "Home")
            away_players = _extract_players(payload, away_team, "Away")
            total = len(home_players) + len(away_players)
            print(f"{total} players")
            for p in home_players + away_players:
                rows.append(
                    (game_id, season, phase, home_team, away_team, p["team_name"],
                     p["player_name"], p["source_player_id"], p["source_person_id"])
                )
        except Exception as exc:
            print(f"FAILED: {exc}")
        time.sleep(0.3)

    if not rows:
        print("No roster rows collected.")
        return 0

    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM game_rosters WHERE season LIKE 'wfc%%'")
        cur.executemany(
            """
            INSERT INTO game_rosters (game_id, season, phase, home_team_name, away_team_name, team_name, player_name, source_player_id, source_person_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (game_id, player_name, team_name) DO UPDATE
                SET season = EXCLUDED.season,
                    phase = EXCLUDED.phase,
                    home_team_name = EXCLUDED.home_team_name,
                    away_team_name = EXCLUDED.away_team_name,
                    source_player_id = EXCLUDED.source_player_id,
                    source_person_id = EXCLUDED.source_person_id,
                    updated_at = NOW()
            """,
            rows,
        )
        conn.commit()

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest WFC game rosters from IFF API into game_rosters table.")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--token", required=True, help="IFF API Bearer token")
    args = parser.parse_args()
    total = ingest_wfc_rosters(database_url=args.database_url, token=args.token)
    print(f"game-rosters: stored {total} player-game rows")


if __name__ == "__main__":
    main()
