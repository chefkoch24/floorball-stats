import argparse
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup, NavigableString
from tqdm import tqdm

from src.scheduled_games import build_scheduled_game_row


USER_AGENT = "Mozilla/5.0 (compatible; FloorballStats/1.0; +https://fliiga.com/)"
DEFAULT_SCHEDULE_URL = "https://fliiga.com/en/matches/men/"
FINLAND_TZ = ZoneInfo("Europe/Helsinki")

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
    is_hidden: bool


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
        is_hidden = "match-hidden" in classes
        game_date = card.get("data-match-date")
        game_start_time = card.get("data-match-time")
        gameday = card.get("data-match-gameday")
        if gameday:
            try:
                ts = int(gameday)
                dt_local = datetime.fromtimestamp(ts, tz=FINLAND_TZ)
                if not game_date:
                    game_date = dt_local.strftime("%Y-%m-%d")
                if not game_start_time:
                    game_start_time = dt_local.strftime("%H:%M")
            except (ValueError, OSError):
                if not game_date:
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
                is_hidden=is_hidden,
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


def _extract_final_score(soup: BeautifulSoup) -> tuple[int | None, int | None]:
    home_node = soup.select_one(".match-scores .home-goals")
    away_node = soup.select_one(".match-scores .away-goals")
    if not home_node or not away_node:
        return None, None
    try:
        return int(home_node.get_text(strip=True)), int(away_node.get_text(strip=True))
    except ValueError:
        return None, None


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


def _parse_goal_people(event_div: Any) -> tuple[str | None, str | None]:
    scorer_node = event_div.select_one(".event-home .scorer, .event-away .scorer")
    assist_node = event_div.select_one(
        ".event-home .has-assists, .event-away .has-assists, .event-home .assist, .event-away .assist"
    )
    scorer_name = scorer_node.get_text(" ", strip=True) if scorer_node else None
    assist_name = assist_node.get_text(" ", strip=True) if assist_node else None
    if assist_name:
        assist_name = re.sub(r"^(assist|syöttäjä)\s*[:\-]?\s*", "", assist_name, flags=re.I).strip()
    return scorer_name or None, assist_name or None


def _parse_penalty_player(event_div: Any) -> str | None:
    info_node = event_div.select_one(".event-home .event-info, .event-away .event-info")
    if not info_node:
        return None
    direct_text = "".join(
        str(content) for content in info_node.contents if isinstance(content, NavigableString)
    ).strip()
    text = direct_text or info_node.get_text(" ", strip=True)
    if not text:
        return None
    text = re.sub(r"^\d+\s*min\s*", "", text, flags=re.I).strip(" -")
    return text or None


def _extract_attendance(soup: BeautifulSoup) -> int | None:
    attendance_node = soup.select_one(".additional.audience")
    text = attendance_node.get_text(" ", strip=True) if attendance_node else soup.get_text(" ", strip=True)
    match = re.search(r"(?:Audience|Yleisömäärä)\s*(\d+)", text, re.I)
    if match:
        return int(match.group(1))
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

    final_home, final_away = _extract_final_score(soup)
    attendance = _extract_attendance(soup)

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
            scorer_name, assist_name = _parse_goal_people(event_div)
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
            scorer_name = None
            assist_name = None
            penalty_player_name = _parse_penalty_player(event_div)
            penalty_type = _penalty_type_from_event(event_div)
            goal_type = None
        if event_type == "goal":
            penalty_player_name = None

        if not event_team:
            continue

        result_home = final_home if final_home is not None else current_home
        result_away = final_away if final_away is not None else current_away

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
                "attendance": attendance,
                "game_status": "Played" if match.is_played else "Scheduled",
                "ingame_status": None,
                "result_string": f"{result_home}-{result_away}",
                "scorer_name": scorer_name,
                "assist_name": assist_name,
                "scorer_number": None,
                "assist_number": None,
                "penalty_player_name": penalty_player_name,
            }
        )

    return rows


def scrape_matches(
    schedule_urls: list[str],
    output_path: str,
    include_unplayed: bool = False,
    phase: str = "regular-season",
) -> pd.DataFrame:
    matches: list[MatchCard] = []
    for url in schedule_urls:
        html = _get(url)
        matches.extend(_parse_match_cards(html))

    def _as_date(value: str | None) -> date | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    phase_lower = phase.lower()
    today_local = datetime.now(FINLAND_TZ).date()
    if phase_lower == "playoffs":
        # User rule for Finland 25/26: playoffs start from today's games onward.
        filtered_matches: list[MatchCard] = []
        for match in matches:
            match_date = _as_date(match.game_date)
            if match_date is not None and match_date >= today_local:
                filtered_matches.append(match)
            elif match_date is None and not match.is_hidden:
                filtered_matches.append(match)
        matches = filtered_matches
    elif phase_lower == "regular-season":
        # All games before today belong to regular season.
        filtered_matches = []
        for match in matches:
            match_date = _as_date(match.game_date)
            if match_date is not None and match_date < today_local:
                filtered_matches.append(match)
            elif match_date is None and match.is_hidden:
                filtered_matches.append(match)
        matches = filtered_matches

    rows: list[dict[str, Any]] = []
    for match in tqdm(matches, desc="fliiga matches"):
        if not include_unplayed and not match.is_played:
            continue
        match_html = _get(match.url)
        events = _parse_match_events(match_html, match)
        if events:
            rows.extend(events)
        elif include_unplayed:
            rows.append(
                build_scheduled_game_row(
                    game_id=match.match_id,
                    home_team=match.home_team,
                    away_team=match.away_team,
                    game_date=match.game_date,
                    game_start_time=match.game_start_time,
                    attendance=None,
                    game_status="Played" if match.is_played else "Scheduled",
                )
            )

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
    parser.add_argument("--phase", type=str, default="regular-season")
    return parser.parse_args()


def main():
    args = parse_args()
    scrape_matches(
        schedule_urls=args.schedule_url,
        output_path=args.output_path,
        include_unplayed=args.include_unplayed,
        phase=args.phase,
    )


if __name__ == "__main__":
    main()
