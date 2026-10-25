"""Read German league data from the public saisonmanager.de pages.

Fallback for when no SAISONMANAGER_API_KEY is configured: the pages are
rendered with a headless Chrome and parsed into the same JSON shape the
Saisonmanager API returns (``leagues/<id>/schedule.json`` and
``games/<id>``), so ``src.scrape.scrape_events`` and the lineup-based player
stats work unchanged.

saisonmanager.de/robots.txt explicitly allows schedule, game and team pages
(not /spieler) and asks for a 10 s crawl delay. Load is kept low on purpose:
one page render per finished game (cached on disk and never fetched again once
it is older than a few days), the crawl delay between renders, images/fonts are
not downloaded, and unplayed games come straight from the schedule page.
"""
from __future__ import annotations

import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

WEB_BASE = "https://saisonmanager.de"
USER_AGENT = "FloorballStats/1.0 (+https://stats.floorballconnect.com)"
DEFAULT_CACHE_DIR = Path(os.environ.get("SAISONMANAGER_WEB_CACHE", ".cache/saisonmanager"))
BERLIN_TZ = ZoneInfo("Europe/Berlin")
# Results may still be corrected shortly after a game; re-read recent games.
REFRESH_WINDOW_DAYS = 3
# "Crawl-delay: 10" in https://saisonmanager.de/robots.txt
CRAWL_DELAY_SECONDS = 10.0

SECTION_PERIODS = {
    "1. drittel": 1,
    "2. drittel": 2,
    "3. drittel": 3,
    "verlängerung": 4,
    "penalty-schießen": 5,
}

_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_CLOCK_RE = re.compile(r"(\d{1,2}):(\d{2})\s*Uhr")
_SCORE_RE = re.compile(r"^(\d+)\s*:\s*(\d+)$")
_EVENT_TIME_RE = re.compile(r"^(\d{1,3})'\s*(\d{1,2})\"$")
_PLAYER_HREF_RE = re.compile(r"/spieler/(\d+)")
_GAME_HREF_RE = re.compile(r"/spiel/(\d+)")


def _text(node: Any) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node is not None else ""


def _parse_date(text: str) -> str | None:
    match = _DATE_RE.search(text or "")
    if not match:
        return None
    day, month, year = match.groups()
    return f"{year}-{month}-{day}"


def _parse_clock(text: str) -> str | None:
    match = _CLOCK_RE.search(text or "")
    return f"{int(match.group(1)):02d}:{match.group(2)}" if match else None


def _player_id(node: Any) -> str | None:
    anchor = node.find("a", href=_PLAYER_HREF_RE) if node is not None else None
    if anchor is None:
        return None
    return _PLAYER_HREF_RE.search(anchor["href"]).group(1)


def parse_schedule_html(html: str) -> list[dict[str, Any]]:
    """Parse the ``/fd/<league>/all-matches`` page."""
    soup = BeautifulSoup(html, "html.parser")
    games: dict[int, dict[str, Any]] = {}
    for anchor in soup.select("a[href*='/spiel/']"):
        cells = anchor.find_all("div", recursive=False)
        if len(cells) < 7 or "Spieltag" not in _text(cells[6]):
            continue  # sidebar teasers, not schedule rows
        game_id = int(_GAME_HREF_RE.search(anchor["href"]).group(1))
        when = _text(cells[0])
        result_text = _text(cells[3])
        score = re.match(r"(\d+)\s*:\s*(\d+)(.*)$", result_text)
        played = bool(score) and "Uhr" not in result_text
        matchday = re.search(r"Spieltag\s+(\d+)", _text(cells[6]))
        games[game_id] = {
            "game_id": game_id,
            "date": _parse_date(when),
            "start_time": _parse_clock(when),
            "home_team_name": _text(cells[1]),
            "guest_team_name": _text(cells[5]),
            "result_string": " ".join(result_text.split()) if played else None,
            "played": played,
            "game_day": int(matchday.group(1)) if matchday else None,
        }
    return [games[key] for key in sorted(games)]


def _penalty_type(label: str) -> tuple[str, str]:
    text = label.replace("Strafe", "", 1).strip()
    if "2+2" in text:
        return "penalty_2and2", "2+2"
    if "t. MS" in text or "techn" in text.lower():
        return "penalty_ms_tech", "t. MS"
    if "MS" in text or "match" in text.lower():
        return "penalty_ms_full", "MS"
    if re.search(r"\b10\b", text):
        return "penalty_10", "10'"
    return "penalty_2", "2'"


def _parse_lineup(container: Any) -> list[dict[str, Any]]:
    players: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in container.select("fb-player-lineup-item"):
        if item.find_parent("fb-team-starting-players") is not None:
            continue
        cells = item.find("div").find_all("div", recursive=False)
        player_id = _player_id(item)
        name = _text(item.find("a", href=_PLAYER_HREF_RE))
        if not player_id or not name or player_id in seen:
            continue
        seen.add(player_id)
        number = next((_text(cell) for cell in cells if _text(cell).isdigit()), None)
        position = _text(cells[-2]) if len(cells) >= 2 else ""
        players.append(
            {
                "player_id": int(player_id),
                "trikot_number": number,
                # The pages only show full names; scrape.py joins first + last name.
                "player_firstname": "",
                "player_name": name,
                "position": position,
            }
        )
    return players


def _parse_history_item(item: Any, home: str, guest: str) -> dict[str, Any] | None:
    grid = item.find("div")
    if grid is None:
        return None
    cells = grid.find_all("div", recursive=False)
    side = None
    for img in grid.find_all("img"):
        alt = (img.get("alt") or "").strip()
        if alt == home:
            side = "home"
        elif alt == guest:
            side = "guest"
    label = score = clock = None
    player_cell = assist_cell = None
    notes: list[str] = []
    for cell in cells:
        text = _text(cell)
        if not text:
            continue
        if _EVENT_TIME_RE.match(text):
            clock = text
        elif _SCORE_RE.match(text):
            score = text
        elif text.startswith("Vorl."):
            assist_cell = cell
        elif text == "Tor" or text.startswith("Strafe") or text == "Auszeit":
            label = label or text
        elif player_cell is None and cell.find("a", href=_PLAYER_HREF_RE) is not None:
            player_cell = cell
        else:
            notes.append(text)
    if side is None or label is None or clock is None:
        return None
    minute, second = (int(part) for part in _EVENT_TIME_RE.match(clock).groups())
    event: dict[str, Any] = {
        "event_team": side,
        "minute": minute,
        "second": second,
        "player_id": _player_id(player_cell),
        "player_name_hint": _text(player_cell.find("a", href=_PLAYER_HREF_RE)) if player_cell is not None else None,
        "assist_id": _player_id(assist_cell),
        "assist_name_hint": _text(assist_cell.find("a", href=_PLAYER_HREF_RE)) if assist_cell is not None else None,
        "note": " ".join(notes) or None,
    }
    if label == "Tor":
        event["event_type"] = "goal"
        if score:
            home_goals, guest_goals = (int(part) for part in _SCORE_RE.match(score).groups())
            event["home_goals"], event["guest_goals"] = home_goals, guest_goals
    elif label.startswith("Strafe"):
        event["event_type"] = "penalty"
        event["penalty_type"], event["penalty_type_string"] = _penalty_type(label)
        event["penalty_reason_string"] = event["note"]
    else:
        event["event_type"] = "timeout"
    return event


def parse_game_html(html: str, game_id: int) -> dict[str, Any]:
    """Parse a ``/fd/<league>/spiel/<id>`` page into the API ``games/<id>`` shape."""
    soup = BeautifulSoup(html, "html.parser")
    header = soup.select_one("fb-match-header")
    if header is None:
        raise ValueError(f"Saisonmanager page for game {game_id} has no match header (not rendered?)")
    team_imgs = [img for img in header.find_all("img") if img.get("alt")]
    home = team_imgs[0]["alt"].strip()
    guest = team_imgs[-1]["alt"].strip()
    when = _text(header.find("span"))
    score_line = [_text(p) for p in header.select("div > p")]
    final_score = next((text for text in score_line if _SCORE_RE.match(text)), None)
    decision = next((text for text in score_line if text.startswith("n.")), None)

    info: dict[str, str] = {}
    for row in soup.select("fb-match-info li"):
        spans = row.find_all("span", recursive=False)
        if len(spans) >= 2:
            info[_text(spans[0])] = _text(spans[1])

    lineups = soup.select("fb-team-lineup")
    players = {
        "home": _parse_lineup(lineups[0]) if len(lineups) > 0 else [],
        "guest": _parse_lineup(lineups[1]) if len(lineups) > 1 else [],
    }
    numbers = {
        side: {str(player["player_id"]): player["trikot_number"] for player in side_players}
        for side, side_players in players.items()
    }

    events: list[dict[str, Any]] = []
    history = soup.select_one("fb-match-history")
    period = 0
    home_goals = guest_goals = 0
    if history is not None:
        for node in history.select("fb-match-history-item, div.font-bold"):
            if node.name != "fb-match-history-item":
                if node.find_parent("fb-match-history-item") is None:
                    period = SECTION_PERIODS.get(_text(node).lower(), period)
                continue
            event = _parse_history_item(node, home, guest)
            if event is None:
                continue
            if event["event_type"] == "goal":
                home_goals = event.get("home_goals", home_goals)
                guest_goals = event.get("guest_goals", guest_goals)
                note = event["note"] or ""
                if "Eigentor" in note:
                    event["goal_type"], event["goal_type_string"] = "own_goal", "Eigentor"
                elif period == 5 or "Strafschuss" in note:
                    event["goal_type"], event["goal_type_string"] = "penalty_shot", "Strafschuss"
                else:
                    event["goal_type"], event["goal_type_string"] = "regular", "Tor"
            side_numbers = numbers.get(event["event_team"], {})
            minute, second = event.pop("minute"), event.pop("second")
            events.append(
                {
                    "event_id": len(events) + 1,
                    "event_type": event["event_type"],
                    "event_team": event["event_team"],
                    "period": period,
                    # The API leaves the score empty on timeouts.
                    "home_goals": None if event["event_type"] == "timeout" else home_goals,
                    "guest_goals": None if event["event_type"] == "timeout" else guest_goals,
                    "time": f"{minute}:{second:02d}",
                    "sortkey": f"{period}-{minute:02d}:{second:02d}",
                    "number": side_numbers.get(event["player_id"] or ""),
                    "assist": side_numbers.get(event["assist_id"] or ""),
                    "goal_type": event.get("goal_type"),
                    "goal_type_string": event.get("goal_type_string"),
                    "penalty_type": event.get("penalty_type"),
                    "penalty_type_string": event.get("penalty_type_string"),
                    "penalty_reason_string": event.get("penalty_reason_string"),
                    "player_name_hint": event["player_name_hint"],
                    "assist_name_hint": event["assist_name_hint"],
                }
            )

    if decision and "PS" in decision.upper():
        ingame_status = "penalty_shots"
    elif decision:
        ingame_status = "extratime"
    else:
        ingame_status = "period3" if final_score else None
    attendance = re.sub(r"\D", "", info.get("Zuschauerzahl", ""))
    return {
        "game_id": game_id,
        "home_team_name": home,
        "guest_team_name": guest,
        "date": _parse_date(info.get("Datum", "")) or _parse_date(when),
        "start_time": _parse_clock(info.get("Spielbeginn", "")) or _parse_clock(when),
        "audience": int(attendance) if attendance else None,
        "game_status": "match_record_closed" if final_score else "pregame",
        "ingame_status": ingame_status,
        "result_string": " ".join(part for part in [final_score, decision] if part) or None,
        "venue": info.get("Austragungshalle"),
        "venue_address": info.get("Austragungsort"),
        "players": players,
        "events": events,
    }


def trim_game_html(html: str) -> str:
    """Keep only the parts ``parse_game_html`` reads (cache size ~16 KB per game)."""
    soup = BeautifulSoup(html, "html.parser")
    keep = [
        soup.select_one("fb-match-header"),
        soup.select_one("fb-match-history"),
        soup.select_one("fb-match-info"),
        *soup.select("fb-team-lineup"),
    ]
    for node in keep:
        for tag in [node, *node.find_all(True)] if node is not None else []:
            for attr in [name for name in tag.attrs if name.startswith("_ng") or name == "style"]:
                del tag[attr]
            if tag.name == "img":
                tag["src"] = ""
    return "<html><body><main>" + "".join(str(node) for node in keep if node is not None) + "</main></body></html>"


def scheduled_game_payload(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "game_id": entry["game_id"],
        "home_team_name": entry["home_team_name"],
        "guest_team_name": entry["guest_team_name"],
        "date": entry["date"],
        "start_time": entry["start_time"],
        "audience": None,
        "game_status": "Scheduled",
        "ingame_status": None,
        "result_string": None,
        "players": {"home": [], "guest": []},
        "events": [],
    }


class SaisonmanagerWebClient:
    """Serve Saisonmanager API paths from the public web pages."""

    def __init__(
        self,
        league_id: int | None = None,
        cache_dir: Path | str = DEFAULT_CACHE_DIR,
        delay_seconds: float = CRAWL_DELAY_SECONDS,
        cache_only: bool = False,
        today: date | None = None,
    ) -> None:
        self.league_id = league_id
        self.cache_dir = Path(cache_dir)
        self.delay_seconds = delay_seconds
        self.cache_only = cache_only
        self.today = today or datetime.now(BERLIN_TZ).date()
        self.schedule: dict[int, dict[str, Any]] = {}
        self._playwright = None
        self._browser = None
        self._page = None
        self._last_render = 0.0

    def __enter__(self) -> "SaisonmanagerWebClient":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._browser = self._playwright = self._page = None

    def _render(self, url: str, ready_selector: str) -> str:
        if self.cache_only:
            raise LookupError(f"{url} is not cached and rendering is disabled")
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
        wait = self.delay_seconds - (time.monotonic() - self._last_render)
        if wait > 0:
            time.sleep(wait)
        self._page.goto(url, wait_until="networkidle", timeout=60000)
        self._page.wait_for_selector(ready_selector, timeout=30000)
        self._last_render = time.monotonic()
        return self._page.content()

    def _cache_path(self, game_id: int) -> Path:
        # Raw (trimmed) HTML is cached, so parser fixes also apply to cached games.
        return self.cache_dir / f"game-{game_id}.html"

    def get_json(self, path: str) -> Any:
        schedule_match = re.fullmatch(r"leagues/(\d+)/schedule\.json", path)
        if schedule_match:
            self.league_id = int(schedule_match.group(1))
            html = self._render(f"{WEB_BASE}/fd/{self.league_id}/all-matches", "a[href*='/spiel/']")
            entries = parse_schedule_html(html)
            if not entries:
                raise ValueError(f"No games found on the Saisonmanager schedule page for league {self.league_id}")
            self.schedule = {entry["game_id"]: entry for entry in entries}
            return entries
        game_match = re.fullmatch(r"games/(\d+)", path)
        if game_match:
            return self.get_game(int(game_match.group(1)))
        raise ValueError(f"Unsupported Saisonmanager path for web fallback: {path}")

    def get_game(self, game_id: int) -> dict[str, Any]:
        entry = self.schedule.get(game_id)
        if entry is not None and not entry["played"]:
            return scheduled_game_payload(entry)
        cache_path = self._cache_path(game_id)
        if cache_path.exists():
            cached = parse_game_html(cache_path.read_text(encoding="utf-8"), game_id)
            game_date = cached.get("date")
            is_settled = game_date and date.fromisoformat(game_date) < self.today - timedelta(days=REFRESH_WINDOW_DAYS)
            if is_settled or self.cache_only:
                return cached
        if not self.league_id:
            raise LookupError(f"Game {game_id} is not cached and no league_id is known to build its URL")
        html = trim_game_html(self._render(f"{WEB_BASE}/fd/{self.league_id}/spiel/{game_id}", "fb-match-info"))
        game = parse_game_html(html, game_id)
        if game["game_status"] == "match_record_closed":
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(html, encoding="utf-8")
        return game
