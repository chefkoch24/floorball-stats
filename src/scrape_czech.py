import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from src.scheduled_games import build_scheduled_game_row


BASE_URL = "https://www.ceskyflorbal.cz"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "cs-CZ,cs;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": BASE_URL,
}


@dataclass
class MatchSummary:
    match_id: int
    home_team: str
    away_team: str
    score_text: str | None
    status: str | None
    round_name: str | None
    game_date: str | None
    game_start_time: str | None


def _build_url_variants(url: str) -> list[str]:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    variants: list[str] = []
    # Keep original URL first.
    variants.append(url)
    # locale=en can be blocked on some edge nodes; fallback to locale=cs.
    if query.get("locale") == "en":
        q_cs = dict(query)
        q_cs["locale"] = "cs"
        variants.append(urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q_cs), parts.fragment)))
    # Also try without locale parameter.
    if "locale" in query:
        q_no_locale = dict(query)
        q_no_locale.pop("locale", None)
        variants.append(urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q_no_locale), parts.fragment)))
    # Deduplicate while preserving order.
    seen = set()
    deduped = []
    for candidate in variants:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def _get_html(url: str, session: requests.Session, timeout: int = 30) -> str:
    variants = _build_url_variants(url)
    last_error: Exception | None = None
    for candidate in variants:
        for attempt in range(3):
            try:
                resp = session.get(candidate, timeout=timeout)
                if resp.status_code == 403:
                    raise requests.HTTPError(f"403 for {candidate}", response=resp)
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as exc:
                last_error = exc
                if attempt < 2:
                    sleep(0.8 * (attempt + 1))
                    continue
                break
    if last_error:
        raise last_error
    raise requests.RequestException(f"Failed to fetch {url}")


def _extract_attendance(soup: BeautifulSoup) -> int | None:
    text = soup.get_text(" ", strip=True)
    patterns = [
        r"divák[ůu]\s*:\s*(\d+)",
        r"návštěv[a-zá]*\s*:\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1))
    return None


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


def _parse_time(date_text: str | None) -> str | None:
    if not date_text:
        return None
    match = re.search(r"(\d{1,2}:\d{2})", date_text)
    if not match:
        return None
    return match.group(1)


def _is_playoff_round(round_name: str | None) -> bool:
    if not round_name:
        return False
    normalized = round_name.lower()
    playoff_markers = (
        "osmifin",
        "čtvrtfin",
        "ctvrtfin",
        "semifin",
        "superfin",
        "play-off",
        "playoff",
    )
    return any(marker in normalized for marker in playoff_markers)


def _is_playout_round(round_name: str | None) -> bool:
    if not round_name:
        return False
    normalized = round_name.lower()
    playout_markers = (
        "play-down",
        "play down",
        "playdown",
        "play-out",
        "play out",
        "playout",
    )
    return any(marker in normalized for marker in playout_markers)


def fetch_match_list(
    schedule_url: str,
    season_start_year: int,
    session: requests.Session | None = None,
) -> list[MatchSummary]:
    sess = session or requests.Session()
    soup = BeautifulSoup(_get_html(schedule_url, sess), "html.parser")
    matches = []
    for match_div in soup.select("div.Match"):
        score_anchor = match_div.select_one(".Match-score a")
        start_time_anchor = match_div.select_one(".Match-startTime a")
        match_anchor = score_anchor or start_time_anchor
        match_id = None
        score_text = _clean_text(score_anchor.get_text()) if score_anchor else None
        if match_anchor and match_anchor.has_attr("href"):
            match = re.search(r"/match/detail/default/(\d+)", match_anchor["href"])
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
                game_date=_parse_date(date_text, season_start_year),
                game_start_time=_parse_time(date_text),
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


def _parse_scorer_details(text: str | None) -> tuple[str | None, str | None]:
    cleaned = _clean_text(text)
    if not cleaned:
        return None, None
    cleaned = re.sub(r"^\d+\s*:\s*\d+\s*", "", cleaned).strip(" -")
    if not cleaned:
        return None, None
    match = re.match(r"(?P<scorer>.+?)(?:\s*\((?P<assist>[^)]+)\))?$", cleaned)
    if not match:
        return cleaned, None
    scorer_name = _clean_text(match.group("scorer"))
    assist_name = _clean_text(match.group("assist"))
    if assist_name in {"", "()"}:
        assist_name = None
    return scorer_name, assist_name


def _parse_penalty_player(lines: list[str]) -> str | None:
    cleaned_lines = [_clean_text(line) for line in lines]
    cleaned_lines = [line for line in cleaned_lines if line]
    if len(cleaned_lines) >= 2:
        return cleaned_lines[1]
    if not cleaned_lines:
        return None
    cleaned = re.sub(r"^\d+\s*:\s*\d+\s*", "", cleaned_lines[0]).strip(" -")
    cleaned = re.sub(r"^\d\+?\d?\b", "", cleaned).strip(" -")
    return cleaned or None


def _build_goal_detail_lookup(soup: BeautifulSoup) -> dict[tuple[str, str], tuple[str | None, str | None]]:
    lookup: dict[tuple[str, str], tuple[str | None, str | None]] = {}
    pattern = re.compile(
        r"vstřelil\s+#?\d+\s+(?P<scorer>.+?)(?:,\s*asistoval\s+#?\d+\s+(?P<assist>.+?))?\s*\((?P<score>\d+:\d+)\)",
        re.I,
    )
    for cell in soup.find_all("td"):
        text = _clean_text(cell.get_text(" ", strip=True))
        if not text or "vstřelil" not in text.lower():
            continue
        match = pattern.search(text)
        if not match:
            continue
        detail_row = cell.find_parent("tr")
        if detail_row is None:
            continue
        previous_row = detail_row.find_previous_sibling("tr")
        if previous_row is None:
            continue
        previous_text = _clean_text(previous_row.get_text(" ", strip=True)) or ""
        time_match = re.search(r"(\d{1,2}:\d{2})", previous_text)
        if not time_match:
            continue
        time_text = time_match.group(1)
        score_text = match.group("score")
        lookup[(time_text, score_text)] = (
            _clean_text(match.group("scorer")),
            _clean_text(match.group("assist")),
        )
    return lookup


def _parse_event_rows(
    event_block: Any,
    goal_detail_lookup: dict[tuple[str, str], tuple[str | None, str | None]],
    event_team: str,
    period_label: str,
    home_team: str,
    away_team: str,
    game_id: int,
    game_date: str | None,
    game_start_time: str | None,
    attendance: int | None,
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
        right_lines = [_clean_text(line) for line in right.get_text("\n").splitlines()]
        right_lines = [line for line in right_lines if line]
        right_text = " ".join(right_lines)

        time_match = re.search(r"(\d{1,2}):(\d{2})", left_text)
        minute = int(time_match.group(1)) if time_match else 0
        second = int(time_match.group(2)) if time_match else 0
        sortkey = f"{period}-{minute:02d}:{second:02d}"
        time_text = f"{minute:02d}:{second:02d}"

        score_match = re.search(r"(\d+)\s*:\s*(\d+)", right_text)
        home_goals = int(score_match.group(1)) if score_match else None
        away_goals = int(score_match.group(2)) if score_match else None
        score_text = f"{home_goals}:{away_goals}" if score_match else None

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
            "game_start_time": game_start_time,
            "attendance": attendance,
            "game_status": None,
            "ingame_status": None,
            "result_string": result_string,
            "scorer_name": None,
            "assist_name": None,
            "scorer_number": None,
            "assist_number": None,
            "penalty_player_name": None,
        }
        if penalty_type is None:
            scorer_name, assist_name = _parse_scorer_details(right_text)
            detailed_names = goal_detail_lookup.get((time_text, score_text)) if score_text else None
            if detailed_names:
                detailed_scorer, detailed_assist = detailed_names
                scorer_name = detailed_scorer or scorer_name
                assist_name = detailed_assist or assist_name
            row_data["scorer_name"] = scorer_name
            row_data["assist_name"] = assist_name
        else:
            row_data["penalty_player_name"] = _parse_penalty_player(right_lines)
        rows.append(row_data)
    return rows


def _parse_match_meta_time(soup: BeautifulSoup) -> str | None:
    text = soup.get_text(" ", strip=True)
    match = re.search(r"\b(\d{1,2}:\d{2})\b", text)
    if not match:
        return None
    return match.group(1)


def _parse_match_venue_info(match_id: int, session: requests.Session) -> tuple[str | None, str | None]:
    """Read venue name and address from Czech match info page."""
    info_url = f"{BASE_URL}/match/detail/info/{match_id}?locale=cs"
    try:
        info_soup = BeautifulSoup(_get_html(info_url, session), "html.parser")
    except requests.RequestException:
        return None, None

    venue_name = None
    venue_link = info_soup.select_one("a.MatchCenter-placeView")
    if venue_link:
        venue_name = _clean_text(venue_link.get_text(" ", strip=True))

    venue_address = None
    for row in info_soup.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        label = (_clean_text(cells[0].get_text(" ", strip=True)) or "").lower()
        if "adresa" in label:
            venue_address = _clean_text(cells[1].get_text(" ", strip=True))
            break

    return venue_name, venue_address


def fetch_match_events(
    match_id: int,
    game_date: str | None,
    game_start_time: str | None,
    status: str | None,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    sess = session or requests.Session()
    url = f"{BASE_URL}/match/detail/match/{match_id}?locale=en"
    soup = BeautifulSoup(_get_html(url, sess), "html.parser")

    home_team = _clean_text(soup.select_one(".MatchHeader-home .MatchHeader-normalName") and soup.select_one(".MatchHeader-home .MatchHeader-normalName").get_text()) or "n.a."
    away_team = _clean_text(soup.select_one(".MatchHeader-quest .MatchHeader-normalName") and soup.select_one(".MatchHeader-quest .MatchHeader-normalName").get_text()) or "n.a."
    score_text = _clean_text(soup.select_one(".MatchHeader-score") and soup.select_one(".MatchHeader-score").get_text())
    home_goals, away_goals, suffix = _parse_score(score_text)
    result_string = f"{home_goals}:{away_goals}" if home_goals is not None and away_goals is not None else None
    game_start_time = game_start_time or _parse_match_meta_time(soup)
    attendance = _extract_attendance(soup)
    venue_name, venue_address = _parse_match_venue_info(match_id, sess)

    events: list[dict[str, Any]] = []
    goal_detail_lookup = _build_goal_detail_lookup(soup)
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
                    goal_detail_lookup=goal_detail_lookup,
                    event_team=event_team,
                    period_label=period_label,
                    home_team=home_team,
                    away_team=away_team,
                    game_id=match_id,
                    game_date=game_date,
                    game_start_time=game_start_time,
                    attendance=attendance,
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
                    "game_start_time": game_start_time,
                    "attendance": attendance,
                    "game_status": None,
                    "ingame_status": None,
                    "result_string": result_string,
                    "scorer_name": None,
                    "assist_name": None,
                    "scorer_number": None,
                    "assist_number": None,
                    "penalty_player_name": None,
                    "venue": venue_name,
                    "venue_address": venue_address,
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
                    "game_start_time": game_start_time,
                    "attendance": attendance,
                    "game_status": None,
                    "ingame_status": None,
                    "result_string": result_string,
                    "scorer_name": None,
                    "assist_name": None,
                    "scorer_number": None,
                    "assist_number": None,
                    "penalty_player_name": None,
                    "venue": venue_name,
                    "venue_address": venue_address,
                }
            )

    for event in events:
        event["venue"] = venue_name
        event["venue_address"] = venue_address

    if not events:
        scheduled_row = build_scheduled_game_row(
            game_id=match_id,
            home_team=home_team,
            away_team=away_team,
            game_date=game_date,
            game_start_time=game_start_time,
            attendance=attendance,
            game_status=status or "Scheduled",
            result_string=result_string,
        )
        scheduled_row["venue"] = venue_name
        scheduled_row["venue_address"] = venue_address
        return [scheduled_row]

    return events


def scrape_competition(
    schedule_urls: list[str],
    output_path: str,
    season_start_year: int,
    include_unplayed: bool = False,
    phase: str = "regular-season",
) -> pd.DataFrame:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    all_matches: list[MatchSummary] = []
    for url in schedule_urls:
        all_matches.extend(fetch_match_list(url, season_start_year, session=session))

    rows: list[dict[str, Any]] = []
    for match in tqdm(all_matches, desc="matches"):
        if _is_playout_round(match.round_name):
            continue
        if phase == "playoffs" and not _is_playoff_round(match.round_name):
            continue
        if phase == "regular-season" and _is_playoff_round(match.round_name):
            continue
        if not include_unplayed and match.status and match.status.lower() != "played":
            continue
        rows.extend(
            fetch_match_events(
                match.match_id,
                match.game_date,
                match.game_start_time,
                match.status,
                session=session,
            )
        )

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
        phase="regular-season",
    )


if __name__ == "__main__":
    main()
