import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.scheduled_games import build_result_game_row, build_scheduled_game_row


PUBLIC_API_ROOT = "https://app.floorball.sport/api/leagueorganizerapi"
AUTH_API_ROOT = "https://iff-api.azurewebsites.net/api"
GAME_OVERVIEW_URL = f"{AUTH_API_ROOT}/magazinegameviewapi/initgameoverview"
REFRESH_TOKEN_URL = f"{AUTH_API_ROOT}/jwtapi/refreshtoken"
DOTNET_DATE_RE = re.compile(r"/Date\((\d+)\)/")
PLAYER_TITLE_RE = re.compile(r"^\s*(?:(?P<number>\d+)\.\s*)?(?P<name>.+?)(?:\s+\((?P<tag>[^)]+)\))?\s*$")
ASSIST_RE = re.compile(r"assist by:\s*(?:(?P<number>\d+)\.\s*)?(?P<name>.+?)\s*$", re.IGNORECASE)
ELIMINATION_ROUND_ORDER = {
    "Play-Off 1": 10,
    "Play-Off 2": 11,
    "Play-Off 3": 12,
    "Play-Off 4": 13,
    "Quarterfinal 1": 20,
    "Quarterfinal 2": 21,
    "Quarterfinal 3": 22,
    "Quarterfinal 4": 23,
    "Semifinal 1": 30,
    "Semifinal 2": 31,
    "Final": 40,
    "3rd Place": 41,
    "5th-8th:1": 50,
    "5th-8th:2": 51,
    "5th Place": 52,
    "7th Place": 53,
    "9th-12th:1": 60,
    "9th-12th:2": 61,
    "9th Place": 62,
    "11th Place": 63,
    "13th-16th:1": 70,
    "13th-16th:2": 71,
    "13th Place": 72,
    "15th Place": 73,
}


@dataclass
class WfcAuth:
    access_token: str
    refresh_token: str


def _get(url: str) -> Any:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def _parse_dotnet_datetime(value: object) -> tuple[str | None, str | None]:
    text = str(value or "").strip()
    match = DOTNET_DATE_RE.search(text)
    if not match:
        return None, None
    timestamp_ms = int(match.group(1))
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")


def _parse_int(value: object) -> int | None:
    text = str(value or "").strip()
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _clean_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_team_name(value: object) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    return re.sub(r"\s+Men$", "", text, flags=re.IGNORECASE).strip() or None


def _load_auth_from_env() -> WfcAuth | None:
    access_token = _clean_text(os.environ.get("IFF_API_ACCESS_TOKEN"))
    refresh_token = _clean_text(os.environ.get("IFF_API_REFRESH_TOKEN"))
    if not access_token and not refresh_token:
        return None
    if not access_token or not refresh_token:
        missing = "IFF_API_ACCESS_TOKEN" if not access_token else "IFF_API_REFRESH_TOKEN"
        raise RuntimeError(f"WFC auth requires both IFF_API_ACCESS_TOKEN and IFF_API_REFRESH_TOKEN; missing {missing}.")
    return WfcAuth(access_token=access_token, refresh_token=refresh_token)


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _refresh_access_token(auth: WfcAuth) -> None:
    response = requests.post(
        REFRESH_TOKEN_URL,
        json={"AccessToken": auth.access_token, "RefreshToken": auth.refresh_token},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    access_token = _clean_text(payload.get("AccessToken"))
    refresh_token = _clean_text(payload.get("RefreshToken"))
    if not access_token or not refresh_token:
        raise RuntimeError("IFF refresh-token response did not include both AccessToken and RefreshToken.")
    auth.access_token = access_token
    auth.refresh_token = refresh_token


def _split_league_display_name(game: dict[str, Any]) -> tuple[str | None, str | None]:
    league_display_name = str(game.get("LeagueDisplayName") or "").strip()
    if not league_display_name:
        return None, None
    if "·" in league_display_name:
        left, right = [part.strip() or None for part in league_display_name.split("·", 1)]
        return left, right
    return league_display_name, None


def _stage_metadata(game: dict[str, Any]) -> dict[str, Any]:
    stage_label, stage_detail = _split_league_display_name(game)
    league_name = str(game.get("LeagueName") or "").strip()
    normalized = league_name.lower()
    if normalized.startswith("group"):
        group_name = league_name or stage_label
        return {
            "tournament_stage_type": "group-stage",
            "tournament_stage_label": group_name,
            "tournament_group": group_name,
            "tournament_round": None,
            "tournament_round_order": None,
        }
    if "play-off" in normalized or "playoffs" in normalized:
        round_name = stage_detail or stage_label or league_name or None
        return {
            "tournament_stage_type": "elimination",
            "tournament_stage_label": round_name,
            "tournament_group": None,
            "tournament_round": round_name,
            "tournament_round_order": ELIMINATION_ROUND_ORDER.get(str(round_name or "").strip()),
        }
    return {
        "tournament_stage_type": None,
        "tournament_stage_label": stage_detail or stage_label,
        "tournament_group": None,
        "tournament_round": None,
        "tournament_round_order": None,
    }


def _game_status(game: dict[str, Any], home_goals: int | None, away_goals: int | None) -> str:
    if bool(game.get("Cancelled")):
        return "Cancelled"
    if bool(game.get("Postponed")):
        return "Postponed"
    if bool(game.get("Interrupted")):
        return "Interrupted"
    if home_goals is not None and away_goals is not None:
        return "Final"
    return "Scheduled"


def _result_suffix(game: dict[str, Any]) -> str:
    result_type_id = _parse_int(game.get("FinalResultTypeID")) or 0
    if result_type_id == 1:
        return " OT"
    if result_type_id == 2:
        return " PS"
    return ""


def _goal_type_from_title_tag(title_tag: str | None) -> str:
    marker = str(title_tag or "").strip().upper()
    if marker == "PS":
        return "penalty_shot"
    return "goal"


def _map_penalty_type(description: str | None) -> str:
    text = str(description or "").lower()
    if "2+2" in text:
        return "penalty_2and2"
    if "10" in text:
        return "penalty_10"
    if "match" in text or "ms" in text:
        return "penalty_ms_full"
    return "penalty_2"


def _parse_player_title(title: object) -> tuple[str | None, str | None, str | None]:
    text = _clean_text(title)
    if not text:
        return None, None, None
    match = PLAYER_TITLE_RE.match(text)
    if not match:
        return text, None, None
    return (
        _clean_text(match.group("name")),
        _clean_text(match.group("number")),
        _clean_text(match.group("tag")),
    )


def _parse_assist(description: object) -> tuple[str | None, str | None]:
    text = _clean_text(description)
    if not text:
        return None, None
    match = ASSIST_RE.search(text)
    if not match:
        return None, None
    return _clean_text(match.group("name")), _clean_text(match.group("number"))


def _build_player_lookup(overview: dict[str, Any]) -> dict[tuple[str, str], str]:
    lookup: dict[tuple[str, str], str] = {}
    game_stats = overview.get("GameStats") or {}
    for side_key in ("HomeTeamPlayers", "AwayTeamPlayers", "HomeTeamGoalies", "AwayTeamGoalies"):
        for player in game_stats.get(side_key) or []:
            shirt_number = _clean_text(player.get("ShirtNumber"))
            full_name = _clean_text(player.get("Name"))
            if not shirt_number or not full_name:
                continue
            parts = [part for part in re.split(r"\s+", full_name) if part]
            surname = parts[-1] if parts else full_name
            lookup.setdefault((shirt_number, surname.lower()), full_name)
    return lookup


def _resolve_player_name(name: str | None, number: str | None, player_lookup: dict[tuple[str, str], str]) -> str | None:
    if not name:
        return None
    if not number:
        return name
    resolved = player_lookup.get((str(number), name.lower()))
    return resolved or name


def _period_and_sortkey(game_minute: object, game_clock_second: object) -> tuple[int | None, str | None]:
    minute_text = str(game_minute or "").strip()
    if ":" not in minute_text:
        return None, None
    minute_part, second_part = minute_text.split(":", 1)
    try:
        absolute_minute = int(minute_part)
        absolute_second = int(second_part)
    except ValueError:
        return None, None
    total_seconds = absolute_minute * 60 + absolute_second
    period = max(1, (total_seconds // (20 * 60)) + 1)
    clock_second = _parse_int(game_clock_second)
    if clock_second is None:
        relative_seconds = total_seconds % (20 * 60)
    else:
        relative_seconds = max(0, min(clock_second, 20 * 60))
    return period, f"{period}-{relative_seconds // 60:02d}:{relative_seconds % 60:02d}"


def _attach_game_metadata(row: dict[str, Any], game: dict[str, Any], stage_metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "venue": str(game.get("ArenaName") or "").strip() or None,
        "venue_address": None,
        "competition_name": str(game.get("FederationOrCupName") or "").strip() or None,
        "league_name": str(game.get("LeagueDisplayName") or "").strip() or None,
        **stage_metadata,
    }


def _parse_score(value: object) -> tuple[int | None, int | None]:
    text = str(value or "").strip()
    if "-" not in text:
        return None, None
    left, right = text.split("-", 1)
    return _parse_int(left), _parse_int(right)


def _overview_event_to_row(
    blurb: dict[str, Any],
    game: dict[str, Any],
    stage_metadata: dict[str, Any],
    player_lookup: dict[tuple[str, str], str],
) -> dict[str, Any] | None:
    is_goal = bool(blurb.get("IsGoal"))
    description = _clean_text(blurb.get("Description"))
    if not is_goal and not description:
        return None

    period, sortkey = _period_and_sortkey(blurb.get("GameMinute"), blurb.get("GameClockSecond"))
    if not period or not sortkey:
        return None

    game_id = game.get("GameID")
    home_team = _normalize_team_name(game.get("HomeTeamDisplayName"))
    away_team = _normalize_team_name(game.get("AwayTeamDisplayName"))
    game_date, game_start_time = _parse_dotnet_datetime(game.get("GameTime"))
    attendance = _parse_int(game.get("Spectators"))
    event_team = away_team if bool(blurb.get("IsAwayTeamAction")) else home_team
    home_goals, away_goals = _parse_score(blurb.get("Score"))
    player_name, player_number, title_tag = _parse_player_title(blurb.get("Title"))
    assist_name, assist_number = _parse_assist(description)
    player_name = _resolve_player_name(player_name, player_number, player_lookup)
    assist_name = _resolve_player_name(assist_name, assist_number, player_lookup)

    row = {
        "event_type": "goal" if is_goal else "penalty",
        "event_team": event_team,
        "period": period,
        "sortkey": sortkey,
        "game_id": game_id,
        "home_team_name": home_team,
        "away_team_name": away_team,
        "home_goals": home_goals,
        "guest_goals": away_goals,
        "goal_type": _goal_type_from_title_tag(title_tag) if is_goal else None,
        "penalty_type": None if is_goal else _map_penalty_type(description),
        "game_date": game_date,
        "game_start_time": game_start_time,
        "attendance": attendance,
        "game_status": "Final",
        "ingame_status": None,
        "result_string": None,
        "scorer_name": player_name if is_goal else None,
        "assist_name": assist_name if is_goal else None,
        "scorer_number": player_number if is_goal else None,
        "assist_number": assist_number if is_goal else None,
        "penalty_player_name": None if is_goal else player_name,
    }
    return _attach_game_metadata(row, game, stage_metadata)


def _fetch_game_overview(game_id: int, auth: WfcAuth) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(2):
        response = requests.get(
            GAME_OVERVIEW_URL,
            params={"GameID": game_id},
            headers=_auth_headers(auth.access_token),
            timeout=30,
        )
        if response.status_code != 401:
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
        last_error = requests.HTTPError(f"WFC overview returned HTTP 401 for game {game_id}.")
        if attempt == 0:
            _refresh_access_token(auth)
    if last_error:
        raise last_error
    return {}


def _build_rows_from_game(game: dict[str, Any], auth: WfcAuth | None = None) -> list[dict[str, Any]]:
    stage_metadata = _stage_metadata(game)
    base_row = _build_game_row(game)
    home_goals = _parse_int(game.get("HomeTeamScore"))
    away_goals = _parse_int(game.get("AwayTeamScore"))
    game_id = _parse_int(game.get("GameID"))

    rows: list[dict[str, Any]] = [base_row]
    if auth is None or game_id is None or home_goals is None or away_goals is None:
        return rows

    overview = _fetch_game_overview(game_id, auth)
    blurbs = overview.get("Blurbs") or []
    if not isinstance(blurbs, list):
        return rows
    player_lookup = _build_player_lookup(overview)

    event_rows = [
        row
        for blurb in blurbs
        for row in [_overview_event_to_row(blurb, game, stage_metadata, player_lookup)]
        if row is not None
    ]
    if not event_rows:
        return rows
    return rows + event_rows


def _build_game_row(game: dict[str, Any]) -> dict[str, Any]:
    game_id = game.get("GameID")
    home_team = _normalize_team_name(game.get("HomeTeamDisplayName"))
    away_team = _normalize_team_name(game.get("AwayTeamDisplayName"))
    home_goals = _parse_int(game.get("HomeTeamScore"))
    away_goals = _parse_int(game.get("AwayTeamScore"))
    game_date, game_start_time = _parse_dotnet_datetime(game.get("GameTime"))
    attendance = _parse_int(game.get("Spectators"))
    game_status = _game_status(game, home_goals, away_goals)
    result_string = None
    stage_metadata = _stage_metadata(game)
    if home_goals is not None and away_goals is not None:
        result_string = f"{home_goals}-{away_goals}{_result_suffix(game)}"

    if home_goals is not None and away_goals is not None:
        periods = _parse_int(game.get("NumberOfPeriods")) or 3
        sortkey = f"{periods}-20:00"
        return _attach_game_metadata(
            build_result_game_row(
                game_id=game_id,
                home_team=home_team,
                away_team=away_team,
                game_date=game_date,
                game_start_time=game_start_time,
                home_goals=home_goals,
                away_goals=away_goals,
                attendance=attendance,
                game_status=game_status,
                result_string=result_string,
                period=periods,
                sortkey=sortkey,
            ),
            game,
            stage_metadata,
        )

    return _attach_game_metadata(
        build_scheduled_game_row(
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            game_date=game_date,
            game_start_time=game_start_time,
            attendance=attendance,
            game_status=game_status,
            result_string=result_string,
        ),
        game,
        stage_metadata,
    )


def _matches_stage(game: dict[str, Any], phase: str | None) -> bool:
    if phase in (None, "", "all"):
        return True
    league_name = str(game.get("LeagueName") or "").strip().lower()
    if phase == "regular-season":
        return league_name.startswith("group")
    if phase == "playoffs":
        return "play-off" in league_name or "playoffs" in league_name
    return True


def fetch_previous_league_organizer_games(
    league_organizer_id: int,
    *,
    phase: str | None = None,
    start_last_game_id: int = 0,
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    games: list[dict[str, Any]] = []
    seen_game_ids: set[int] = set()
    cursor = start_last_game_id
    page_count = 0

    while True:
        payload = _get(
            f"{PUBLIC_API_ROOT}/getpreviousleagueorganizergames?LeagueOrganizerID={league_organizer_id}&LastGameID={cursor}"
        )
        if not isinstance(payload, list) or not payload:
            break

        page_game_ids: list[int] = []
        new_ids_on_page = 0
        for game in payload:
            game_id = _parse_int(game.get("GameID"))
            if game_id is None:
                continue
            page_game_ids.append(game_id)
            if game_id in seen_game_ids:
                continue
            seen_game_ids.add(game_id)
            new_ids_on_page += 1
            if not _matches_stage(game, phase):
                continue
            games.append(game)

        page_count += 1
        if max_pages is not None and page_count >= max_pages:
            break
        if not page_game_ids or new_ids_on_page == 0:
            break
        cursor = page_game_ids[-1]

    return games


def scrape_league_organizer_games(league_organizer_id: int, output_path: str, *, phase: str | None = None) -> pd.DataFrame:
    raw_games = fetch_previous_league_organizer_games(league_organizer_id, phase=phase)
    auth = _load_auth_from_env()
    rows = [row for game in raw_games for row in _build_rows_from_game(game, auth)]
    rows.sort(
        key=lambda row: (
            str(row.get("game_date") or ""),
            str(row.get("game_start_time") or ""),
            str(row.get("game_id") or ""),
            int(row.get("period") or 0),
            str(row.get("sortkey") or ""),
        )
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    return df
