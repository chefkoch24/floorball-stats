import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


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


def _parse_match_events(session: requests.Session, match: MatchCard) -> list[dict[str, Any]]:
    response = session.get(match.match_url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    home_node = soup.select_one(".HomeCompetitorTitle a")
    away_node = soup.select_one(".AwayCompetitorTitle a")
    if not home_node or not away_node:
        return []
    home_team = home_node.get_text(" ", strip=True)
    away_team = away_node.get_text(" ", strip=True)

    home_goals_node = soup.select_one("[data-match-text='goalsHome']")
    away_goals_node = soup.select_one("[data-match-text='goalsAway']")
    if not home_goals_node or not away_goals_node:
        return []
    try:
        final_home_goals = int(home_goals_node.get_text(strip=True))
        final_away_goals = int(away_goals_node.get_text(strip=True))
    except ValueError:
        return []

    game_date, game_start_time = _parse_meta(soup)
    result_string = f"{final_home_goals}:{final_away_goals}"

    container = soup.select_one("[data-match-placeholder='MatchOverviewEvents']")
    if not container:
        return []

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
                    if is_penalty:
                        penalty_text = event_cell.get_text(" ", strip=True)
                        penalty_type = _parse_penalty_type(penalty_text)

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
                            "game_status": "Played",
                            "ingame_status": None,
                            "result_string": result_string,
                        }
                    )
            table = table.find_next_sibling("table", class_="table-comparison")

    return rows


def scrape_competition(
    schedule_urls: list[str],
    output_path: str,
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
        rows.extend(_parse_match_events(session, match))

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
        ],
    )
    df.to_csv(out, index=False)
    return df


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule_url", action="append", required=True)
    parser.add_argument("--output_path", type=str, default="data/data_slovakia.csv")
    return parser.parse_args()


def main():
    args = parse_args()
    scrape_competition(schedule_urls=args.schedule_url, output_path=args.output_path)


if __name__ == "__main__":
    main()
