import argparse
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import time
from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from src.scheduled_games import build_scheduled_game_row


BASE_URL = "https://www.szfb.sk"
USER_AGENT = "Mozilla/5.0 (compatible; FloorballStats/1.0; +https://stats.floorballconnect.com)"


@dataclass
class MatchCard:
    match_id: int
    match_url: str


def _new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def _extract_league_slug(schedule_url: str) -> str | None:
    match = re.search(r"/(?:results-date|results|home)/\d+/([^/?#]+)", schedule_url)
    return match.group(1) if match else None


def _results_url_from_date_url(schedule_url: str) -> str | None:
    if "/results-date/" not in schedule_url:
        return None
    return re.sub(r"/results-date/", "/results/", schedule_url).split("?", 1)[0]


def _parse_schedule_matches(html: str, schedule_url: str) -> list[MatchCard]:
    soup = BeautifulSoup(html, "html.parser")
    expected_slug = _extract_league_slug(schedule_url)
    matches: dict[tuple[int, str], MatchCard] = {}
    for link in soup.select("a[href*='/sk/stats/matches/'][href*='/match/']"):
        href = link.get("href") or ""
        if expected_slug and f"/{expected_slug}/" not in href:
            continue
        match = re.search(r"(/sk/stats/matches/\d+/[^/]+/match/(\d+))", href)
        if not match:
            continue
        match_path = match.group(1)
        match_id = int(match.group(2))
        match_url = urljoin(BASE_URL, f"{match_path}/overview")
        matches[(match_id, match_path)] = MatchCard(match_id=match_id, match_url=match_url)
    return sorted(matches.values(), key=lambda m: m.match_id)


def _parse_penalty_type(text: str) -> str:
    lowered = text.lower()
    if "2+2" in lowered:
        return "penalty_2and2"
    if "10" in lowered:
        return "penalty_10"
    if "ms" in lowered:
        return "penalty_ms_full"
    return "penalty_2"


def _period_from_title(title: str) -> int:
    lowered = title.lower()
    if "1." in lowered:
        return 1
    if "2." in lowered:
        return 2
    if "3." in lowered:
        return 3
    if "predĺženie" in lowered:
        return 4
    if "nájazdy" in lowered:
        return 5
    return 0


def _sortkey(period: int, total_time: str) -> str:
    mm, ss = total_time.split(":", 1)
    total_min = int(mm)
    sec = int(ss)
    minute_in_period = max(0, total_min - (period - 1) * 20) if period > 0 else total_min
    return f"{period}-{minute_in_period:02d}:{sec:02d}"


def _parse_goal_people(text: str) -> tuple[str | None, str | None]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return None, None
    match = re.match(r"(?P<scorer>.+?)(?:\s*\((?P<assist>[^)]+)\))?$", cleaned)
    if not match:
        return cleaned, None
    scorer_name = (match.group("scorer") or "").strip()
    assist_name = (match.group("assist") or "").strip()
    return scorer_name or None, assist_name or None


def _normalize_player_name(text: str | None) -> str | None:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return None
    cleaned = re.sub(r"\(\d+\)$", "", cleaned).strip(" -")
    if "," in cleaned:
        last_name, first_name = [part.strip() for part in cleaned.split(",", 1)]
        if first_name and last_name:
            cleaned = f"{first_name} {last_name}"
    return cleaned or None


def _parse_penalty_player(text: str) -> str | None:
    cleaned = " ".join(text.split())
    cleaned = re.sub(r"^\d+\s*:\s*\d+\s*", "", cleaned).strip()
    cleaned = re.sub(r"\b(?:2\+2|10|5|4|2)\s*min\.?\b", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"\b(2\+2|10|5|2|ms)\b", "", cleaned, flags=re.I).strip(" -")
    cleaned = re.sub(r"\([^)]*\)$", "", cleaned).strip(" -")
    return _normalize_player_name(cleaned)


def _parse_meta(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    meta = soup.select_one(".match-info")
    if not meta:
        return None, None
    text = meta.get_text(" ", strip=True)
    date_match = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})", text)
    time_match = re.search(r",\s*(\d{1,2}:\d{2})", text)
    game_date = None
    if date_match:
        try:
            game_date = datetime.strptime(date_match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")
        except ValueError:
            game_date = None
    return game_date, time_match.group(1) if time_match else None


def _extract_attendance(soup: BeautifulSoup) -> int | None:
    candidates = []
    match_info = soup.select_one(".match-info")
    if match_info:
        candidates.append(match_info.get_text(" ", strip=True))
    candidates.append(soup.get_text(" ", strip=True))
    patterns = [
        r"diváci\s*:\s*(\d+)",
        r"divákov\s*:\s*(\d+)",
        r"návštevnosť\s*:\s*(\d+)",
        r"návšteva\s*:\s*(\d+)",
    ]
    for text in candidates:
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return int(match.group(1))
    return None


def _is_placeholder_team_name(name: Any) -> bool:
    text = str(name or "").strip().upper()
    return bool(re.fullmatch(r"[A-D]{3}", text))


def _parse_match_events(session: requests.Session, match: MatchCard) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    response = None
    for attempt in range(3):
        try:
            response = session.get(match.match_url, timeout=30)
            response.raise_for_status()
            break
        except requests.RequestException as exc:
            last_error = exc
            if attempt == 2:
                raise
            time.sleep(1.0 + attempt)
    if response is None:
        raise RuntimeError(f"Could not fetch match URL: {match.match_url}") from last_error
    soup = BeautifulSoup(response.text, "html.parser")

    home_node = soup.select_one(".HomeCompetitorTitle a")
    away_node = soup.select_one(".AwayCompetitorTitle a")
    if not home_node or not away_node:
        return []
    home_team = home_node.get_text(" ", strip=True)
    away_team = away_node.get_text(" ", strip=True)
    game_date, game_start_time = _parse_meta(soup)
    attendance = _extract_attendance(soup)

    home_goals_node = soup.select_one("[data-match-text='goalsHome']")
    away_goals_node = soup.select_one("[data-match-text='goalsAway']")
    if not home_goals_node or not away_goals_node:
        return [
            build_scheduled_game_row(
                game_id=match.match_id,
                home_team=home_team,
                away_team=away_team,
                game_date=game_date,
                game_start_time=game_start_time,
                attendance=attendance,
                game_status="Scheduled",
            )
        ]
    try:
        final_home_goals = int(home_goals_node.get_text(strip=True))
        final_away_goals = int(away_goals_node.get_text(strip=True))
    except ValueError:
        return [
            build_scheduled_game_row(
                game_id=match.match_id,
                home_team=home_team,
                away_team=away_team,
                game_date=game_date,
                game_start_time=game_start_time,
                attendance=attendance,
                game_status="Scheduled",
            )
        ]

    result_string = f"{final_home_goals}:{final_away_goals}"

    container = soup.select_one("[data-match-placeholder='MatchOverviewEvents']")
    if not container:
        return [
            build_scheduled_game_row(
                game_id=match.match_id,
                home_team=home_team,
                away_team=away_team,
                game_date=game_date,
                game_start_time=game_start_time,
                attendance=attendance,
                game_status="Played",
                result_string=result_string,
            )
        ]

    rows: list[dict[str, Any]] = []
    current_home = 0
    current_away = 0

    for period_block in container.select("div.matchPeriod-title"):
        title = period_block.get_text(" ", strip=True)
        current_period = _period_from_title(title)
        table = period_block.find_next_sibling("table", class_="table-comparison")
        while table and table.find_previous_sibling("div", class_="matchPeriod-title") == period_block:
            tr = table.find("tr")
            if tr:
                cells = tr.find_all("td")
                if len(cells) == 3:
                    left_cell, center_cell, right_cell = cells
                    time_text = center_cell.get_text(" ", strip=True)
                    if not re.match(r"^\d{1,2}:\d{2}$", time_text):
                        table = table.find_next_sibling("table", class_="table-comparison")
                        continue

                    team = None
                    event_cell = None
                    if left_cell.get_text(" ", strip=True):
                        team = home_team
                        event_cell = left_cell
                    elif right_cell.get_text(" ", strip=True):
                        team = away_team
                        event_cell = right_cell
                    if not team or event_cell is None:
                        table = table.find_next_sibling("table", class_="table-comparison")
                        continue

                    is_goal = event_cell.select_one(".label-success") is not None
                    is_penalty = event_cell.select_one(".label-danger") is not None
                    if not is_goal and not is_penalty:
                        table = table.find_next_sibling("table", class_="table-comparison")
                        continue

                    score_label = event_cell.select_one(".label-success")
                    if is_goal and score_label:
                        score_match = re.search(r"(\d+)\s*:\s*(\d+)", score_label.get_text(" ", strip=True))
                        if score_match:
                            current_home = int(score_match.group(1))
                            current_away = int(score_match.group(2))

                    event_type = "goal" if is_goal else "penalty"
                    penalty_type = None
                    goal_type = "goal" if is_goal else None
                    scorer_name = None
                    assist_name = None
                    penalty_player_name = None
                    if is_penalty:
                        penalty_text = event_cell.get_text(" ", strip=True)
                        penalty_type = _parse_penalty_type(penalty_text)
                        penalty_player_name = _parse_penalty_player(penalty_text)
                    else:
                        if score_label:
                            score_label.extract()
                        scorer_node = event_cell.select_one("div > a, span > a, a")
                        assist_node = event_cell.select_one(".faded.font-small a")
                        if scorer_node:
                            scorer_name = _normalize_player_name(scorer_node.get_text(" ", strip=True))
                        if assist_node:
                            assist_name = _normalize_player_name(assist_node.get_text(" ", strip=True))
                        if not scorer_name and not assist_name:
                            scorer_name, assist_name = _parse_goal_people(event_cell.get_text(" ", strip=True))
                            scorer_name = _normalize_player_name(scorer_name)
                            assist_name = _normalize_player_name(assist_name)

                    rows.append(
                        {
                            "event_type": event_type,
                            "event_team": team,
                            "period": current_period,
                            "sortkey": _sortkey(current_period, time_text),
                            "game_id": match.match_id,
                            "home_team_name": home_team,
                            "away_team_name": away_team,
                            "home_goals": current_home,
                            "guest_goals": current_away,
                            "goal_type": goal_type,
                            "penalty_type": penalty_type,
                            "game_date": game_date,
                            "game_start_time": game_start_time,
                            "attendance": attendance,
                            "game_status": "Played",
                            "ingame_status": None,
                            "result_string": result_string,
                            "scorer_name": scorer_name,
                            "assist_name": assist_name,
                            "scorer_number": None,
                            "assist_number": None,
                            "penalty_player_name": penalty_player_name,
                        }
                    )
            table = table.find_next_sibling("table", class_="table-comparison")

    return rows


def scrape_competition(
    schedule_urls: list[str],
    output_path: str,
    phase: str = "regular-season",
    regular_season_end_date: str | None = None,
    regular_season_games_per_team: int | None = None,
) -> pd.DataFrame:
    session = _new_session()
    all_matches: dict[int, MatchCard] = {}
    resolved_urls: list[str] = []
    seen_urls: set[str] = set()
    for schedule_url in schedule_urls:
        if schedule_url not in seen_urls:
            resolved_urls.append(schedule_url)
            seen_urls.add(schedule_url)
        alt_url = _results_url_from_date_url(schedule_url)
        if alt_url and alt_url not in seen_urls:
            resolved_urls.append(alt_url)
            seen_urls.add(alt_url)

    for schedule_url in resolved_urls:
        response = session.get(schedule_url, timeout=30)
        response.raise_for_status()
        for match in _parse_schedule_matches(response.text, schedule_url):
            all_matches[match.match_id] = match

    rows: list[dict[str, Any]] = []
    for match in tqdm(sorted(all_matches.values(), key=lambda m: m.match_id), desc="slovakia matches"):
        try:
            rows.extend(_parse_match_events(session, match))
        except requests.RequestException as exc:
            print(f"[WARN] skipping match {match.match_id} after repeated request failures: {exc}")
            continue

    if regular_season_end_date:
        cutoff = datetime.strptime(regular_season_end_date, "%Y-%m-%d").date()

        def _parse_row_date(value: Any) -> date | None:
            if not value:
                return None
            try:
                return datetime.strptime(str(value), "%Y-%m-%d").date()
            except ValueError:
                return None

        games: dict[int, dict[str, Any]] = {}
        for row in rows:
            game_id = int(row.get("game_id"))
            entry = games.setdefault(
                game_id,
                {
                    "rows": [],
                    "date": _parse_row_date(row.get("game_date")),
                    "home": row.get("home_team_name"),
                    "away": row.get("away_team_name"),
                },
            )
            entry["rows"].append(row)
            if entry["date"] is None:
                entry["date"] = _parse_row_date(row.get("game_date"))

        pre_cutoff_ids = {
            game_id
            for game_id, game in games.items()
            if game.get("date") is not None and game["date"] <= cutoff
        }
        post_cutoff_ids = [
            game_id
            for game_id, game in sorted(
                games.items(),
                key=lambda item: (item[1].get("date") or date.max, item[0]),
            )
            if game.get("date") is not None and game["date"] > cutoff
        ]

        regular_ids = set(pre_cutoff_ids)
        if regular_season_games_per_team and regular_season_games_per_team > 0:
            team_games: dict[str, int] = {}

            def _inc_team(team: str | None) -> None:
                if not team:
                    return
                team_games[team] = team_games.get(team, 0) + 1

            for game_id in sorted(regular_ids):
                game = games[game_id]
                _inc_team(game.get("home"))
                _inc_team(game.get("away"))

            for game_id in post_cutoff_ids:
                game = games[game_id]
                home = game.get("home")
                away = game.get("away")
                home_games = team_games.get(home, 0)
                away_games = team_games.get(away, 0)
                if home_games < regular_season_games_per_team and away_games < regular_season_games_per_team:
                    regular_ids.add(game_id)
                    _inc_team(home)
                    _inc_team(away)

        phase_lower = (phase or "regular-season").lower()
        selected_ids = regular_ids if phase_lower == "regular-season" else (set(games.keys()) - regular_ids)
        selected_ids = {
            game_id
            for game_id in selected_ids
            if not (
                _is_placeholder_team_name(games[game_id].get("home"))
                or _is_placeholder_team_name(games[game_id].get("away"))
            )
        }
        rows = [row for game_id in sorted(selected_ids) for row in games[game_id]["rows"]]

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        rows,
        columns=[
            "event_type",
            "event_team",
            "period",
            "sortkey",
            "game_id",
            "home_team_name",
            "away_team_name",
            "home_goals",
            "guest_goals",
            "goal_type",
            "penalty_type",
            "game_date",
            "game_start_time",
            "game_status",
            "ingame_status",
            "result_string",
            "attendance",
            "scorer_name",
            "assist_name",
            "scorer_number",
            "assist_number",
            "penalty_player_name",
        ],
    )
    df.to_csv(out, index=False)
    return df


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule_url", action="append", required=True)
    parser.add_argument("--phase", type=str, default="regular-season")
    parser.add_argument("--regular_season_end_date", type=str, default=None)
    parser.add_argument("--regular_season_games_per_team", type=int, default=None)
    parser.add_argument("--output_path", type=str, default="data/data_slovakia.csv")
    return parser.parse_args()


def main():
    args = parse_args()
    scrape_competition(
        schedule_urls=args.schedule_url,
        output_path=args.output_path,
        phase=args.phase,
        regular_season_end_date=args.regular_season_end_date,
        regular_season_games_per_team=args.regular_season_games_per_team,
    )


if __name__ == "__main__":
    main()
