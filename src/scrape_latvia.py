import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


BASE_URL = "https://www.floorball.lv"
AJAX_CALENDAR_URL = "https://www.floorball.lv/ajax/ajax_chempionats_kalendars.php"
AJAX_MONTHS_URL = "https://www.floorball.lv/ajax/ajax_chempionats_kalendars_meneshi.php"
USER_AGENT = "Mozilla/5.0 (compatible; FloorballStats/1.0; +https://stats.floorballconnect.com)"


@dataclass
class LatviaMatch:
    game_id: int
    proto_url: str
    home_team: str
    away_team: str
    game_date: str | None
    game_start_time: str | None
    result_string: str | None
    ingame_status: str | None


def _new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    return session


def _parse_group_from_url(calendar_url: str) -> str:
    path = urlparse(calendar_url).path
    match = re.search(r"/chempionats/([^/]+)/kalendars/?$", path)
    if not match:
        raise ValueError(f"Could not parse group code from calendar URL: {calendar_url}")
    return match.group(1)


def _extract_season_id(page_html: str) -> int:
    match = re.search(r'"name":\s*"filtrs_sezona"\s*,\s*"value":\s*"(\d+)"', page_html)
    if not match:
        raise ValueError("Could not find filtrs_sezona value on calendar page")
    return int(match.group(1))


def _extract_game_types(page_html: str, phase: str = "regular-season") -> list[str]:
    soup = BeautifulSoup(page_html, "html.parser")
    options: list[tuple[str, str]] = []
    for option in soup.select("#filtrs_kalendars_spelu_veids option"):
        value = (option.get("value") or "").strip()
        if not value:
            continue
        label = option.get_text(" ", strip=True).lower()
        options.append((value, label))

    if not options:
        return ["all"]

    # Prefer phase-specific matches; "all" mixes regular season and playoffs.
    phase_lower = (phase or "regular-season").lower()
    if phase_lower == "playoffs":
        playoff_values = [value for value, label in options if ("play" in label or "izsl" in label)]
        if playoff_values:
            return [playoff_values[0]]
    else:
        regular_values = [value for value, label in options if "regul" in label]
        if regular_values:
            return [regular_values[0]]

    option_values = [value for value, _ in options]
    if "1" in option_values:
        return ["1"]
    if "all" in option_values:
        return ["all"]
    if "0" in option_values:
        return ["0"]
    return [option_values[0]]


def _fetch_month_options(
    session: requests.Session,
    calendar_url: str,
    season_id: int,
    group: str,
    game_type: str,
) -> list[str]:
    response = session.post(
        AJAX_MONTHS_URL,
        data={
            "sezona": str(season_id),
            "grupa": group,
            "filtrs_spelu_veids": game_type,
        },
        headers={"Referer": calendar_url},
        timeout=30,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    months = []
    for option in soup.select("option"):
        value = (option.get("value") or "").strip()
        if value:
            months.append(value)
    return months or ["all"]


def _extract_score(score_html: str) -> tuple[int | None, int | None, str | None]:
    text = BeautifulSoup(score_html or "", "html.parser").get_text(" ", strip=True)
    if not text:
        return None, None, None
    match = re.search(r"(\d+)\s*:\s*(\d+)", text)
    if not match:
        return None, None, None
    home = int(match.group(1))
    away = int(match.group(2))
    suffix = None
    upper_text = text.upper()
    if "PS" in upper_text:
        suffix = "penalty_shots"
    elif "ET" in upper_text or "OT" in upper_text:
        suffix = "extratime"
    return home, away, suffix


def _parse_match_row(
    row: list[Any],
    season_start_year: int,
) -> LatviaMatch | None:
    if len(row) < 5:
        return None

    date_text = BeautifulSoup(str(row[0]), "html.parser").get_text(" ", strip=True)
    time_text = BeautifulSoup(str(row[1]), "html.parser").get_text(" ", strip=True) or None

    home_soup = BeautifulSoup(str(row[2]), "html.parser")
    away_soup = BeautifulSoup(str(row[4]), "html.parser")
    score_soup = BeautifulSoup(str(row[3]), "html.parser")

    home_anchor = home_soup.select_one("a")
    away_anchor = away_soup.select_one("a")
    score_anchor = score_soup.select_one("a")
    if not home_anchor or not away_anchor or not score_anchor:
        return None

    home_team = (home_anchor.get("title") or home_anchor.get_text(" ", strip=True)).replace("\xa0", " ").strip()
    away_team = (away_anchor.get("title") or away_anchor.get_text(" ", strip=True)).replace("\xa0", " ").strip()

    proto_href = score_anchor.get("href")
    if not proto_href:
        return None
    proto_url = urljoin(BASE_URL, proto_href)

    id_match = re.search(r"/proto/(\d+)-", proto_url)
    if not id_match:
        return None
    game_id = int(id_match.group(1))

    home_goals, away_goals, status = _extract_score(str(row[3]))
    result_string = None
    if home_goals is not None and away_goals is not None:
        result_string = f"{home_goals}:{away_goals}"

    game_date = None
    dm_match = re.match(r"(\d{1,2})\.(\d{1,2})", date_text)
    if dm_match:
        day = int(dm_match.group(1))
        month = int(dm_match.group(2))
        year = season_start_year if month >= 7 else season_start_year + 1
        game_date = datetime(year, month, day).strftime("%Y-%m-%d")

    return LatviaMatch(
        game_id=game_id,
        proto_url=proto_url,
        home_team=home_team,
        away_team=away_team,
        game_date=game_date,
        game_start_time=time_text,
        result_string=result_string,
        ingame_status=status,
    )


def _fetch_calendar_matches(
    session: requests.Session,
    calendar_url: str,
    season_start_year: int,
    phase: str = "regular-season",
) -> list[LatviaMatch]:
    page_response = session.get(calendar_url, timeout=30)
    page_response.raise_for_status()
    page_html = page_response.text

    season_id = _extract_season_id(page_html)
    group = _parse_group_from_url(calendar_url)
    game_types = _extract_game_types(page_html, phase=phase)

    matches: dict[int, LatviaMatch] = {}
    for game_type in game_types:
        months = _fetch_month_options(
            session=session,
            calendar_url=calendar_url,
            season_id=season_id,
            group=group,
            game_type=game_type,
        )
        for month in months:
            response = session.post(
                AJAX_CALENDAR_URL,
                data={
                    "sEcho": "1",
                    "iColumns": "7",
                    "iDisplayStart": "0",
                    "iDisplayLength": "500",
                    "url": "https://www.floorball.lv/lv",
                    "menu": "chempionats",
                    "filtrs_grupa": group,
                    "filtrs_sezona": str(season_id),
                    "filtrs_spelu_veids": game_type,
                    "filtrs_menesis": month,
                    "filtrs_komanda": "all",
                    "filtrs_majas_viesi": "all",
                },
                headers={"Referer": calendar_url},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            for row in payload.get("aaData", []):
                match = _parse_match_row(row=row, season_start_year=season_start_year)
                if match:
                    matches[match.game_id] = match
    return sorted(matches.values(), key=lambda m: m.game_id)


def _period_and_sortkey(total_time: str, period_hint: int | None) -> tuple[int, str]:
    mm, ss = total_time.split(":", 1)
    total_min = int(mm)
    sec = int(ss)
    if period_hint:
        period = period_hint
    elif total_min >= 60:
        period = 4
    elif total_min >= 40:
        period = 3
    elif total_min >= 20:
        period = 2
    else:
        period = 1
    minute_in_period = max(0, total_min - (period - 1) * 20)
    return period, f"{period}-{minute_in_period:02d}:{sec:02d}"


def _map_penalty_type(text: str) -> str:
    lowered = text.lower()
    if "10" in lowered:
        return "penalty_10"
    if "2+2" in lowered:
        return "penalty_2and2"
    if "5" in lowered:
        return "penalty_5"
    if "ms" in lowered:
        return "penalty_ms_full"
    return "penalty_2"


def _parse_proto_events(session: requests.Session, match: LatviaMatch) -> list[dict[str, Any]]:
    response = session.get(match.proto_url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    events_table = soup.select_one("table.event_list")
    if not events_table:
        return []

    current_home = 0
    current_away = 0
    current_period_hint: int | None = None
    rows: list[dict[str, Any]] = []

    for tr in events_table.select("tr"):
        cells = tr.find_all("td")
        if len(cells) != 4:
            continue
        cell_class = (cells[0].get("class") or ["both"])[0]
        if cell_class == "both":
            marker = cells[3].get_text(" ", strip=True).lower()
            if "1. periods" in marker:
                current_period_hint = 1
            elif "2. periods" in marker:
                current_period_hint = 2
            elif "3. periods" in marker:
                current_period_hint = 3
            elif "pagarinājums" in marker:
                current_period_hint = 4
            elif "pēcspēles metieni" in marker or "bullīši" in marker:
                current_period_hint = 5
            continue

        time_text = cells[0].get_text(" ", strip=True)
        if not re.match(r"^\d{1,2}:\d{2}$", time_text):
            continue

        event_label = cells[1].get_text(" ", strip=True)
        score_text = cells[2].get_text(" ", strip=True)
        details = cells[3].get_text(" ", strip=True)
        team = match.home_team if cell_class == "maj" else match.away_team

        period, sortkey = _period_and_sortkey(time_text, current_period_hint)

        event_type = None
        penalty_type = None
        goal_type = None

        if "Vārti" in event_label:
            event_type = "goal"
            goal_type = "goal"
            score_match = re.search(r"(\d+)\s*-\s*(\d+)", score_text)
            if score_match:
                current_home = int(score_match.group(1))
                current_away = int(score_match.group(2))
        elif "Sods" in event_label:
            event_type = "penalty"
            penalty_type = _map_penalty_type(details)

        if not event_type:
            continue

        rows.append(
            {
                "event_type": event_type,
                "event_team": team,
                "period": period,
                "sortkey": sortkey,
                "game_id": match.game_id,
                "home_team_name": match.home_team,
                "away_team_name": match.away_team,
                "home_goals": current_home,
                "guest_goals": current_away,
                "goal_type": goal_type,
                "penalty_type": penalty_type,
                "game_date": match.game_date,
                "game_start_time": match.game_start_time,
                "game_status": "Played",
                "ingame_status": match.ingame_status,
                "result_string": match.result_string,
            }
        )

    return rows


def scrape_competition(
    calendar_urls: list[str],
    output_path: str,
    season_start_year: int,
    phase: str = "regular-season",
) -> pd.DataFrame:
    session = _new_session()
    all_matches: list[LatviaMatch] = []
    for calendar_url in calendar_urls:
        all_matches.extend(_fetch_calendar_matches(session, calendar_url, season_start_year, phase=phase))

    unique_matches: dict[int, LatviaMatch] = {m.game_id: m for m in all_matches}
    rows: list[dict[str, Any]] = []
    for match in tqdm(sorted(unique_matches.values(), key=lambda m: m.game_id), desc="latvia matches"):
        rows.extend(_parse_proto_events(session, match))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    return df


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--calendar_url", action="append", required=True)
    parser.add_argument("--season_start_year", type=int, required=True)
    parser.add_argument("--phase", type=str, default="regular-season")
    parser.add_argument("--output_path", type=str, default="data/data_latvia.csv")
    return parser.parse_args()


def main():
    args = parse_args()
    scrape_competition(
        calendar_urls=args.calendar_url,
        output_path=args.output_path,
        season_start_year=args.season_start_year,
        phase=args.phase,
    )


if __name__ == "__main__":
    main()
