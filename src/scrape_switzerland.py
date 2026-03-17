import argparse
import re
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


@dataclass
class GameDetails:
    home_team: str
    away_team: str
    game_date: str | None
    game_start_time: str | None
    result_string: str | None
    goals_home: int | None
    goals_away: int | None
    attendance: int | None
    header_text: str | None


def _fetch_block(game_id: int, block_type: str, locale: str = "de-CH") -> str:
    params = {
        "view": "short",
        "game_id": str(game_id),
        "is_home": "1",
        "block_type": block_type,
        "ID_Block": "SU_2886",
        "locale": locale,
    }
    response = requests.get(RENDER_URL, params=params, timeout=30)
    response.raise_for_status()
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

    result_raw = data.get("result")
    goals_home = None
    goals_away = None
    if result_raw and ":" in result_raw:
        score = result_raw.split("(", 1)[0].strip()
        match = re.match(r"(?P<h>\d+)\s*:\s*(?P<a>\d+)", score)
        if match:
            goals_home = int(match.group("h"))
            goals_away = int(match.group("a"))
    spectators_raw = data.get("spectators")
    attendance = int(spectators_raw) if spectators_raw and str(spectators_raw).isdigit() else None

    return GameDetails(
        home_team=data.get("home_name", ""),
        away_team=data.get("away_name", ""),
        game_date=_normalize_date(data.get("date")),
        game_start_time=data.get("time"),
        result_string=result_raw,
        goals_home=goals_home,
        goals_away=goals_away,
        attendance=attendance,
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
        scorer_name = cleaned[:assist_match.start()].strip(" ,;-")
        assist_name = assist_match.group(1).strip(" ,;-")
        return scorer_name or None, assist_name or None
    match = re.match(r"(?P<scorer>.+?)(?:\s*\((?P<assist>[^)]+)\))?$", cleaned)
    if not match:
        return cleaned, None
    return (match.group("scorer") or "").strip() or None, (match.group("assist") or "").strip() or None


def _classify_phase(header_text: str | None) -> str:
    if not header_text:
        return "regular-season"
    text = header_text.lower()
    playoff_keywords = [
        "playoff",
        "playoffs",
        "playdown",
        "playdowns",
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


def _parse_game_events(html: str, game_id: int, details: GameDetails) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table.su-result tbody tr")
    events: list[dict[str, Any]] = []

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

    return events


def _extract_game_ids(html: str) -> set[int]:
    ids = set()
    for match in re.findall(r"game_id=(\d+)", html):
        ids.add(int(match))
    return ids


def fetch_game_ids_from_url(url: str) -> list[int]:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
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
    response = requests.get(RENDER_URL, params=params, timeout=30)
    response.raise_for_status()
    return sorted(_extract_game_ids(response.text))


def _extract_round_ids(html: str) -> set[int]:
    ids = set()
    for match in re.findall(r"round=(\d+)", html):
        ids.add(int(match))
    return ids


def fetch_game_ids_by_rounds(
    league: int,
    season: int,
    game_class: int,
    group: str,
    locale: str = "de-CH",
    start_round: int | None = None,
) -> list[int]:
    base_params = {
        "block_type": "games",
        "league": str(league),
        "season": str(season),
        "game_class": str(game_class),
        "view": "full",
        "group": group,
        "mode": "list",
        "use_streaming_logos": "0",
        "locale": locale,
    }

    to_visit: list[int] = []
    seen_rounds: set[int] = set()
    game_ids: set[int] = set()

    if start_round is not None:
        to_visit.append(start_round)
    else:
        response = requests.get(RENDER_URL, params=base_params, timeout=30)
        response.raise_for_status()
        html = response.text
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
        response = requests.get(RENDER_URL, params=params, timeout=30)
        response.raise_for_status()
        html = response.text
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
        if phase_filter and _classify_phase(details.header_text) != phase_filter:
            continue
        events = _parse_game_events(events_html, game_id, details)
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
