"""Read the Suomen Cup from the public Torneopal result service (tulospalvelu.salibandy.fi).

The Finnish federation publishes the cup only there, and its REST API
(salibandy-api.torneopal.net) answers scripts with a Cloudflare 403. The result
service itself is a single-page app that loads the same JSON in a normal browser,
so, like ``scrape_saisonmanager_web``, a headless Chrome opens the public pages and
this module reads the responses the page requests (``getMatches`` for a category,
``getMatch`` for a game). robots.txt only disallows ``/person/``; load is kept low:
one page per game, a pause between pages, finished games are cached on disk and
re-read only within a few days after the game.

Torneopal event codes used: ``maali`` (goal, with ``syotto`` assists linked by
``connected_event_id``) and ``2min`` and friends (penalties). Penalty shootout
attempts (``rpkmaali``/``rpkohi``) are skipped: the shootout winner is the period 5
``maali`` event, as in the other backends.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from tqdm import tqdm

from src.competitions import STAGE_ELIMINATION, STAGE_GROUP, cup_columns
from src.scheduled_games import build_result_game_row, build_scheduled_game_row

WEB_BASE = "https://tulospalvelu.salibandy.fi"
USER_AGENT = "FloorballStats/1.0 (+https://stats.floorballconnect.com)"
DEFAULT_CACHE_DIR = Path(os.environ.get("TORNEOPAL_WEB_CACHE", ".cache/torneopal"))
HELSINKI_TZ = ZoneInfo("Europe/Helsinki")
CRAWL_DELAY_SECONDS = 3.0
# Results may still be corrected shortly after a game; re-read recent games.
REFRESH_WINDOW_DAYS = 3

PLACEHOLDER_TEAM = re.compile(r"^(voittaja|häviäjä)\b", re.IGNORECASE)
GOAL_CODE = "maali"
ASSIST_CODE = "syotto"
# Penalty event codes -> the penalty_type vocabulary of the other backends.
PENALTY_CODES = {
    "2min": "penalty_2",
    "2+2min": "penalty_2and2",
    "5min": "penalty_5",
    "10min": "penalty_10",
}
_PENALTY_LIKE = re.compile(r"^\d+(\+\d+)?min$")


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def is_placeholder_team(name: Any) -> bool:
    """Undrawn bracket slots are named "Voittaja ottelusta ... (3204)"."""
    return not _text(name) or bool(PLACEHOLDER_TEAM.match(_text(name)))


def _stage_columns(listed: dict[str, Any]) -> dict[str, Any]:
    """Cup markers of a game: knockout rounds keep their round name, regional groups their group."""
    group_name = _text(listed.get("group_name"))
    category_name = _text(listed.get("category_name"))
    is_group = _text(listed.get("group_type")) == "group_stage"
    label = _text(listed.get("round_name")) if group_name == category_name else group_name
    return cup_columns(
        category_name or None,
        stage_type=STAGE_GROUP if is_group else STAGE_ELIMINATION,
        stage_label=label or None,
        group=group_name if is_group else None,
    )


def _game_fields(listed: dict[str, Any], detail: dict[str, Any] | None) -> dict[str, Any]:
    source = {**listed, **(detail or {})}
    attendance = _int_or_none(source.get("attendance")) or _int_or_none(source.get("report_attendance"))
    home_goals, away_goals = _int_or_none(source.get("fs_A")), _int_or_none(source.get("fs_B"))
    result = f"{home_goals}:{away_goals}" if home_goals is not None and away_goals is not None else None
    return {
        "game_id": int(listed["match_id"]),
        "home": _text(listed.get("team_A_name")),
        "away": _text(listed.get("team_B_name")),
        "game_date": _text(listed.get("date")) or None,
        "game_start_time": _text(listed.get("time"))[:5] or None,
        "attendance": attendance,
        "result_string": result,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "venue": _text(source.get("venue_name")) or None,
    }


def _player_names(detail: dict[str, Any]) -> dict[str, str]:
    """player_id -> "First Last" (events carry "Last First")."""
    names: dict[str, str] = {}
    for entry in detail.get("lineups") or []:
        first, last = _text(entry.get("first_name")), _text(entry.get("last_name"))
        if entry.get("player_id") and (first or last):
            names[_text(entry["player_id"])] = f"{first} {last}".strip()
    return names


def _event_clock(event: dict[str, Any]) -> tuple[int, str]:
    """(period, "mm:ss" inside the period); ``time_sec`` counts seconds into the period."""
    period = _int_or_none(event.get("period")) or 0
    seconds = _int_or_none(event.get("time_sec")) or 0
    return period, f"{seconds // 60:02d}:{seconds % 60:02d}"


def match_rows(listed: dict[str, Any], detail: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Event rows of one cup game (goals, assists, penalties), or one result/scheduled row."""
    fields = _game_fields(listed, detail)
    marker = _stage_columns(listed)
    status = _text(listed.get("status"))
    base = {
        "game_id": fields["game_id"],
        "home_team": fields["home"],
        "away_team": fields["away"],
        "game_date": fields["game_date"],
        "game_start_time": fields["game_start_time"],
        "attendance": fields["attendance"],
    }
    if status != "Played":
        # Planned/fixture games with real teams and a date; forfeits, undrawn slots and
        # games without a date are not shown (the page would invent a date).
        return [
            {**build_scheduled_game_row(
                game_id=fields["game_id"], home_team=fields["home"], away_team=fields["away"],
                game_date=fields["game_date"], game_start_time=fields["game_start_time"], attendance=None,
            ), "venue": fields["venue"], **marker}
        ] if status in {"Planned", "Fixture"} and fields["game_date"] else []

    events = (detail or {}).get("events") or []
    names = _player_names(detail or {})
    team_names = {"A": fields["home"], "B": fields["away"]}
    assists: dict[str, str | None] = {}
    for event in events:
        if event.get("code") == ASSIST_CODE and _text(event.get("connected_event_id")) not in {"", "0"}:
            assists[_text(event["connected_event_id"])] = names.get(_text(event.get("player_id"))) or _text(event.get("player_name")) or None

    rows: list[dict[str, Any]] = []
    for event in events:
        code = _text(event.get("code"))
        side = _text(event.get("team"))
        if side not in team_names:
            continue
        if code == GOAL_CODE:
            event_type, penalty_type = "goal", None
        elif code in PENALTY_CODES:
            event_type, penalty_type = "penalty", PENALTY_CODES[code]
        else:
            continue
        period, clock = _event_clock(event)
        scorer = names.get(_text(event.get("player_id"))) or _text(event.get("player_name")) or None
        rows.append({
            "event_type": event_type,
            "event_team": team_names[side],
            "period": period,
            "sortkey": f"{period}-{clock}",
            "game_id": fields["game_id"],
            "home_team_name": fields["home"],
            "away_team_name": fields["away"],
            "home_goals": _int_or_none(event.get("s_A")),
            "guest_goals": _int_or_none(event.get("s_B")),
            "goal_type": "goal" if event_type == "goal" else None,
            "penalty_type": penalty_type,
            "game_date": fields["game_date"],
            "game_start_time": fields["game_start_time"],
            "attendance": fields["attendance"],
            "game_status": "Played",
            "ingame_status": None,
            "result_string": fields["result_string"],
            "scorer_name": scorer if event_type == "goal" else None,
            "assist_name": assists.get(_text(event.get("event_id"))) if event_type == "goal" else None,
            "scorer_number": _int_or_none(event.get("shirt_number")) if event_type == "goal" else None,
            "assist_number": None,
            "penalty_player_name": scorer if event_type == "penalty" else None,
            "venue": fields["venue"],
            **marker,
        })
    if not any(row["event_type"] == "goal" for row in rows):
        # Lower-level games without scorer tracking: keep the final score.
        if fields["home_goals"] is None or fields["away_goals"] is None:
            return []
        return [{
            **build_result_game_row(
                game_id=fields["game_id"], home_team=fields["home"], away_team=fields["away"],
                game_date=fields["game_date"], game_start_time=fields["game_start_time"],
                home_goals=fields["home_goals"], away_goals=fields["away_goals"], attendance=fields["attendance"],
                game_status="Played", result_string=fields["result_string"],
            ), "venue": fields["venue"], **marker,
        }]
    return rows


class TorneopalWebClient:
    """Capture the JSON the Torneopal result service requests while it renders a page."""

    def __init__(
        self,
        cache_dir: Path | str = DEFAULT_CACHE_DIR,
        delay_seconds: float = CRAWL_DELAY_SECONDS,
        today: date | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.delay_seconds = delay_seconds
        self.today = today or datetime.now(HELSINKI_TZ).date()
        self._playwright = None
        self._browser = None
        self._page = None
        self._last_load = 0.0

    def __enter__(self) -> "TorneopalWebClient":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._browser = self._playwright = self._page = None

    def _open(self):
        if self._page is None:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
            try:
                self._browser = self._playwright.chromium.launch(headless=True, channel="chrome")
            except Exception:
                self._browser = self._playwright.chromium.launch(headless=True)
            self._page = self._browser.new_page(user_agent=USER_AGENT)
            self._page.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in {"image", "media", "font"}
                else route.continue_(),
            )
        return self._page

    def _capture(self, url: str, call: str, **params: object) -> dict[str, Any]:
        """Open ``url`` and return the JSON of the page's own ``call`` request."""
        page = self._open()
        wait = self.delay_seconds - (time.monotonic() - self._last_load)
        if wait > 0:
            time.sleep(wait)

        def wanted(response) -> bool:
            return f"/taso/rest/{call}?" in response.url and all(f"{key}={value}" in response.url for key, value in params.items())

        with page.expect_response(wanted, timeout=60000) as captured:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        self._last_load = time.monotonic()
        return captured.value.json()

    def fetch_matches(self, category_id: int, competition_id: str) -> list[dict[str, Any]]:
        payload = self._capture(
            f"{WEB_BASE}/category/{category_id}!{competition_id}/tables",
            "getMatches", competition_id=competition_id, category_id=category_id,
        )
        return list(payload.get("matches") or [])

    def _cache_path(self, match_id: str) -> Path:
        return self.cache_dir / f"match-{match_id}.json"

    def fetch_match(self, match_id: str, game_date: str | None) -> dict[str, Any]:
        cache_path = self._cache_path(match_id)
        if cache_path.exists() and game_date:
            if date.fromisoformat(game_date) < self.today - timedelta(days=REFRESH_WINDOW_DAYS):
                return json.loads(cache_path.read_text(encoding="utf-8"))
        payload = self._capture(f"{WEB_BASE}/match/{match_id}", "getMatch", match_id=match_id)
        match = payload.get("match") or {}
        if _text(match.get("status")) == "Played":
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(match, ensure_ascii=False), encoding="utf-8")
        return match


def scrape_cup(
    category_id: int,
    output_path: str,
    competition_id: str = "sb2026",
    client: TorneopalWebClient | None = None,
) -> pd.DataFrame:
    """Events of every real game of a Torneopal cup category (Suomen Cup miehet 366, naiset 365)."""
    owned = client is None
    web = client or TorneopalWebClient()
    try:
        listed = [m for m in web.fetch_matches(category_id, competition_id)
                  if not is_placeholder_team(m.get("team_A_name")) and not is_placeholder_team(m.get("team_B_name"))]
        rows: list[dict[str, Any]] = []
        for game in tqdm(listed, desc=f"suomen cup {category_id}"):
            detail = web.fetch_match(game["match_id"], game.get("date")) if _text(game.get("status")) == "Played" else None
            rows.extend(match_rows(game, detail))
    finally:
        if owned:
            web.close()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(out, index=False)
    return frame
