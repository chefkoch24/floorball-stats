import json
from pathlib import Path
import pandas as pd
import requests
from tqdm import tqdm
import argparse

DEFAULT_API_BASE = "https://saisonmanager.de/api/v2/"


def scrape_events(input_path: str, output_path: str, api_base: str = DEFAULT_API_BASE) -> pd.DataFrame:
    games_endpoint = "games/"
    all_games = json.loads(requests.request("GET", api_base + input_path).content)
    game_ids = [x["game_id"] for x in all_games]
    all_events = []

    for game_id in tqdm(game_ids):
        game = json.loads(requests.request("GET", api_base + games_endpoint + str(game_id)).content)
        home_team_name = game["home_team_name"]
        away_team_name = game["guest_team_name"]
        game_date = game.get("date")
        game_start_time = game.get("start_time")
        game_status = game.get("game_status")
        ingame_status = game.get("ingame_status")
        result_string = game.get("result_string")
        events = game["events"]
        for event in events:
            event["event_team"] = home_team_name if event["event_team"] == "home" else away_team_name
            event["game_id"] = game_id
            event["home_team_name"] = home_team_name
            event["away_team_name"] = away_team_name
            event["game_date"] = game_date
            event["game_start_time"] = game_start_time
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
