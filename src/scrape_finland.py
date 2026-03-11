import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


USER_AGENT = "Mozilla/5.0 (compatible; FloorballStats/1.0; +https://fliiga.com/)"
DEFAULT_SCHEDULE_URL = "https://fliiga.com/en/matches/men/"

GOAL_SCORE_RE = re.compile(r"(\d+)\s*-\s*(\d+)")
PENALTY_CLASS_RE = re.compile(r"event-(\d+)min")


@dataclass
class MatchCard:
    match_id: str
    url: str
    game_date: str | None
    game_start_time: str | None
    home_team: str | None
    away_team: str | None
    is_played: bool


def _get(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return resp.text


def _parse_match_cards(html: str) -> list[MatchCard]:
    soup = BeautifulSoup(html, "html.parser")
    cards: list[MatchCard] = []
    for card in soup.select(".match-card"):
        match_id_raw = card.get("data-match-id")
        match_url = card.select_one("a.match-link")
        if not match_id_raw or not match_url or not match_url.get("href"):
            if not match_url or not match_url.get("href"):
                continue
            match_id = match_url["href"].rstrip("/").split("/")[-1]
        else:
            match_id = str(match_id_raw)
        team_names = [t.get_text(strip=True) for t in card.select(".match-team .team-name")]
        home_team = team_names[0] if len(team_names) >= 1 else None
        away_team = team_names[1] if len(team_names) >= 2 else None
        classes = card.get("class", [])
        is_played = "match-Played" in classes
        game_date = card.get("data-match-date")
        game_start_time = card.get("data-match-time")
        gameday = card.get("data-match-gameday")
        if not game_date and gameday:
            try:
                ts = int(gameday)
                game_date = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            except (ValueError, OSError):
                game_date = None
        if not game_date:
            slug = match_url["href"].rstrip("/").split("/")[-1]
            parts = slug.rsplit("-", 3)
            if len(parts) == 4:
                day, month, year = parts[-3:]
                if day.isdigit() and month.isdigit() and year.isdigit():
                    game_date = f"{year}-{int(month):02d}-{int(day):02d}"

        cards.append(
            MatchCard(
                match_id=match_id,
                url=match_url["href"],
                game_date=game_date,
                game_start_time=game_start_time,
                home_team=home_team,
                away_team=away_team,
                is_played=is_played,
            )
        )
    return cards


def _period_from_total_minutes(total_minutes: int) -> int:
    if total_minutes < 20:
        return 1
    if total_minutes < 40:
        return 2
    if total_minutes < 60:
        return 3
    if total_minutes < 80:
        return 4
    return 5


def _minute_in_period(total_minutes: int, period: int) -> int:
    return max(0, total_minutes - (period - 1) * 20)


def _parse_time(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    parts = value.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        minutes = int(parts[0])
        seconds = int(parts[1])
    except ValueError:
        return None
    return minutes, seconds


def _extract_score(desc: str | None, current_home: int, current_away: int) -> tuple[int, int]:
    if not desc:
        return current_home, current_away
    match = GOAL_SCORE_RE.search(desc)
    if not match:
        return current_home, current_away
    return int(match.group(1)), int(match.group(2))


def _penalty_type_from_event(event_div: Any) -> str:
    penalty_tag = event_div.select_one(".penalty-tag")
    if penalty_tag:
        text = penalty_tag.get_text(strip=True).lower()
        if "10" in text:
            return "penalty_10"
        if "5" in text:
            return "penalty_5"
        if "2" in text:
            return "penalty_2"
    for cls in event_div.get("class", []):
        match = PENALTY_CLASS_RE.match(cls)
        if match:
            minutes = match.group(1)
            if minutes == "10":
                return "penalty_10"
            if minutes == "5":
                return "penalty_5"
            return "penalty_2"
    return "penalty_2"


def _event_team_from_goal(event_div: Any, home_team: str, away_team: str) -> str | None:
    if event_div.select_one(".event-home .scorer"):
        return home_team
    if event_div.select_one(".event-away .scorer"):
        return away_team
    return None


def _event_team_from_penalty(event_div: Any, home_team: str, away_team: str) -> str | None:
    home_text = event_div.select_one(".event-home .event-info")
    away_text = event_div.select_one(".event-away .event-info")
    if home_text and home_text.get_text(strip=True):
        return home_team
    if away_text and away_text.get_text(strip=True):
        return away_team
    return None


def _parse_match_events(match_html: str, match: MatchCard) -> list[dict[str, Any]]:
    soup = BeautifulSoup(match_html, "html.parser")
    home_team = match.home_team
    away_team = match.away_team
    if not home_team or not away_team:
        names = [t.get_text(strip=True) for t in soup.select(".match-teams .team-name")]
        if len(names) >= 2:
            home_team = names[0]
            away_team = names[1]
    if not home_team or not away_team:
        return []

    current_home = 0
    current_away = 0
    rows: list[dict[str, Any]] = []
    for event_div in soup.select(".match-event"):
        classes = event_div.get("class", [])
        event_type = None
        if "event-maali" in classes:
            event_type = "goal"
        elif any(cls.startswith("event-") and cls.endswith("min") for cls in classes):
            event_type = "penalty"
        if not event_type:
            continue

        time_node = event_div.select_one(".event-time .time")
        parsed_time = _parse_time(time_node.get_text(strip=True) if time_node else None)
        if not parsed_time:
            continue
        total_min, sec = parsed_time
        period = _period_from_total_minutes(total_min)
        minute_in_period = _minute_in_period(total_min, period)
        sortkey = f"{period}-{minute_in_period:02d}:{sec:02d}"

        if event_type == "goal":
            event_team = _event_team_from_goal(event_div, home_team, away_team)
            desc_node = event_div.select_one(".event-time .desc")
            current_home, current_away = _extract_score(
                desc_node.get_text(strip=True) if desc_node else None,
                current_home,
                current_away,
            )
            penalty_type = None
            goal_type = "goal"
        else:
            event_team = _event_team_from_penalty(event_div, home_team, away_team)
            penalty_type = _penalty_type_from_event(event_div)
            goal_type = None

        if not event_team:
            continue

        rows.append(
            {
                "event_type": event_type,
                "event_team": event_team,
                "period": period,
                "sortkey": sortkey,
                "game_id": match.match_id,
                "home_team_name": home_team,
                "away_team_name": away_team,
                "home_goals": current_home,
                "guest_goals": current_away,
                "goal_type": goal_type,
                "penalty_type": penalty_type,
                "game_date": match.game_date,
                "game_start_time": match.game_start_time,
                "game_status": "Played" if match.is_played else "Scheduled",
                "ingame_status": None,
                "result_string": f"{current_home}-{current_away}",
            }
        )

    return rows


def scrape_matches(
    schedule_urls: list[str],
    output_path: str,
    include_unplayed: bool = False,
) -> pd.DataFrame:
    matches: list[MatchCard] = []
    for url in schedule_urls:
        html = _get(url)
        matches.extend(_parse_match_cards(html))

    rows: list[dict[str, Any]] = []
    for match in tqdm(matches, desc="fliiga matches"):
        if not include_unplayed and not match.is_played:
            continue
        match_html = _get(match.url)
        events = _parse_match_events(match_html, match)
        if events:
            rows.extend(events)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    return df


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule_url", action="append", default=[DEFAULT_SCHEDULE_URL])
    parser.add_argument("--output_path", type=str, default="data/data_finland.csv")
    parser.add_argument("--include_unplayed", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    scrape_matches(
        schedule_urls=args.schedule_url,
        output_path=args.output_path,
        include_unplayed=args.include_unplayed,
    )


if __name__ == "__main__":
    main()
