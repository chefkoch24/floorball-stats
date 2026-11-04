"""IFF Champions Cup backend.

The Champions Cup runs in the IFF app like the WFC (one LeagueOrganizerID per
edition, e.g. 853 for 2027), so this module reuses the WFC parsing helpers and
only adds what differs:

- the feed needs IFF_API_ACCESS_TOKEN / IFF_API_REFRESH_TOKEN (no public API),
- men and women share one organizer and are split by league name,
- team names look like "Storvreta IBK (SWE) Men" and are mapped to the names the
  national backends use, so team and player pages line up across competitions,
- periods last 15 minutes and kick-off times are given in UTC.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from src.scheduled_games import build_result_game_row, build_scheduled_game_row
from src.scrape_wfc import (
    WfcAuth,
    _attach_game_metadata,
    _build_player_lookup,
    _clean_text,
    _fetch_game_overview,
    _load_auth_from_env,
    _overview_event_to_row,
    _parse_dotnet_datetime,
    _parse_int,
    _result_suffix,
    fetch_previous_league_organizer_games,
)


PERIOD_SECONDS = 15 * 60
REGULATION_PERIODS = 3
LOCAL_TIMEZONE = ZoneInfo("Europe/Berlin")
GAME_STATUS_FINISHED = 3
DISPLAY_NAME_RE = re.compile(
    r"^(?P<club>.+?)\s*\((?P<country>[A-Z]{3})\)\s*(?P<division>Men|Women)?\s*$",
    re.IGNORECASE,
)
CONFERENCE_RE = re.compile(r"\b(Northern|Southern)\s+Conference\b", re.IGNORECASE)
# Checked in order: "Quarterfinals" and "Semi-finals" both contain "final".
ROUNDS = (
    ("quarter", "Quarter-finals", 20),
    ("semi", "Semi-finals", 30),
    ("final", "Final", 40),
)
# National backend per IFF country code; women's leagues add "w" (see LEAGUES in pelicanconf).
COUNTRY_LEAGUE_PREFIX = {"SWE": "se", "FIN": "fi", "CZE": "cz", "SUI": "ch"}


def parse_team_display_name(value: object) -> tuple[str | None, str | None, str | None]:
    """Split "Storvreta IBK (SWE) Men" into ("Storvreta IBK", "SWE", "men")."""
    text = _clean_text(value)
    if not text:
        return None, None, None
    match = DISPLAY_NAME_RE.match(text)
    if not match:
        return text, None, None
    division = (match.group("division") or "").lower() or None
    return match.group("club").strip(), match.group("country").upper(), division


def national_league_prefix(country: str | None, division: str | None) -> str | None:
    prefix = COUNTRY_LEAGUE_PREFIX.get(str(country or "").upper())
    if not prefix:
        return None
    return f"{prefix}w" if division == "women" else prefix


def make_team_normalizer(team_aliases: dict[str, str] | None = None):
    aliases = {str(key).strip(): str(value).strip() for key, value in (team_aliases or {}).items()}

    def normalize(value: object) -> str | None:
        club, _country, _division = parse_team_display_name(value)
        if not club:
            return None
        return aliases.get(club, club)

    return normalize


def game_division(game: dict[str, Any]) -> str | None:
    league_name = str(game.get("LeagueName") or "").strip().lower()
    if league_name.startswith("women"):
        return "women"
    if league_name.startswith("men"):
        return "men"
    return parse_team_display_name(game.get("HomeTeamDisplayName"))[2]


def stage_metadata(game: dict[str, Any]) -> dict[str, Any]:
    league_name = str(game.get("LeagueName") or "").strip()
    normalized = league_name.lower()
    round_name, round_order = None, None
    for needle, name, order in ROUNDS:
        if needle in normalized:
            round_name, round_order = name, order
            break
    conference = CONFERENCE_RE.search(league_name)
    return {
        "tournament_stage_type": "elimination" if round_name else None,
        "tournament_stage_label": league_name or None,
        "tournament_group": f"{conference.group(1).title()} Conference" if conference else None,
        "tournament_round": round_name,
        "tournament_round_order": round_order,
    }


def parse_game_time(value: object) -> tuple[str | None, str | None]:
    """Kick-off as local (Europe/Berlin) date and time; the feed sends ISO UTC timestamps."""
    text = str(value or "").strip()
    if not text:
        return None, None
    if text.startswith("/Date("):
        return _parse_dotnet_datetime(text)
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None, None
    if moment.tzinfo is not None:
        moment = moment.astimezone(LOCAL_TIMEZONE)
    return moment.strftime("%Y-%m-%d"), moment.strftime("%H:%M")


def _is_finished(game: dict[str, Any]) -> bool:
    # Scheduled games come with a 0-0 score, so the score alone does not mark a result.
    return _parse_int(game.get("GameStatusID")) == GAME_STATUS_FINISHED and not bool(game.get("Cancelled"))


def _game_status(game: dict[str, Any]) -> str:
    if bool(game.get("Cancelled")):
        return "Cancelled"
    if bool(game.get("Postponed")):
        return "Postponed"
    return "Final" if _is_finished(game) else "Scheduled"


def build_game_row(game: dict[str, Any], normalize_team) -> dict[str, Any]:
    home_team = normalize_team(game.get("HomeTeamDisplayName"))
    away_team = normalize_team(game.get("AwayTeamDisplayName"))
    game_date, game_start_time = parse_game_time(game.get("GameTime"))
    attendance = _parse_int(game.get("Spectators"))
    metadata = stage_metadata(game)
    home_goals = _parse_int(game.get("HomeTeamScore"))
    away_goals = _parse_int(game.get("AwayTeamScore"))
    if _is_finished(game) and home_goals is not None and away_goals is not None:
        # In two-legged ties the feed flags the tie-break overtime after a second leg
        # (FinalResultTypeID), but that period is not part of the game score.
        suffix = _result_suffix(game) if metadata["tournament_round"] == "Final" else ""
        row = build_result_game_row(
            game_id=game.get("GameID"),
            home_team=home_team,
            away_team=away_team,
            game_date=game_date,
            game_start_time=game_start_time,
            home_goals=home_goals,
            away_goals=away_goals,
            attendance=attendance,
            game_status="Final",
            result_string=f"{home_goals}-{away_goals}{suffix}",
            period=REGULATION_PERIODS,
            sortkey=f"{REGULATION_PERIODS}-{PERIOD_SECONDS // 60:02d}:00",
        )
    else:
        row = build_scheduled_game_row(
            game_id=game.get("GameID"),
            home_team=home_team,
            away_team=away_team,
            game_date=game_date,
            game_start_time=game_start_time,
            attendance=attendance,
            game_status=_game_status(game),
        )
    return _attach_game_metadata(row, game, metadata)


def build_rows_from_game(game: dict[str, Any], normalize_team, auth: WfcAuth | None) -> list[dict[str, Any]]:
    rows = [build_game_row(game, normalize_team)]
    game_id = _parse_int(game.get("GameID"))
    if auth is None or game_id is None or not _is_finished(game):
        return rows
    try:
        overview = _fetch_game_overview(game_id, auth)
    except requests.RequestException as exc:
        print(f"[WARN] Champions Cup overview failed for game {game_id}: {exc}")
        return rows
    blurbs = overview.get("Blurbs") or []
    if not isinstance(blurbs, list):
        return rows
    metadata = stage_metadata(game)
    player_lookup = _build_player_lookup(overview)
    for blurb in blurbs:
        row = _overview_event_to_row(
            blurb,
            game,
            metadata,
            player_lookup,
            normalize_team=normalize_team,
            parse_game_time=parse_game_time,
            period_seconds=PERIOD_SECONDS,
        )
        if row is not None:
            rows.append(row)
    return rows


def fetch_competition_games(league_organizer_id: int, auth: WfcAuth, division: str | None) -> list[dict[str, Any]]:
    """Played games plus the published schedule, deduplicated and limited to one division."""
    games: dict[int, dict[str, Any]] = {}
    for endpoint in ("getpreviousleagueorganizergames", "getcomingleagueorganizergames"):
        for game in fetch_previous_league_organizer_games(league_organizer_id, auth=auth, endpoint=endpoint):
            game_id = _parse_int(game.get("GameID"))
            if game_id is None:
                continue
            # A game can move from "coming" to "previous" between the two calls; keep the finished copy.
            if game_id in games and _is_finished(games[game_id]) and not _is_finished(game):
                continue
            games[game_id] = game
    return [game for game in games.values() if division is None or game_division(game) == division]


def scrape_competition(
    league_organizer_id: int,
    output_path: str,
    *,
    division: str | None = None,
    team_aliases: dict[str, str] | None = None,
) -> pd.DataFrame:
    auth = _load_auth_from_env()
    if auth is None:
        raise RuntimeError(
            "The Champions Cup feed needs IFF_API_ACCESS_TOKEN and IFF_API_REFRESH_TOKEN (IFF app login)."
        )
    normalize_team = make_team_normalizer(team_aliases)
    games = fetch_competition_games(league_organizer_id, auth, division)
    rows = [row for game in games for row in build_rows_from_game(game, normalize_team, auth)]
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
    frame = pd.DataFrame(rows)
    frame.to_csv(out, index=False)
    return frame
