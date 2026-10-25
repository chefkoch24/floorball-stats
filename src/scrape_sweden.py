import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from tqdm import tqdm

from src.http_client import request_with_retries
from src.scheduled_games import build_scheduled_game_row


STARTKIT_URL = "https://api.innebandy.se/StatsAppApi/api/startkit"
DEFAULT_API_ROOT = "https://api.innebandy.se/v2/api/"

EVENT_GOAL_TYPES = {"M\u00e5l", "Straffm\u00e5l", "M\u00e5l i tom bur"}
EVENT_PENALTY_TYPES = {"Utvisning"}


@dataclass
class ApiConfig:
    api_root: str
    token: str


def _get_api_config() -> ApiConfig:
    response = request_with_retries("GET", STARTKIT_URL, timeout=30)
    payload = response.json()
    api_root = payload.get("apiRoot") or DEFAULT_API_ROOT
    token = payload.get("accessToken")
    if not token:
        raise RuntimeError("Startkit response did not include accessToken")
    return ApiConfig(api_root=api_root, token=token)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _fetch_federation_competitions(api_root: str, headers: dict[str, str], federation_id: int = 1) -> list[dict[str, Any]]:
    response = request_with_retries(
        "GET",
        f"{api_root}federations/{federation_id}/competitions",
        headers=headers,
        timeout=30,
    )
    payload = response.json()
    return payload if isinstance(payload, list) else []


def _fetch_competition(api_root: str, headers: dict[str, str], competition_id: int) -> dict[str, Any]:
    response = request_with_retries("GET", f"{api_root}competitions/{competition_id}", headers=headers, timeout=30)
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _fetch_competition_category_competitions(
    api_root: str, headers: dict[str, str], category_id: int
) -> list[dict[str, Any]]:
    response = request_with_retries(
        "GET",
        f"{api_root}competitioncategories/{category_id}/competitions",
        headers=headers,
        timeout=30,
    )
    payload = response.json()
    return payload if isinstance(payload, list) else []


def _list_category_competitions(
    api_root: str,
    headers: dict[str, str],
    category_id: int,
    federation_competitions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    try:
        return _fetch_competition_category_competitions(api_root, headers, category_id)
    except requests.HTTPError:
        # The public API dropped the category endpoint in 2026; the federation
        # list only holds current-season competitions but carries CategoryID.
        return [item for item in federation_competitions if item.get("CategoryID") == category_id]


def expand_competition_ids_by_category(competition_ids: list[int], federation_id: int = 1) -> list[int]:
    """Resolve the playoff competitions (one per series) for the given competitions.

    A regular-season competition (non-zero PlayOffCategoryID) maps to its playoff
    category, so a config can point at the regular season before the playoff
    series exist. A playoff competition expands to all series of its category.
    Only competitions of the same season are returned.
    """
    cfg = _get_api_config()
    headers = _auth_headers(cfg.token)
    federation_competitions = _fetch_federation_competitions(cfg.api_root, headers, federation_id=federation_id)
    season_by_id: dict[int, Any] = {}

    def _season_of(competition_id: int) -> Any:
        if competition_id not in season_by_id:
            season_by_id[competition_id] = _fetch_competition(cfg.api_root, headers, competition_id).get("SeasonID")
        return season_by_id[competition_id]

    targets: set[tuple[int, Any]] = set()
    playoff_ids: set[int] = set()
    for competition_id in {int(value) for value in competition_ids}:
        detail = _fetch_competition(cfg.api_root, headers, competition_id)
        season_by_id[competition_id] = detail.get("SeasonID")
        playoff_category_id = int(detail.get("PlayOffCategoryID") or 0)
        if playoff_category_id:
            targets.add((playoff_category_id, detail.get("SeasonID")))
        elif detail.get("CategoryID") is not None:
            targets.add((int(detail["CategoryID"]), detail.get("SeasonID")))
            playoff_ids.add(competition_id)
    if not targets:
        return sorted({int(value) for value in competition_ids})

    expanded: set[int] = set()
    for category_id, season_id in targets:
        for item in _list_category_competitions(cfg.api_root, headers, category_id, federation_competitions):
            if item.get("CompetitionID") is None:
                continue
            candidate_id = int(item["CompetitionID"])
            if season_id is not None and (item.get("SeasonID") or _season_of(candidate_id)) != season_id:
                continue
            expanded.add(candidate_id)
    # Never fall back to a regular-season competition: before the playoff series
    # are published this returns an empty list.
    return sorted(expanded or playoff_ids)


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
        # Since 2026 events name their side via MatchTeamID instead of IsHomeTeam.
        team_id = event.get("MatchTeamID")
        if team_id and team_id == match.get("HomeMatchTeamID"):
            is_home = True
        elif team_id and team_id == match.get("AwayMatchTeamID"):
            is_home = False
        else:
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
        "attendance": match.get("Spectators"),
        "game_status": match.get("MatchStatus"),
        "ingame_status": None,
        "result_string": result_string,
        "scorer_name": event.get("PlayerName") if event_type == "goal" else None,
        "assist_name": event.get("PlayerAssistName") if event_type == "goal" else None,
        "scorer_number": event.get("PlayerShirtNo") if event_type == "goal" else None,
        "assist_number": event.get("PlayerAssistShirtNo") if event_type == "goal" else None,
        "penalty_player_name": event.get("PlayerName") if event_type == "penalty" else None,
    }
    return row


def scrape_competition_events(competition_id: int, output_path: str, include_unplayed: bool = False) -> pd.DataFrame:
    cfg = _get_api_config()
    headers = _auth_headers(cfg.token)

    matches_url = f"{cfg.api_root}competitions/{competition_id}/matches"
    matches_response = request_with_retries("GET", matches_url, headers=headers, timeout=30)
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
        try:
            match_response = request_with_retries("GET", match_url, headers=headers, timeout=30)
            match_detail = match_response.json()
        except requests.RequestException as exc:
            tqdm.write(f"[sweden] failed to fetch match {match_id}: {exc}")
            if include_unplayed:
                game_date, game_start_time = _safe_split_datetime(match.get("MatchDateTime"))
                all_rows.append(
                    build_scheduled_game_row(
                        game_id=match_id,
                        home_team=match.get("HomeTeam"),
                        away_team=match.get("AwayTeam"),
                        game_date=game_date,
                        game_start_time=game_start_time,
                        attendance=match.get("Spectators"),
                        game_status=match.get("MatchStatus") or "Scheduled",
                    )
                )
            continue

        events = match_detail.get("Events") or []
        if not events:
            if include_unplayed:
                game_date, game_start_time = _safe_split_datetime(match_detail.get("MatchDateTime"))
                all_rows.append(
                    build_scheduled_game_row(
                        game_id=match_id,
                        home_team=match_detail.get("HomeTeam"),
                        away_team=match_detail.get("AwayTeam"),
                        game_date=game_date,
                        game_start_time=game_start_time,
                        attendance=match_detail.get("Spectators"),
                        game_status=match_detail.get("MatchStatus") or "Scheduled",
                    )
                )
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


def scrape_competitions_events(
    competition_ids: list[int],
    output_path: str,
    include_unplayed: bool = False,
) -> pd.DataFrame:
    cfg = _get_api_config()
    headers = _auth_headers(cfg.token)

    all_rows: list[dict[str, Any]] = []
    seen_match_ids: set[int] = set()
    for competition_id in competition_ids:
        matches_url = f"{cfg.api_root}competitions/{competition_id}/matches"
        matches_response = request_with_retries("GET", matches_url, headers=headers, timeout=30)
        matches = matches_response.json()

        for match in tqdm(matches, desc=f"competition {competition_id}"):
            match_id = match.get("MatchID")
            if not match_id or match_id in seen_match_ids:
                continue

            if not include_unplayed:
                results = match.get("Results") or []
                has_final = any(r.get("IsFinalResult") for r in results)
                if not has_final:
                    continue

            match_url = f"{cfg.api_root}matches/{match_id}"
            try:
                match_response = request_with_retries("GET", match_url, headers=headers, timeout=30)
                match_detail = match_response.json()
            except requests.RequestException as exc:
                tqdm.write(f"[sweden] failed to fetch match {match_id}: {exc}")
                if include_unplayed:
                    game_date, game_start_time = _safe_split_datetime(match.get("MatchDateTime"))
                    all_rows.append(
                        build_scheduled_game_row(
                            game_id=match_id,
                            home_team=match.get("HomeTeam"),
                            away_team=match.get("AwayTeam"),
                            game_date=game_date,
                            game_start_time=game_start_time,
                            attendance=match.get("Spectators"),
                            game_status=match.get("MatchStatus") or "Scheduled",
                        )
                    )
                seen_match_ids.add(match_id)
                continue
            events = match_detail.get("Events") or []

            if not events:
                if include_unplayed:
                    game_date, game_start_time = _safe_split_datetime(match_detail.get("MatchDateTime"))
                    all_rows.append(
                        build_scheduled_game_row(
                            game_id=match_id,
                            home_team=match_detail.get("HomeTeam"),
                            away_team=match_detail.get("AwayTeam"),
                            game_date=game_date,
                            game_start_time=game_start_time,
                            attendance=match_detail.get("Spectators"),
                            game_status=match_detail.get("MatchStatus") or "Scheduled",
                        )
                    )
                seen_match_ids.add(match_id)
                continue

            for event in events:
                row = _event_to_row(event, match_detail)
                if row:
                    all_rows.append(row)
            seen_match_ids.add(match_id)

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
