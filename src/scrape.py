import json
from pathlib import Path
import pandas as pd
import requests
from tqdm import tqdm
import argparse

from src.scheduled_games import build_scheduled_game_row

DEFAULT_API_BASE = "https://saisonmanager.de/api/v2/"


def _normalize_shirt_number(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return str(int(text))
    except ValueError:
        return text


def _build_player_map(players: list[dict] | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for player in players or []:
        shirt_number = _normalize_shirt_number(player.get("trikot_number"))
        first_name = str(player.get("player_firstname") or "").strip()
        last_name = str(player.get("player_name") or "").strip()
        player_name = " ".join(part for part in [first_name, last_name] if part).strip()
        if shirt_number and player_name:
            mapping[shirt_number] = player_name
    return mapping


def scrape_events(input_path: str, output_path: str, api_base: str = DEFAULT_API_BASE) -> pd.DataFrame:
    games_endpoint = "games/"
    all_games = json.loads(requests.request("GET", api_base + input_path).content)
    game_ids = [x["game_id"] for x in all_games]
    all_events = []

    for game_id in tqdm(game_ids):
        game = json.loads(requests.request("GET", api_base + games_endpoint + str(game_id)).content)
        home_team_name = game["home_team_name"]
        away_team_name = game["guest_team_name"]
        player_map = {}
        player_map.update(_build_player_map((game.get("players") or {}).get("home")))
        player_map.update(_build_player_map((game.get("players") or {}).get("guest")))
        game_date = game.get("date")
        game_start_time = game.get("start_time")
        attendance = game.get("audience")
        game_status = game.get("game_status")
        ingame_status = game.get("ingame_status")
        result_string = game.get("result_string")
        events = game["events"]
        if not events:
            all_events.append(
                build_scheduled_game_row(
                    game_id=game_id,
                    home_team=home_team_name,
                    away_team=away_team_name,
                    game_date=game_date,
                    game_start_time=game_start_time,
                    attendance=attendance,
                    game_status=game_status or "Scheduled",
                    ingame_status=ingame_status,
                    result_string=result_string,
                )
            )
            continue
        for event in events:
            event["event_team"] = home_team_name if event["event_team"] == "home" else away_team_name
            scorer_number = _normalize_shirt_number(event.get("number"))
            assist_number = _normalize_shirt_number(event.get("assist"))
            event["scorer_number"] = scorer_number
            event["assist_number"] = assist_number
            event["scorer_name"] = player_map.get(scorer_number) if scorer_number else None
            event["assist_name"] = player_map.get(assist_number) if assist_number else None
            event["penalty_player_name"] = player_map.get(scorer_number) if event.get("event_type") == "penalty" and scorer_number else None
            event["game_id"] = game_id
            event["home_team_name"] = home_team_name
            event["away_team_name"] = away_team_name
            event["game_date"] = game_date
            event["game_start_time"] = game_start_time
            event["attendance"] = attendance
            event["game_status"] = game_status
            event["ingame_status"] = ingame_status
            event["result_string"] = result_string
            all_events.append(event)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(all_events)
    df.to_csv(out, index=False)
    return df


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_path", type=str, default="leagues/1204/schedule.json")
    parser.add_argument("--output_path", type=str, default="data/data_regular_season.csv")
    parser.add_argument("--api_base", type=str, default=DEFAULT_API_BASE)
    return parser.parse_args()


def main():
    args = parse_args()
    scrape_events(input_path=args.input_path, output_path=args.output_path, api_base=args.api_base)


if __name__ == "__main__":
    main()
