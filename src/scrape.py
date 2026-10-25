import json
import os
from pathlib import Path
import pandas as pd
import requests
from tqdm import tqdm
import argparse

from src.scheduled_games import build_scheduled_game_row

DEFAULT_API_BASE = "https://saisonmanager.de/api/v2/"
API_KEY_ENV = "SAISONMANAGER_API_KEY"


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


def _resolve_player_name(
    shirt_number: str | None,
    raw_event_team: object,
    home_player_map: dict[str, str],
    away_player_map: dict[str, str],
) -> str | None:
    if not shirt_number:
        return None

    team_key = str(raw_event_team or "").strip().lower()
    if team_key == "home":
        return home_player_map.get(shirt_number)
    if team_key in {"guest", "away"}:
        return away_player_map.get(shirt_number)

    in_home = shirt_number in home_player_map
    in_away = shirt_number in away_player_map
    if in_home and not in_away:
        return home_player_map.get(shirt_number)
    if in_away and not in_home:
        return away_player_map.get(shirt_number)
    return None


def saisonmanager_headers() -> dict[str, str]:
    # Since summer 2026 the public Saisonmanager API requires a personal key
    # (request it via saisonmanager.de, "API-Zugang").
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    return {"X-Api-Key": api_key} if api_key else {}


def fetch_saisonmanager_json(path: str, api_base: str = DEFAULT_API_BASE, session: requests.Session | None = None):
    client = session or requests
    response = client.get(api_base + path, headers=saisonmanager_headers(), timeout=30)
    if response.status_code == 401:
        hint = "is missing" if not saisonmanager_headers() else "was rejected"
        raise RuntimeError(f"Saisonmanager API returned 401: {API_KEY_ENV} {hint} ({api_base + path}).")
    response.raise_for_status()
    return json.loads(response.content)


def scrape_events(input_path: str, output_path: str, api_base: str = DEFAULT_API_BASE) -> pd.DataFrame:
    if not saisonmanager_headers():
        # Without an API key read the public saisonmanager.de pages instead;
        # the web client answers with the same JSON shape as the API.
        from src.scrape_saisonmanager_web import SaisonmanagerWebClient

        print(f"[saisonmanager] {API_KEY_ENV} not set; reading the public web pages instead of the API.")
        with SaisonmanagerWebClient() as web:
            return _scrape_events_with(web.get_json, input_path, output_path)
    session = requests.Session()
    return _scrape_events_with(
        lambda path: fetch_saisonmanager_json(path, api_base=api_base, session=session),
        input_path,
        output_path,
    )


def _scrape_events_with(fetch, input_path: str, output_path: str) -> pd.DataFrame:
    games_endpoint = "games/"
    all_games = fetch(input_path)
    game_ids = [x["game_id"] for x in all_games]
    all_events = []

    for game_id in tqdm(game_ids):
        game = fetch(games_endpoint + str(game_id))
        home_team_name = game["home_team_name"]
        away_team_name = game["guest_team_name"]
        home_player_map = _build_player_map((game.get("players") or {}).get("home"))
        away_player_map = _build_player_map((game.get("players") or {}).get("guest"))
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
            # Web-fallback events carry names directly in case a shirt number is missing.
            player_name_hint = event.pop("player_name_hint", None)
            assist_name_hint = event.pop("assist_name_hint", None)
            raw_event_team = event.get("event_team")
            event["event_team"] = home_team_name if raw_event_team == "home" else away_team_name
            scorer_number = _normalize_shirt_number(event.get("number"))
            assist_number = _normalize_shirt_number(event.get("assist"))
            event["scorer_number"] = scorer_number
            event["assist_number"] = assist_number
            event["scorer_name"] = _resolve_player_name(
                scorer_number,
                raw_event_team,
                home_player_map,
                away_player_map,
            ) or player_name_hint
            event["assist_name"] = _resolve_player_name(
                assist_number,
                raw_event_team,
                home_player_map,
                away_player_map,
            ) or assist_name_hint
            event["penalty_player_name"] = (
                _resolve_player_name(
                    scorer_number,
                    raw_event_team,
                    home_player_map,
                    away_player_map,
                ) or player_name_hint
                if event.get("event_type") == "penalty"
                else None
            )
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
