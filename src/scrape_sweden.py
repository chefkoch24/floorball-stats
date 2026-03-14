import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from tqdm import tqdm


STARTKIT_URL = "https://api.innebandy.se/StatsAppApi/api/startkit"
DEFAULT_API_ROOT = "https://api.innebandy.se/v2/api/"

EVENT_GOAL_TYPES = {"M\u00e5l", "Straffm\u00e5l"}
EVENT_PENALTY_TYPES = {"Utvisning"}


@dataclass
class ApiConfig:
    api_root: str
    token: str


def _get_api_config() -> ApiConfig:
    response = requests.get(STARTKIT_URL, timeout=30)
    response.raise_for_status()
    payload = response.json()
    api_root = payload.get("apiRoot") or DEFAULT_API_ROOT
    token = payload.get("accessToken")
    if not token:
        raise RuntimeError("Startkit response did not include accessToken")
    return ApiConfig(api_root=api_root, token=token)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _safe_split_datetime(dt: str | None) -> tuple[str | None, str | None]:
    if not dt:
        return None, None
    if "T" in dt:
        date, time = dt.split("T", 1)
        return date, time
    return dt, None


def _map_penalty_type(penalty_name: str | None) -> str:
    if not penalty_name:
        return "penalty_2"
    name = penalty_name.lower()
    if "2+2" in name:
        return "penalty_2and2"
    if "10" in name:
        return "penalty_10"
    if "matchstraff" in name or "ms" in name:
        return "penalty_ms_full"
    if "2 min" in name or "2min" in name:
        return "penalty_2"
    return "penalty_2"


def _event_to_row(event: dict[str, Any], match: dict[str, Any]) -> dict[str, Any] | None:
    event_type_raw = event.get("MatchEventType")
    if event_type_raw in EVENT_GOAL_TYPES:
        event_type = "goal"
    elif event_type_raw in EVENT_PENALTY_TYPES:
        event_type = "penalty"
    else:
        return None

    home_team = match.get("HomeTeam")
    away_team = match.get("AwayTeam")
    is_home = event.get("IsHomeTeam")
    if is_home is None:
        return None
    event_team = home_team if is_home else away_team

    period = int(event.get("Period") or 0)
    minute = int(event.get("Minute") or 0)
    second = int(event.get("Second") or 0)
    sortkey = f"{period}-{minute:02d}:{second:02d}"

    game_date, game_start_time = _safe_split_datetime(match.get("MatchDateTime"))
    goals_home = event.get("GoalsHomeTeam")
    goals_away = event.get("GoalsAwayTeam")
    if goals_home is None or goals_away is None:
        goals_home = match.get("GoalsHomeTeam")
        goals_away = match.get("GoalsAwayTeam")

    result_string = None
    if match.get("GoalsHomeTeam") is not None and match.get("GoalsAwayTeam") is not None:
        result_string = f"{match.get('GoalsHomeTeam')}-{match.get('GoalsAwayTeam')}"

    row = {
        "event_type": event_type,
        "event_team": event_team,
        "period": period,
        "sortkey": sortkey,
        "game_id": match.get("MatchID"),
        "home_team_name": home_team,
        "away_team_name": away_team,
        "home_goals": goals_home,
        "guest_goals": goals_away,
        "goal_type": "penalty_shot" if event_type_raw == "Straffm\u00e5l" else "goal",
        "penalty_type": _map_penalty_type(event.get("PenaltyName")) if event_type == "penalty" else None,
        "game_date": game_date,
        "game_start_time": game_start_time,
        "game_status": match.get("MatchStatus"),
        "ingame_status": None,
        "result_string": result_string,
    }
    return row


def scrape_competition_events(competition_id: int, output_path: str, include_unplayed: bool = False) -> pd.DataFrame:
    cfg = _get_api_config()
    headers = _auth_headers(cfg.token)

    matches_url = f"{cfg.api_root}competitions/{competition_id}/matches"
    matches_response = requests.get(matches_url, headers=headers, timeout=30)
    matches_response.raise_for_status()
    matches = matches_response.json()

    all_rows: list[dict[str, Any]] = []
    for match in tqdm(matches, desc="matches"):
        if not include_unplayed:
            results = match.get("Results") or []
            has_final = any(r.get("IsFinalResult") for r in results)
            if not has_final:
                continue

        match_id = match.get("MatchID")
        if not match_id:
            continue

        match_url = f"{cfg.api_root}matches/{match_id}"
        match_response = requests.get(match_url, headers=headers, timeout=30)
        match_response.raise_for_status()
        match_detail = match_response.json()

        events = match_detail.get("Events") or []
        if not events:
            continue

        for event in events:
            row = _event_to_row(event, match_detail)
            if row:
                all_rows.append(row)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(all_rows)
    df.to_csv(out, index=False)
    return df


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--competition_id", type=int, required=True)
    parser.add_argument("--output_path", type=str, default="data/data_sweden.csv")
    parser.add_argument("--include_unplayed", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    scrape_competition_events(
        competition_id=args.competition_id,
        output_path=args.output_path,
        include_unplayed=args.include_unplayed,
    )


if __name__ == "__main__":
    main()
