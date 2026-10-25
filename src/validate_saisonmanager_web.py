"""Smoke test for the saisonmanager.de web fallback.

Renders a league schedule and the most recent finished games with the same
client the pipeline uses, then checks each game for consistency. Writes no
database rows and no repository files (fresh temporary cache), so it is safe
to run in CI before enabling the nightly refresh:

    python -m src.validate_saisonmanager_web --league-id 2447 --games 3
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
import time

from src.scrape_saisonmanager_web import SaisonmanagerWebClient


def check_game(game: dict) -> list[str]:
    problems: list[str] = []
    goals = [event for event in game["events"] if event["event_type"] == "goal"]
    score = re.match(r"(\d+):(\d+)", game.get("result_string") or "")
    if not score:
        problems.append(f"no final score ({game.get('result_string')!r})")
    elif int(score.group(1)) + int(score.group(2)) != len(goals):
        problems.append(f"{len(goals)} goal events for result {game['result_string']}")
    unnamed = [
        event["sortkey"]
        for event in goals
        if not event.get("number") and not event.get("player_name_hint") and event.get("goal_type") != "own_goal"
    ]
    if unnamed:
        problems.append(f"goals without scorer at {', '.join(unnamed)}")
    for side in ("home", "guest"):
        if not game["players"].get(side):
            problems.append(f"empty {side} lineup")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--league-id", type=int, required=True)
    parser.add_argument("--games", type=int, default=3, help="number of most recent finished games to render")
    args = parser.parse_args()

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as cache_dir, SaisonmanagerWebClient(
        league_id=args.league_id, cache_dir=cache_dir
    ) as client:
        started = time.monotonic()
        schedule = client.get_json(f"leagues/{args.league_id}/schedule.json")
        played = [entry for entry in schedule if entry["played"]]
        print(f"schedule: {len(schedule)} games, {len(played)} finished ({time.monotonic() - started:.1f}s)")
        if not played:
            failures.append("schedule lists no finished games")
        for entry in played[-args.games :]:
            started = time.monotonic()
            game = client.get_game(entry["game_id"])
            problems = check_game(game)
            print(
                f"game {entry['game_id']}: {game['home_team_name']} {game['result_string']} {game['guest_team_name']}, "
                f"{len(game['events'])} events, lineups {len(game['players']['home'])}/{len(game['players']['guest'])} "
                f"({time.monotonic() - started:.1f}s) -> {'OK' if not problems else '; '.join(problems)}"
            )
            failures.extend(f"game {entry['game_id']}: {problem}" for problem in problems)

    if failures:
        print("FAILED:\n  " + "\n  ".join(failures))
        return 1
    print("OK: saisonmanager.de web fallback works from this environment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
