import argparse
import re
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from src.scheduled_games import build_scheduled_game_row


BASE_URL = "https://www.swissunihockey.ch"
RENDER_URL = f"{BASE_URL}/renderengine/load_view.php"


def _get_with_retries(url: str, *, params: dict[str, str] | None = None, timeout: int = 30, attempts: int = 3) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < attempts:
                time.sleep(0.8 * attempt)
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Failed to fetch {url}")


@dataclass
class GameDetails:
    home_team: str
    away_team: str
    game_date: str | None
    game_start_time: str | None
    result_string: str | None
    goals_home: int | None
    goals_away: int | None
    attendance: int | None = None
    venue: str | None = None
    venue_address: str | None = None
    header_text: str | None = None


def _fetch_block(game_id: int, block_type: str, locale: str = "de-CH", is_home: bool = True) -> str:
    params = {
        "view": "short",
        "game_id": str(game_id),
        "is_home": "1" if is_home else "0",
        "block_type": block_type,
        "ID_Block": "SU_2886",
        "locale": locale,
    }
    response = _get_with_retries(RENDER_URL, params=params, timeout=45, attempts=4)
    return response.text


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip().lower()
    today = datetime.now()
    if raw == "heute":
        return today.strftime("%Y-%m-%d")
    if raw == "gestern":
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    if raw == "morgen":
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    # Swiss format dd.mm.yyyy
    match = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", raw)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    return value


def _parse_game_details(html: str) -> GameDetails:
    soup = BeautifulSoup(html, "html.parser")
    header = soup.select_one("div.su-header.su-basictable")
    header_text = header.get_text(" ", strip=True) if header else None

    def _text_or_none(node: Any) -> str | None:
        if not node:
            return None
        value = node.get_text(" ", strip=True)
        return value or None

    # Newer swissunihockey markup exposes details via CSS classes.
    home_team = _text_or_none(soup.select_one(".su-value-teams-verein-name:nth-of-type(1) a"))
    away_team = _text_or_none(soup.select_one(".su-col04:last-of-type .su-value-teams-verein-name a"))
    result_raw = _text_or_none(soup.select_one(".su-value-result"))
    game_date = _normalize_date(_text_or_none(soup.select_one(".su-value-date")))
    game_start_time = _text_or_none(soup.select_one(".su-value-time"))
    venue = _text_or_none(soup.select_one(".su-value-location"))
    spectators_raw = _text_or_none(soup.select_one(".su-value-spectators"))

    # Legacy fallback: table data-key format.
    rows = soup.select("table.su-result tr")
    data: dict[str, str] = {}
    for row in rows:
        cells = row.find_all("td")
        if len(cells) != 2:
            continue
        key_span = cells[0].find("span", attrs={"data-key": True})
        if not key_span:
            continue
        key = key_span.get("data-key")
        value = cells[1].get_text(" ", strip=True)
        if key:
            data[key] = value

    if not home_team:
        home_team = data.get("home_name") or ""
    if not away_team:
        away_team = data.get("away_name") or ""
    if not result_raw:
        result_raw = data.get("result")
    if not game_date:
        game_date = _normalize_date(data.get("date"))
    if not game_start_time:
        game_start_time = data.get("time")
    if not spectators_raw:
        spectators_raw = data.get("spectators")
    if not venue:
        venue = data.get("venue") or data.get("location") or data.get("place")

    goals_home = None
    goals_away = None
    if result_raw and ":" in result_raw:
        score = result_raw.split("(", 1)[0].strip()
        match = re.match(r"(?P<h>\d+)\s*:\s*(?P<a>\d+)", score)
        if match:
            goals_home = int(match.group("h"))
            goals_away = int(match.group("a"))
    attendance = int(spectators_raw) if spectators_raw and str(spectators_raw).isdigit() else None

    return GameDetails(
        home_team=home_team,
        away_team=away_team,
        game_date=game_date,
        game_start_time=game_start_time,
        result_string=result_raw,
        goals_home=goals_home,
        goals_away=goals_away,
        attendance=attendance,
        venue=venue,
        venue_address=None,
        header_text=header_text,
    )


def _event_period(minute: int) -> tuple[int, int]:
    if minute >= 60:
        return 4, minute - 60
    return minute // 20 + 1, minute % 20


def _penalty_type(event_text: str) -> str:
    text = event_text.lower()
    if "2+2" in text:
        return "penalty_2and2"
    if "10" in text and "strafe" in text:
        return "penalty_10"
    if "matchstrafe" in text or "spieldauerdisziplinarstrafe" in text:
        return "penalty_ms_full"
    return "penalty_2"


def _goal_type(event_text: str) -> str:
    text = event_text.lower()
    if "penaltyschuss" in text or "penaltyschiessen" in text:
        return "penalty_shot"
    return "goal"


def _parse_player_details(player_text: str | None) -> tuple[str | None, str | None]:
    if not player_text:
        return None, None
    cleaned = " ".join(player_text.split())
    if not cleaned:
        return None, None
    assist_match = re.search(r"(?:assist|vorlage)\s*[:\-]?\s*(.+)$", cleaned, re.I)
    if assist_match:
        scorer_name = cleaned[:assist_match.start()].strip(" ,;()-")
        assist_name = assist_match.group(1).strip(" ,;()-")
        return scorer_name or None, assist_name or None
    match = re.match(r"(?P<scorer>.+?)(?:\s*\((?P<assist>[^)]+)\))?$", cleaned)
    if not match:
        return cleaned, None
    return (match.group("scorer") or "").strip() or None, (match.group("assist") or "").strip() or None


def _normalize_person_name(value: str | None) -> str | None:
    cleaned = " ".join(str(value or "").split()).strip()
    if not cleaned:
        return None
    if "," in cleaned:
        last_name, first_name = [part.strip() for part in cleaned.split(",", 1)]
        if first_name and last_name:
            cleaned = f"{first_name} {last_name}"
    tokens = [token for token in re.split(r"\s+", cleaned) if token]
    normalized_tokens: list[str] = []
    for token in tokens:
        if len(token) <= 1:
            normalized_tokens.append(token)
            continue
        if token.endswith(".") and len(token) <= 3:
            normalized_tokens.append(token.upper())
            continue
        if token.isupper() or token.islower():
            normalized_tokens.append(token[0].upper() + token[1:].lower())
            continue
        normalized_tokens.append(token)
    normalized = " ".join(normalized_tokens).strip()
    return normalized or None


def _abbreviated_player_key(full_name: str) -> str | None:
    parts = [part for part in full_name.split(" ") if part]
    if len(parts) < 2:
        return None
    first = parts[0]
    last = parts[-1]
    if not first or not last:
        return None
    return f"{first[0].upper()}. {last}"


def _parse_players_block_names(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    names: list[str] = []
    seen: set[str] = set()
    for row in soup.select("table.su-result tbody tr"):
        player_cell = row.select_one("td:nth-of-type(3)")
        if player_cell is None:
            continue
        anchor = player_cell.select_one("a")
        player_name = (anchor or player_cell).get_text(" ", strip=True)
        normalized = _normalize_person_name(player_name)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(normalized)
    return names


def _build_player_name_lookup(game_id: int, details: GameDetails) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {details.home_team: {}, details.away_team: {}}
    try:
        home_html = _fetch_block(game_id, "players", is_home=True)
        away_html = _fetch_block(game_id, "players", is_home=False)
    except requests.RequestException:
        return lookup

    for team_name, html in [(details.home_team, home_html), (details.away_team, away_html)]:
        team_lookup = lookup.setdefault(team_name, {})
        for full_name in _parse_players_block_names(html):
            keys = {full_name.lower()}
            abbreviated = _abbreviated_player_key(full_name)
            if abbreviated:
                keys.add(abbreviated.lower())
                keys.add(abbreviated.replace(".", "").lower())
            for key in keys:
                team_lookup.setdefault(key, full_name)
    return lookup


def _resolve_player_name(name: str | None, team_name: str | None, lookup: dict[str, dict[str, str]]) -> str | None:
    normalized = _normalize_person_name(name)
    if not normalized:
        return None
    if not team_name:
        return normalized
    team_lookup = lookup.get(team_name) or {}
    return team_lookup.get(normalized.lower(), team_lookup.get(normalized.replace(".", "").lower(), normalized))


def _classify_phase(header_text: str | None) -> str:
    if not header_text:
        return "regular-season"
    text = header_text.lower()
    # Swiss phases can include multiple post-season tracks; keep them separate.
    if any(keyword in text for keyword in ["playout", "play-out", "play out"]):
        return "playouts"
    if any(keyword in text for keyword in ["playdown", "play-down", "play down"]):
        return "playdowns"
    playoff_keywords = [
        "playoff",
        "playoffs",
        "viertelfinal",
        "halbfinal",
        "final",
        "finale",
        "platzierungsspiel",
    ]
    if any(keyword in text for keyword in playoff_keywords):
        return "playoffs"
    return "regular-season"


def _needs_penalty_shootout_marker(result_string: str | None) -> bool:
    if not result_string:
        return False
    text = result_string.lower()
    return "n.p" in text or "penalty" in text


def _needs_overtime_marker(result_string: str | None) -> bool:
    if not result_string:
        return False
    text = result_string.lower()
    return "n.v" in text or "verlängerung" in text


def _parse_game_events(
    html: str,
    game_id: int,
    details: GameDetails,
    player_name_lookup: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table.su-result tbody tr")
    events: list[dict[str, Any]] = []
    name_lookup = player_name_lookup or {}

    for row in rows:
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        if len(cells) < 4:
            continue
        minute_raw, event_text, team_name, player_text = cells[:4]
        if not minute_raw or not event_text:
            continue
        if ":" not in minute_raw:
            continue

        try:
            minute_val, second_val = minute_raw.split(":", 1)
            minute = int(minute_val)
            second = int(second_val)
        except ValueError:
            continue

        period, minute_in_period = _event_period(minute)
        sortkey = f"{period}-{minute_in_period:02d}:{second:02d}"

        if event_text.startswith("Torschütze") and team_name:
            scorer_name, assist_name = _parse_player_details(player_text)
            scorer_name = _resolve_player_name(scorer_name, team_name, name_lookup)
            assist_name = _resolve_player_name(assist_name, team_name, name_lookup)
            events.append(
                {
                    "event_type": "goal",
                    "event_team": team_name or None,
                    "period": period,
                    "sortkey": sortkey,
                    "game_id": game_id,
                    "home_team_name": details.home_team,
                    "away_team_name": details.away_team,
                    "home_goals": 0,
                    "guest_goals": 0,
                    "goal_type": _goal_type(event_text),
                    "penalty_type": None,
                    "game_date": details.game_date,
                    "game_start_time": details.game_start_time,
                    "attendance": details.attendance,
                    "game_status": None,
                    "ingame_status": None,
                    "result_string": details.result_string,
                    "scorer_name": scorer_name,
                    "assist_name": assist_name,
                    "scorer_number": None,
                    "assist_number": None,
                    "penalty_player_name": None,
                }
            )
        elif "strafe" in event_text.lower() and team_name:
            penalty_player_name, _ = _parse_player_details(player_text)
            penalty_player_name = _resolve_player_name(penalty_player_name, team_name, name_lookup)
            events.append(
                {
                    "event_type": "penalty",
                    "event_team": team_name or None,
                    "period": period,
                    "sortkey": sortkey,
                    "game_id": game_id,
                    "home_team_name": details.home_team,
                    "away_team_name": details.away_team,
                    "home_goals": 0,
                    "guest_goals": 0,
                    "goal_type": None,
                    "penalty_type": _penalty_type(event_text),
                    "game_date": details.game_date,
                    "game_start_time": details.game_start_time,
                    "attendance": details.attendance,
                    "game_status": None,
                    "ingame_status": None,
                    "result_string": details.result_string,
                    "scorer_name": None,
                    "assist_name": None,
                    "scorer_number": None,
                    "assist_number": None,
                    "penalty_player_name": penalty_player_name,
                }
            )

    if _needs_penalty_shootout_marker(details.result_string):
        winner = None
        if details.goals_home is not None and details.goals_away is not None:
            winner = details.home_team if details.goals_home > details.goals_away else details.away_team
        if winner and not any(e.get("period") == 5 for e in events):
            events.append(
                {
                    "event_type": "goal",
                    "event_team": winner,
                    "period": 5,
                    "sortkey": "5-00:00",
                    "game_id": game_id,
                    "home_team_name": details.home_team,
                    "away_team_name": details.away_team,
                    "home_goals": details.goals_home,
                    "guest_goals": details.goals_away,
                    "goal_type": "penalty_shot",
                    "penalty_type": None,
                    "game_date": details.game_date,
                    "game_start_time": details.game_start_time,
                    "attendance": details.attendance,
                    "game_status": None,
                    "ingame_status": None,
                    "result_string": details.result_string,
                    "scorer_name": None,
                    "assist_name": None,
                    "scorer_number": None,
                    "assist_number": None,
                    "penalty_player_name": None,
                }
            )
    elif _needs_overtime_marker(details.result_string):
        winner = None
        if details.goals_home is not None and details.goals_away is not None:
            winner = details.home_team if details.goals_home > details.goals_away else details.away_team
        if winner and not any(e.get("period") == 4 for e in events):
            events.append(
                {
                    "event_type": "goal",
                    "event_team": winner,
                    "period": 4,
                    "sortkey": "4-00:00",
                    "game_id": game_id,
                    "home_team_name": details.home_team,
                    "away_team_name": details.away_team,
                    "home_goals": details.goals_home,
                    "guest_goals": details.goals_away,
                    "goal_type": "goal",
                    "penalty_type": None,
                    "game_date": details.game_date,
                    "game_start_time": details.game_start_time,
                    "attendance": details.attendance,
                    "game_status": None,
                    "ingame_status": None,
                    "result_string": details.result_string,
                    "scorer_name": None,
                    "assist_name": None,
                    "scorer_number": None,
                    "assist_number": None,
                    "penalty_player_name": None,
                }
            )

    def _sort_key(event: dict[str, Any]) -> tuple[int, int, int]:
        sortkey = str(event.get("sortkey", "1-00:00"))
        period_str, time_str = sortkey.split("-", 1) if "-" in sortkey else ("1", "00:00")
        minute_str, second_str = time_str.split(":", 1) if ":" in time_str else ("0", "0")
        try:
            period = int(period_str)
            minute = int(minute_str)
            second = int(second_str)
        except ValueError:
            return (99, 99, 99)
        return (period, minute, second)

    # Swiss feed contains final score on each event row. Rebuild in-game score progression.
    home_goals = 0
    away_goals = 0
    for event in sorted(events, key=_sort_key):
        if event.get("event_type") == "goal" and int(event.get("period", 0)) <= 4:
            if event.get("event_team") == details.home_team:
                home_goals += 1
            elif event.get("event_team") == details.away_team:
                away_goals += 1
        event["home_goals"] = home_goals
        event["guest_goals"] = away_goals

        # Keep shootout marker at final result when available.
        if int(event.get("period", 0)) == 5 and details.goals_home is not None and details.goals_away is not None:
            event["home_goals"] = details.goals_home
            event["guest_goals"] = details.goals_away

    for event in events:
        event["venue"] = details.venue
        event["venue_address"] = details.venue_address

    return events


def _extract_game_ids(html: str) -> set[int]:
    ids = set()
    for match in re.findall(r"game_id=(\d+)", html):
        ids.add(int(match))
    return ids


def fetch_game_ids_from_url(url: str) -> list[int]:
    response = _get_with_retries(url, timeout=45, attempts=3)
    return sorted(_extract_game_ids(response.text))


def fetch_game_ids_from_renderengine(
    league: int,
    season: int,
    game_class: int,
    mode: str = "list",
    locale: str = "de-CH",
) -> list[int]:
    params = {
        "view": "short",
        "block_type": "games",
        "league": str(league),
        "season": str(season),
        "game_class": str(game_class),
        "mode": mode,
        "locale": locale,
    }
    response = _get_with_retries(RENDER_URL, params=params, timeout=45, attempts=4)
    return sorted(_extract_game_ids(response.text))


def _extract_round_ids(html: str) -> set[int]:
    ids = set()
    for match in re.findall(r"round=(\d+)", html):
        ids.add(int(match))
    return ids


def _extract_round_label(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    label = soup.select_one("div.su-label")
    if not label:
        return None
    return label.get_text(" ", strip=True) or None


def fetch_game_ids_by_rounds(
    league: int,
    season: int,
    game_class: int,
    group: str | None = None,
    locale: str = "de-CH",
    start_round: int | None = None,
    phase_filter: str | None = None,
) -> list[int]:
    base_params = {
        "block_type": "games",
        "league": str(league),
        "season": str(season),
        "game_class": str(game_class),
        "view": "full",
        "mode": "list",
        "use_streaming_logos": "0",
        "locale": locale,
    }
    if group:
        base_params["group"] = group

    to_visit: list[int] = []
    seen_rounds: set[int] = set()
    game_ids: set[int] = set()

    def _should_include_round(html: str) -> bool:
        if not phase_filter:
            return True
        label = _extract_round_label(html)
        return _classify_phase(label) == phase_filter

    if start_round is not None:
        to_visit.append(start_round)
    else:
        response = _get_with_retries(RENDER_URL, params=base_params, timeout=45, attempts=4)
        html = response.text
        if _should_include_round(html):
            game_ids.update(_extract_game_ids(html))
        rounds = sorted(_extract_round_ids(html))
        to_visit.extend(rounds)

    while to_visit:
        round_id = to_visit.pop()
        if round_id in seen_rounds:
            continue
        seen_rounds.add(round_id)
        params = dict(base_params)
        params["round"] = str(round_id)
        response = _get_with_retries(RENDER_URL, params=params, timeout=45, attempts=4)
        html = response.text
        if _should_include_round(html):
            game_ids.update(_extract_game_ids(html))
        for nxt in _extract_round_ids(html):
            if nxt not in seen_rounds:
                to_visit.append(nxt)

    return sorted(game_ids)


def _load_game_ids_from_file(path: str) -> list[int]:
    ids = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for part in re.split(r"[\\s,]+", line):
            if part.isdigit():
                ids.add(int(part))
    return sorted(ids)


def scrape_games(game_ids: list[int], output_path: str, phase_filter: str | None = None) -> pd.DataFrame:
    all_events: list[dict[str, Any]] = []
    for game_id in tqdm(game_ids, desc="swiss games"):
        details_html = _fetch_block(game_id, "game_details")
        events_html = _fetch_block(game_id, "game_events")
        details = _parse_game_details(details_html)
        player_name_lookup = _build_player_name_lookup(game_id, details)
        if phase_filter:
            game_phase = _classify_phase(details.header_text)
            if phase_filter == "playoffs":
                # For Swiss post-season fetches, include only true playoffs and
                # exclude playdowns/playouts.
                if game_phase != "playoffs":
                    continue
            elif game_phase != phase_filter:
                continue
        events = _parse_game_events(events_html, game_id, details, player_name_lookup=player_name_lookup)
        if events:
            all_events.extend(events)
        else:
            all_events.append(
                build_scheduled_game_row(
                    game_id=game_id,
                    home_team=details.home_team,
                    away_team=details.away_team,
                    game_date=details.game_date,
                    game_start_time=details.game_start_time,
                    attendance=details.attendance,
                    game_status="Scheduled" if details.goals_home is None or details.goals_away is None else "Played",
                    result_string=details.result_string,
                )
            )
            all_events[-1]["venue"] = details.venue
            all_events[-1]["venue_address"] = details.venue_address

    if not all_events:
        raise ValueError("No Swiss games matched the requested phase filter.")

    df = pd.DataFrame(all_events)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return df


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game_id", type=int, default=None)
    parser.add_argument("--game_ids", type=str, default=None)
    parser.add_argument("--game_ids_file", type=str, default=None)
    parser.add_argument("--schedule_url", action="append", default=None)
    parser.add_argument("--league", type=int, default=None)
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--game_class", type=int, default=None)
    parser.add_argument("--mode", type=str, default="list")
    parser.add_argument("--group", type=str, default=None)
    parser.add_argument("--start_round", type=int, default=None)
    parser.add_argument("--output_path", type=str, default="data/data_switzerland.csv")
    return parser.parse_args()


def main():
    args = parse_args()
    game_ids: set[int] = set()
    if args.game_id:
        game_ids.add(args.game_id)
    if args.game_ids:
        for part in re.split(r"[\\s,]+", args.game_ids):
            if part.isdigit():
                game_ids.add(int(part))
    if args.game_ids_file:
        game_ids.update(_load_game_ids_from_file(args.game_ids_file))
    if args.schedule_url:
        for url in args.schedule_url:
            game_ids.update(fetch_game_ids_from_url(url))
    if args.league and args.season and args.game_class:
        game_ids.update(
            fetch_game_ids_from_renderengine(
                league=args.league,
                season=args.season,
                game_class=args.game_class,
                mode=args.mode,
            )
        )
    if args.league and args.season and args.game_class and args.group:
        game_ids.update(
            fetch_game_ids_by_rounds(
                league=args.league,
                season=args.season,
                game_class=args.game_class,
                group=args.group,
                start_round=args.start_round,
            )
        )

    if not game_ids:
        raise SystemExit(
            "Provide --game_id, --game_ids, --game_ids_file, --schedule_url, or --league/--season/--game_class (optionally with --group)."
        )

    scrape_games(game_ids=sorted(game_ids), output_path=args.output_path)


if __name__ == "__main__":
    main()
