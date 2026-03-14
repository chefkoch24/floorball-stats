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


BASE_URL = "https://www.ceskyflorbal.cz"


@dataclass
class MatchSummary:
    match_id: int
    home_team: str
    away_team: str
    score_text: str | None
    status: str | None
    round_name: str | None
    date_text: str | None


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned if cleaned else None


def _parse_score(score_text: str | None) -> tuple[int | None, int | None, str | None]:
    if not score_text:
        return None, None, None
    score_text = score_text.strip()
    suffix = None
    match = re.match(r"(\d+)\s*:\s*(\d+)([A-Za-z]+)?", score_text)
    if not match:
        return None, None, None
    home = int(match.group(1))
    away = int(match.group(2))
    suffix = match.group(3).lower() if match.group(3) else None
    return home, away, suffix


def _parse_date(date_text: str | None, season_start_year: int) -> str | None:
    if not date_text:
        return None
    match = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.", date_text)
    if not match:
        return None
    day = int(match.group(1))
    month = int(match.group(2))
    year = season_start_year if month >= 7 else season_start_year + 1
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def fetch_match_list(
    schedule_url: str,
    season_start_year: int,
    session: requests.Session | None = None,
) -> list[MatchSummary]:
    sess = session or requests.Session()
    resp = sess.get(schedule_url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    matches = []
    for match_div in soup.select("div.Match"):
        score_anchor = match_div.select_one(".Match-score a")
        match_id = None
        score_text = _clean_text(score_anchor.get_text()) if score_anchor else None
        if score_anchor and score_anchor.has_attr("href"):
            match = re.search(r"/match/detail/default/(\d+)", score_anchor["href"])
            if match:
                match_id = int(match.group(1))
        if not match_id:
            continue

        home_team = _clean_text(match_div.select_one(".Match-leftContent .Match-teamName") and match_div.select_one(".Match-leftContent .Match-teamName").get_text())
        away_team = _clean_text(match_div.select_one(".Match-rightContent .Match-teamName") and match_div.select_one(".Match-rightContent .Match-teamName").get_text())
        status = _clean_text(match_div.select_one(".Match-status") and match_div.select_one(".Match-status").get_text())
        round_name = _clean_text(match_div.select_one(".Match-round") and match_div.select_one(".Match-round").get_text())
        date_text = _clean_text(match_div.select_one(".Match-date") and match_div.select_one(".Match-date").get_text())

        matches.append(
            MatchSummary(
                match_id=match_id,
                home_team=home_team or "n.a.",
                away_team=away_team or "n.a.",
                score_text=score_text,
                status=status,
                round_name=round_name,
                date_text=_parse_date(date_text, season_start_year),
            )
        )
    return matches


def _map_penalty_type(text: str | None) -> str:
    if not text:
        return "penalty_2"
    cleaned = text.strip()
    if "2+2" in cleaned:
        return "penalty_2and2"
    if cleaned.startswith("10"):
        return "penalty_10"
    if cleaned.lower().startswith("ms"):
        return "penalty_ms_full"
    return "penalty_2"


def _parse_event_rows(
    event_block: Any,
    event_team: str,
    period_label: str,
    home_team: str,
    away_team: str,
    game_id: int,
    game_date: str | None,
    result_string: str | None,
    goal_type: str,
    penalty_type: str | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    period_label = period_label.strip()
    if period_label.isdigit():
        period = int(period_label)
    elif period_label.upper() == "P":
        period = 4
    elif period_label.upper() == "N":
        period = 5
    else:
        period = 0

    for row in event_block.select("li.Timeline-win-row"):
        left = row.select_one(".Timeline-win-left")
        right = row.select_one(".Timeline-win-right")
        if not left or not right:
            continue
        left_text = " ".join(left.get_text("\n").split())
        right_text = " ".join(right.get_text("\n").split())

        time_match = re.search(r"(\d{1,2}):(\d{2})", left_text)
        minute = int(time_match.group(1)) if time_match else 0
        second = int(time_match.group(2)) if time_match else 0
        sortkey = f"{period}-{minute:02d}:{second:02d}"

        score_match = re.search(r"(\d+)\s*:\s*(\d+)", right_text)
        home_goals = int(score_match.group(1)) if score_match else None
        away_goals = int(score_match.group(2)) if score_match else None

        # Timeline "more" blocks can mix goals with penalties/timeouts.
        # If this row is treated as a goal but has no score snapshot, skip it.
        if penalty_type is None and score_match is None:
            continue

        row_data = {
            "event_type": "penalty" if penalty_type else "goal",
            "event_team": event_team,
            "period": period,
            "sortkey": sortkey,
            "game_id": game_id,
            "home_team_name": home_team,
            "away_team_name": away_team,
            "home_goals": home_goals,
            "guest_goals": away_goals,
            "goal_type": goal_type,
            "penalty_type": penalty_type,
            "game_date": game_date,
            "game_start_time": None,
            "game_status": None,
            "ingame_status": None,
            "result_string": result_string,
        }
        rows.append(row_data)
    return rows


def fetch_match_events(match_id: int, game_date: str | None, session: requests.Session | None = None) -> list[dict[str, Any]]:
    sess = session or requests.Session()
    url = f"{BASE_URL}/match/detail/match/{match_id}?locale=en"
    resp = sess.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    home_team = _clean_text(soup.select_one(".MatchHeader-home .MatchHeader-normalName") and soup.select_one(".MatchHeader-home .MatchHeader-normalName").get_text()) or "n.a."
    away_team = _clean_text(soup.select_one(".MatchHeader-quest .MatchHeader-normalName") and soup.select_one(".MatchHeader-quest .MatchHeader-normalName").get_text()) or "n.a."
    score_text = _clean_text(soup.select_one(".MatchHeader-score") and soup.select_one(".MatchHeader-score").get_text())
    home_goals, away_goals, suffix = _parse_score(score_text)
    result_string = f"{home_goals}:{away_goals}" if home_goals is not None and away_goals is not None else None

    events: list[dict[str, Any]] = []
    timeline = soup.select_one(".Timeline.u-display-flex.u-sm-display-none")
    for part in timeline.select(".Timeline-part") if timeline else []:
        period_label = _clean_text(part.select_one(".Timeline-name") and part.select_one(".Timeline-name").get_text()) or ""
        for event in part.select(".Timeline-goal, .Timeline-exclusion, .Timeline-more, .Timeline-raid-success"):
            class_list = event.get("class", [])
            is_home = any("home" in cls for cls in class_list)
            is_quest = any("quest" in cls for cls in class_list)
            event_team = home_team if is_home else away_team if is_quest else home_team
            is_penalty = any("exclusion" in cls for cls in class_list)
            is_raid = any("raid" in cls for cls in class_list)

            goal_type = "penalty_shot" if is_raid else "goal"
            penalty_type = None
            if is_penalty:
                right = event.select_one(".Timeline-win-right")
                penalty_minutes = None
                if right:
                    right_text = right.get_text("\n")
                    penalty_match = re.search(r"(\d\+?\d?)", right_text)
                    if penalty_match:
                        penalty_minutes = penalty_match.group(1)
                penalty_type = _map_penalty_type(penalty_minutes)

            events.extend(
                _parse_event_rows(
                    event_block=event,
                    event_team=event_team,
                    period_label=period_label,
                    home_team=home_team,
                    away_team=away_team,
                    game_id=match_id,
                    game_date=game_date,
                    result_string=result_string,
                    goal_type=goal_type,
                    penalty_type=penalty_type,
                )
            )

    if suffix in {"pn", "ps"} and result_string:
        winner = home_team if (home_goals or 0) > (away_goals or 0) else away_team
        if not any(e["period"] == 5 for e in events):
            events.append(
                {
                    "event_type": "goal",
                    "event_team": winner,
                    "period": 5,
                    "sortkey": "5-00:00",
                    "game_id": match_id,
                    "home_team_name": home_team,
                    "away_team_name": away_team,
                    "home_goals": home_goals,
                    "guest_goals": away_goals,
                    "goal_type": "penalty_shot",
                    "penalty_type": None,
                    "game_date": game_date,
                    "game_start_time": None,
                    "game_status": None,
                    "ingame_status": None,
                    "result_string": result_string,
                }
            )
    elif suffix in {"pp", "ot"} and result_string:
        winner = home_team if (home_goals or 0) > (away_goals or 0) else away_team
        if not any(e["period"] == 4 for e in events):
            events.append(
                {
                    "event_type": "goal",
                    "event_team": winner,
                    "period": 4,
                    "sortkey": "4-00:00",
                    "game_id": match_id,
                    "home_team_name": home_team,
                    "away_team_name": away_team,
                    "home_goals": home_goals,
                    "guest_goals": away_goals,
                    "goal_type": "goal",
                    "penalty_type": None,
                    "game_date": game_date,
                    "game_start_time": None,
                    "game_status": None,
                    "ingame_status": None,
                    "result_string": result_string,
                }
            )

    return events


def scrape_competition(
    schedule_urls: list[str],
    output_path: str,
    season_start_year: int,
    include_unplayed: bool = False,
) -> pd.DataFrame:
    session = requests.Session()
    all_matches: list[MatchSummary] = []
    for url in schedule_urls:
        all_matches.extend(fetch_match_list(url, season_start_year, session=session))

    rows: list[dict[str, Any]] = []
    for match in tqdm(all_matches, desc="matches"):
        if not include_unplayed and match.status and match.status.lower() != "played":
            continue
        rows.extend(fetch_match_events(match.match_id, match.date_text, session=session))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    return df


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule_url", action="append", required=True)
    parser.add_argument("--output_path", type=str, default="data/data_czech.csv")
    parser.add_argument("--season_start_year", type=int, required=True)
    parser.add_argument("--include_unplayed", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    scrape_competition(
        schedule_urls=args.schedule_url,
        output_path=args.output_path,
        season_start_year=args.season_start_year,
        include_unplayed=args.include_unplayed,
    )


if __name__ == "__main__":
    main()
