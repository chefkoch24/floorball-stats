import argparse
import json
from pathlib import Path
import re
import sys
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.scrape_wfc import (
    AUTH_API_ROOT as WFC_AUTH_API_ROOT,
    _auth_headers as _wfc_auth_headers,
    _load_auth_from_env as _load_wfc_auth_from_env,
    _normalize_team_name as _normalize_wfc_team_name,
    _refresh_access_token as _refresh_wfc_access_token,
)
from src.utils import generate_player_uid, normalize_slug_fragment


FILE_PATTERN = re.compile(r"^data_((?P<prefix>[a-z]{2,3})-)?(?P<years>\d{2}-\d{2}|\d{4})_(?P<phase>regular_season|playoffs)\.csv$")
STARTKIT_URL = "https://api.innebandy.se/StatsAppApi/api/startkit"
DEFAULT_API_ROOT = "https://api.innebandy.se/v2/api/"
GERMANY_API_BASE = "https://saisonmanager.de/api/v2/"
CZECH_BASE_URL = "https://www.ceskyflorbal.cz"
SWISS_RENDER_URL = "https://www.swissunihockey.ch/renderengine/load_view.php"
WFC_GAME_LINEUPS_URL = f"{WFC_AUTH_API_ROOT}/magazinegameviewapi/initgamelineups"
LEAGUE_INFO = {
    "": {"source_system": "germany", "league": "Germany"},
    "ch": {"source_system": "switzerland", "league": "Switzerland"},
    "cz": {"source_system": "czech-republic", "league": "Czech Republic"},
    "fi": {"source_system": "finland", "league": "Finland"},
    "lv": {"source_system": "latvia", "league": "Latvia"},
    "se": {"source_system": "sweden", "league": "Sweden"},
    "sk": {"source_system": "slovakia", "league": "Slovakia"},
    "wfc": {"source_system": "wfc", "league": "IFF WFC"},
}


def _player_stats_export_name(prefix: str) -> str:
    normalized = prefix or "de"
    return f"player_stats_{normalized}.csv"


def _normalize_prefix_tokens(raw: str | None) -> set[str]:
    if not raw:
        return set()
    aliases = {
        "de": "",
        "ger": "",
        "germany": "",
    }
    normalized: set[str] = set()
    for token in str(raw).split(","):
        cleaned = token.strip().lower()
        if not cleaned:
            continue
        normalized.add(aliases.get(cleaned, cleaned))
    return normalized


def _load_existing_player_stats_exports(
    directory: Path,
    include_prefixes: set[str],
    output_csv: str,
) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    target_name = Path(output_csv).name
    prefixes = sorted(include_prefixes if include_prefixes else LEAGUE_INFO.keys(), key=lambda value: (value != "", value))
    for prefix in prefixes:
        export_name = _player_stats_export_name(prefix)
        if export_name == target_name:
            continue
        export_path = directory / export_name
        if not export_path.exists():
            continue
        try:
            frame = pd.read_csv(export_path)
        except Exception:
            continue
        if frame.empty:
            continue
        frames.append(frame)
    return frames


def _name_style_score(name: str) -> int:
    tokens = [token for token in re.split(r"\s+", str(name or "").strip()) if token]
    score = 0
    for token in tokens:
        if token.isupper():
            score += 0
        elif token.islower():
            score += 1
        elif token[0].isupper() and token[1:].islower():
            score += 3
        else:
            score += 2
    return score


def _normalize_player_name_for_identity(value: str | None) -> str:
    cleaned = " ".join(str(value or "").split()).strip()
    if not cleaned:
        return ""
    if cleaned.lower() in {"nan", "none", "null", "n/a", "na", "-"}:
        return ""
    cleaned = re.sub(
        r"\s+(?:bez\s+asistence|z\s+trestn[eé]ho\s+stř[íi]len[íi])$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip(" ,-")


def _phase_from_file_token(token: str) -> str:
    return "regular-season" if token == "regular_season" else token


def _season_token(prefix: str, years: str) -> str:
    return f"{prefix}-{years}" if prefix else years


def _canonical_player_uid(player: str) -> str:
    cleaned_player = _normalize_player_name_for_identity(player)
    normalized_player = normalize_slug_fragment(cleaned_player)
    return generate_player_uid("player", normalized_player or cleaned_player.lower())


def _row_slug(player: str, season: str, phase: str) -> str:
    return normalize_slug_fragment(f"{player}-{season}-{phase}")


def _aggregate_team_names(values: pd.Series) -> str:
    seen = []
    for value in values.astype(str):
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.append(cleaned)
    return " / ".join(seen)


def _aggregate_source_ids(values: pd.Series) -> str:
    seen = []
    for value in values.astype(str):
        cleaned = value.strip()
        if not cleaned or cleaned == "0" or cleaned in seen:
            continue
        seen.append(cleaned)
    return seen[0] if len(seen) == 1 else ",".join(seen)


def _aggregate_player_name(values: pd.Series) -> str:
    cleaned_values = [str(value).strip() for value in values.astype(str) if str(value).strip()]
    if not cleaned_values:
        return ""
    counts: dict[str, int] = {}
    for name in cleaned_values:
        counts[name] = counts.get(name, 0) + 1
    return max(
        counts.keys(),
        key=lambda name: (
            counts[name],
            _name_style_score(name),
            -len(name),
            name,
        ),
    )


def _to_name_case(token: str) -> str:
    token = str(token or "").strip()
    if not token:
        return ""
    return token[0].upper() + token[1:].lower()


def _harmonize_slovakia_player_names(stats: pd.DataFrame) -> pd.DataFrame:
    frame = stats.copy()
    players = (
        frame.get("player", pd.Series(dtype=str))
        .fillna("")
        .astype(str)
        .str.replace(r"\s+\.\s+", " ", regex=True)
        .str.strip()
    )

    pair_votes: dict[tuple[str, str], dict[str, int]] = {}
    for name in players.tolist():
        parts = [part for part in name.split() if part]
        if len(parts) != 2:
            continue
        first, second = parts
        first_key = first.lower()
        second_key = second.lower()
        pair_key = tuple(sorted([first_key, second_key]))
        votes = pair_votes.setdefault(pair_key, {})

        # Only change order when the source gives actual evidence.
        # A fully upper token is typically the surname marker, which means the
        # other token should become the canonical first name.
        if first.isupper() and not second.isupper():
            votes[second_key] = votes.get(second_key, 0) + 4
            votes[first_key] = votes.get(first_key, 0) + 1
        elif second.isupper() and not first.isupper():
            votes[first_key] = votes.get(first_key, 0) + 4
            votes[second_key] = votes.get(second_key, 0) + 1
        else:
            # Otherwise keep the observed order instead of guessing, so
            # legitimate two-token identities are not flipped by default.
            votes[first_key] = votes.get(first_key, 0) + 2

    preferred_first: dict[tuple[str, str], str] = {}
    for pair_key, votes in pair_votes.items():
        preferred_first[pair_key] = max(votes.keys(), key=lambda token: (votes[token], token))

    def _normalize_name(name: str) -> str:
        cleaned = " ".join(str(name or "").split()).strip()
        if not cleaned:
            return ""
        parts = [part for part in cleaned.split() if part]
        if len(parts) == 2:
            first, second = parts
            first_key = first.lower()
            second_key = second.lower()
            pair_key = tuple(sorted([first_key, second_key]))
            chosen_first = preferred_first.get(pair_key)
            if chosen_first == second_key:
                first, second = second, first
            return f"{_to_name_case(first)} {_to_name_case(second)}"
        normalized_tokens = []
        for token in parts:
            if token.isupper() or token.islower():
                normalized_tokens.append(_to_name_case(token))
            else:
                normalized_tokens.append(token)
        return " ".join(normalized_tokens)

    frame["player"] = players.map(_normalize_name)
    frame["player_uid"] = frame["player"].map(_canonical_player_uid)
    return frame


def _finalize_rows(stats: pd.DataFrame, season: str, phase: str, league: str, source_system: str) -> pd.DataFrame:
    if stats.empty:
        return pd.DataFrame(
            columns=[
                "player_uid",
                "source_system",
                "source_player_id",
                "source_person_id",
                "player",
                "title",
                "slug",
                "category",
                "team",
                "league",
                "season",
                "phase",
                "rank",
                "games",
                "goals",
                "assists",
                "points",
                "pim",
                "penalties",
            ]
        )

    prepared_stats = stats.copy()
    prepared_stats["player"] = (
        prepared_stats.get("player", pd.Series(dtype=str))
        .fillna("")
        .astype(str)
        .map(_normalize_player_name_for_identity)
    )
    prepared_stats = prepared_stats[prepared_stats["player"] != ""].copy()
    if source_system == "slovakia":
        prepared_stats = _harmonize_slovakia_player_names(prepared_stats)
    # Identity must always be derived from canonicalized names.
    prepared_stats["player_uid"] = prepared_stats["player"].map(_canonical_player_uid)

    grouped = (
        prepared_stats.groupby(["player_uid"], as_index=False)
        .agg(
            {
                "player": _aggregate_player_name,
                "team": _aggregate_team_names,
                "games": "sum",
                "goals": "sum",
                "assists": "sum",
                "points": "sum",
                "pim": "sum",
                "penalties": "sum",
                "source_player_id": _aggregate_source_ids,
                "source_person_id": _aggregate_source_ids,
            }
        )
        .sort_values(["points", "goals", "assists", "player"], ascending=[False, False, False, True])
        .reset_index(drop=True)
    )
    grouped["source_system"] = source_system
    grouped["title"] = grouped["player"]
    grouped["slug"] = grouped["player"].apply(lambda player: _row_slug(player, season, phase))
    grouped["category"] = f"{season}-{phase}, players"
    grouped["league"] = league
    grouped["season"] = season
    grouped["phase"] = phase
    grouped["rank"] = grouped.index + 1
    return grouped[
        [
            "player_uid",
            "source_system",
            "source_player_id",
            "source_person_id",
            "player",
            "title",
            "slug",
            "category",
            "team",
            "league",
            "season",
            "phase",
            "rank",
            "games",
            "goals",
            "assists",
            "points",
            "pim",
            "penalties",
        ]
    ]


def _rows_from_event_csv(path: Path, season: str, phase: str, league: str, source_system: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required_columns = {"event_type", "event_team", "game_id", "scorer_name", "assist_name", "penalty_player_name"}
    if not required_columns.issubset(df.columns):
        return _finalize_rows(pd.DataFrame(), season=season, phase=phase, league=league, source_system=source_system)

    goals_df = df[df["event_type"] == "goal"].copy()
    goals_df["scorer_name"] = (
        goals_df["scorer_name"].fillna("").astype(str).map(_normalize_player_name_for_identity)
    )
    goals_df["assist_name"] = (
        goals_df["assist_name"].fillna("").astype(str).map(_normalize_player_name_for_identity)
    )
    goals_df = goals_df[goals_df["scorer_name"] != ""]

    penalties_df = df[df["event_type"] == "penalty"].copy()
    penalties_df["penalty_player_name"] = (
        penalties_df["penalty_player_name"].fillna("").astype(str).map(_normalize_player_name_for_identity)
    )
    penalties_df = penalties_df[penalties_df["penalty_player_name"] != ""]

    goals = goals_df.groupby(["scorer_name", "event_team"]).size().reset_index(name="goals")
    goals = goals.rename(columns={"scorer_name": "player", "event_team": "team"})

    assists_raw = goals_df[goals_df["assist_name"] != ""][["assist_name", "event_team"]].copy()
    assists = assists_raw.groupby(["assist_name", "event_team"]).size().reset_index(name="assists")
    assists = assists.rename(columns={"assist_name": "player", "event_team": "team"})

    penalties = penalties_df.groupby(["penalty_player_name", "event_team"]).size().reset_index(name="penalties")
    penalties = penalties.rename(columns={"penalty_player_name": "player", "event_team": "team"})

    stats = goals.merge(assists, on=["player", "team"], how="outer")
    stats = stats.merge(penalties, on=["player", "team"], how="outer").fillna(0)

    gp_goals = goals_df[["game_id", "event_team", "scorer_name"]].rename(
        columns={"event_team": "team", "scorer_name": "player"}
    )
    gp_assists = goals_df[goals_df["assist_name"] != ""][["game_id", "event_team", "assist_name"]].rename(
        columns={"event_team": "team", "assist_name": "player"}
    )
    gp_pen = penalties_df[["game_id", "event_team", "penalty_player_name"]].rename(
        columns={"event_team": "team", "penalty_player_name": "player"}
    )
    gp = pd.concat([gp_goals, gp_assists, gp_pen], ignore_index=True).drop_duplicates()
    gp = gp.groupby(["player", "team"]).size().reset_index(name="games")

    stats = stats.merge(gp, on=["player", "team"], how="left")
    stats["player"] = stats["player"].fillna("").astype(str).str.strip()
    stats["team"] = stats["team"].fillna("").astype(str).str.strip()
    stats = stats[stats["player"] != ""].copy()
    for col in ["games", "goals", "assists", "penalties"]:
        stats[col] = stats[col].fillna(0).astype(int)
    stats["points"] = stats["goals"] + stats["assists"]
    stats["pim"] = stats["penalties"] * 2
    stats["player_uid"] = stats["player"].apply(_canonical_player_uid)
    stats["source_player_id"] = ""
    stats["source_person_id"] = ""

    return _finalize_rows(stats, season=season, phase=phase, league=league, source_system=source_system)


def _load_league_configs_for(backend: str, season: str, phase: str) -> list[dict]:
    configs: list[dict] = []
    for cfg_path in sorted(Path("config/leagues").glob("*.json")):
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(cfg.get("backend") or "").strip().lower() != backend.lower():
            continue
        if str(cfg.get("season") or "").strip() != season:
            continue
        if str(cfg.get("phase") or "").strip() != phase:
            continue
        configs.append(cfg)
    return configs


def _rows_from_germany_lineups(match_ids: list[int], season: str, phase: str) -> pd.DataFrame:
    records: list[dict] = []
    session = requests.Session()
    for match_id in sorted(set(match_ids)):
        response = session.get(f"{GERMANY_API_BASE}games/{match_id}", timeout=30)
        response.raise_for_status()
        game = response.json()
        home_team = str(game.get("home_team_name") or "").strip()
        away_team = str(game.get("guest_team_name") or "").strip()
        if not home_team or not away_team:
            continue
        players = game.get("players") or {}
        for side_key, team_name in [("home", home_team), ("guest", away_team)]:
            for player in players.get(side_key) or []:
                first_name = str(player.get("player_firstname") or "").strip()
                last_name = str(player.get("player_name") or "").strip()
                player_name = " ".join(part for part in [first_name, last_name] if part).strip()
                if not player_name:
                    continue
                records.append(
                    {
                        "player_uid": _canonical_player_uid(player_name),
                        "source_player_id": str(int(player.get("player_id") or 0) or ""),
                        "source_person_id": "",
                        "player": player_name,
                        "team": team_name,
                        "games": 1,
                        "goals": 0,
                        "assists": 0,
                        "points": 0,
                        "pim": 0,
                        "penalties": 0,
                    }
                )
    stats = pd.DataFrame.from_records(records)
    return _finalize_rows(stats, season=season, phase=phase, league="Germany", source_system="germany")


def _normalize_finland_player_name(text: str) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    cleaned = re.sub(r"\s+[CV]$", "", cleaned)
    return cleaned.strip(" ,-")


def _normalize_roster_player_name(text: str | None) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"\(\d+\)$", "", cleaned).strip(" -")
    if "," in cleaned:
        last_name, first_name = [part.strip() for part in cleaned.split(",", 1)]
        if first_name and last_name:
            cleaned = f"{first_name} {last_name}"
    return cleaned.strip()


def _extract_finland_match_players_data(html: str) -> list[str]:
    marker = "var matchPlayersData = "
    start = html.find(marker)
    if start < 0:
        return []
    start += len(marker)
    end = html.find(";</script>", start)
    if end < 0:
        return []
    payload = html[start:end].strip()
    try:
        data = json.loads(payload)
    except Exception:
        return []
    names: list[str] = []
    for value in (data or {}).values():
        player_name = _normalize_finland_player_name((value or {}).get("name"))
        if player_name:
            names.append(player_name)
    return names


def _rows_from_finland_rosters(matches: pd.DataFrame, season: str, phase: str) -> pd.DataFrame:
    from src.scrape_finland import _get as _fin_get, _parse_match_cards

    configs = _load_league_configs_for("finland", season, phase)
    schedule_urls: list[str] = []
    for cfg in configs:
        schedule_urls.extend((cfg.get("finland") or {}).get("schedule_urls") or [])
    schedule_urls = list(dict.fromkeys(schedule_urls))
    if not schedule_urls:
        return _finalize_rows(pd.DataFrame(), season=season, phase=phase, league="Finland", source_system="finland")

    match_url_by_id: dict[str, str] = {}
    for url in schedule_urls:
        cards = _parse_match_cards(_fin_get(url))
        for card in cards:
            match_url_by_id[str(card.match_id)] = card.url

    records: list[dict] = []
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; FloorballStats/1.0; +https://fliiga.com/)"})
    lineup_titles = {"1. kenttä", "2. kenttä", "3. kenttä", "4. kenttä", "maalivahdit"}

    for row in matches.itertuples(index=False):
        game_id = str(getattr(row, "game_id"))
        home_team = str(getattr(row, "home_team_name", "") or "").strip()
        away_team = str(getattr(row, "away_team_name", "") or "").strip()
        if not home_team or not away_team:
            continue
        rel_url = match_url_by_id.get(game_id)
        if not rel_url:
            continue
        url = rel_url if rel_url.startswith("http") else f"https://fliiga.com{rel_url}"
        response = session.get(url, timeout=30, allow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        lineup_tables: list = []
        titles: list[str] = []
        for table in soup.select("table"):
            if "sortable-table" in (table.get("class") or []):
                continue
            heading = table.find_previous("h4")
            heading_text = " ".join((heading.get_text(" ", strip=True) if heading else "").lower().split())
            if heading_text in lineup_titles:
                lineup_tables.append(table)
                titles.append(heading_text)
        if len(lineup_tables) >= 2:
            split_idx = None
            for idx in range(1, len(titles)):
                if titles[idx].startswith("1."):
                    split_idx = idx
                    break
            if split_idx is None:
                split_idx = len(lineup_tables) // 2

            for side, tables in [("home", lineup_tables[:split_idx]), ("away", lineup_tables[split_idx:])]:
                team_name = home_team if side == "home" else away_team
                seen_names: set[str] = set()
                for table in tables:
                    for tr in table.select("tr"):
                        cells = tr.find_all("td")
                        if len(cells) < 2:
                            continue
                        player_name = _normalize_finland_player_name(cells[1].get_text(" ", strip=True))
                        if not player_name or player_name in seen_names:
                            continue
                        seen_names.add(player_name)
                        records.append(
                            {
                                "player_uid": _canonical_player_uid(player_name),
                                "source_player_id": "",
                                "source_person_id": "",
                                "player": player_name,
                                "team": team_name,
                                "games": 1,
                                "goals": 0,
                                "assists": 0,
                                "points": 0,
                                "pim": 0,
                                "penalties": 0,
                            }
                        )
        else:
            # Current F-liiga pages often embed players in JS payload instead of static lineup tables.
            for player_name in _extract_finland_match_players_data(response.text):
                records.append(
                    {
                        "player_uid": _canonical_player_uid(player_name),
                        "source_player_id": "",
                        "source_person_id": "",
                        "player": player_name,
                        # Team assignment is not exposed in this payload; keep empty and rely on event rows for team labels.
                        "team": "",
                        "games": 1,
                        "goals": 0,
                        "assists": 0,
                        "points": 0,
                        "pim": 0,
                        "penalties": 0,
                    }
                )

    stats = pd.DataFrame.from_records(records)
    return _finalize_rows(stats, season=season, phase=phase, league="Finland", source_system="finland")


def _fetch_czech_roster_html(match_id: int, session: requests.Session) -> str:
    response = session.get(f"{CZECH_BASE_URL}/match/detail/roster/{match_id}", timeout=30)
    response.raise_for_status()
    return response.text


def _extract_player_id_from_href(href: str) -> str:
    match = re.search(r"/person/detail/player/(\d+)", href)
    return match.group(1) if match else ""


def _extract_roster_players(container) -> list[tuple[str, str]]:
    players: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for anchor in container.select("a[href*='/person/detail/player/']"):
        href = str(anchor.get("href") or "")
        player_name = str(anchor.get_text(" ", strip=True) or "").strip()
        if not player_name:
            continue
        source_person_id = _extract_player_id_from_href(href)
        key = (player_name, source_person_id)
        if key in seen:
            continue
        seen.add(key)
        players.append((player_name, source_person_id))
    return players


def _rows_from_czech_rosters(matches: pd.DataFrame, season: str, phase: str, league: str, source_system: str) -> pd.DataFrame:
    records: list[dict] = []
    session = requests.Session()
    for row in matches.itertuples(index=False):
        match_id = int(row.game_id)
        home_team = str(getattr(row, "home_team_name", "") or "").strip()
        away_team = str(getattr(row, "away_team_name", "") or "").strip()
        if not home_team or not away_team:
            continue
        html = _fetch_czech_roster_html(match_id, session=session)
        soup = BeautifulSoup(html, "html.parser")
        home_container = soup.select_one("#tab-domaci")
        away_container = soup.select_one("#tab-hoste")
        if home_container is None or away_container is None:
            continue
        for player_name, source_person_id in _extract_roster_players(home_container):
            records.append(
                {
                    "player_uid": _canonical_player_uid(player_name),
                    "source_player_id": "",
                    "source_person_id": source_person_id,
                    "player": player_name,
                    "team": home_team,
                    "games": 1,
                    "goals": 0,
                    "assists": 0,
                    "points": 0,
                    "pim": 0,
                    "penalties": 0,
                }
            )
        for player_name, source_person_id in _extract_roster_players(away_container):
            records.append(
                {
                    "player_uid": _canonical_player_uid(player_name),
                    "source_player_id": "",
                    "source_person_id": source_person_id,
                    "player": player_name,
                    "team": away_team,
                    "games": 1,
                    "goals": 0,
                    "assists": 0,
                    "points": 0,
                    "pim": 0,
                    "penalties": 0,
                }
            )
    stats = pd.DataFrame.from_records(records)
    return _finalize_rows(stats, season=season, phase=phase, league=league, source_system=source_system)


def _rows_from_slovakia_rosters(matches: pd.DataFrame, season: str, phase: str) -> pd.DataFrame:
    from src.scrape_slovakia import _new_session, _parse_schedule_matches, _results_url_from_date_url

    configs = _load_league_configs_for("slovakia", season, phase)
    schedule_urls: list[str] = []
    for cfg in configs:
        schedule_urls.extend((cfg.get("slovakia") or {}).get("schedule_urls") or [])
    schedule_urls = list(dict.fromkeys(schedule_urls))
    if not schedule_urls:
        return _finalize_rows(pd.DataFrame(), season=season, phase=phase, league="Slovakia", source_system="slovakia")

    session = _new_session()
    lineup_url_by_id: dict[int, str] = {}
    for schedule_url in schedule_urls:
        resolved = [schedule_url]
        alt = _results_url_from_date_url(schedule_url)
        if alt:
            resolved.append(alt)
        for url in resolved:
            html = session.get(url, timeout=30).text
            for match in _parse_schedule_matches(html, schedule_url):
                lineup_url_by_id[match.match_id] = match.match_url.replace("/overview", "/LineUp")

    records: list[dict] = []
    for row in matches.itertuples(index=False):
        game_id = int(getattr(row, "game_id"))
        home_team = str(getattr(row, "home_team_name", "") or "").strip()
        away_team = str(getattr(row, "away_team_name", "") or "").strip()
        lineup_url = lineup_url_by_id.get(game_id)
        if not lineup_url or not home_team or not away_team:
            continue
        response = session.get(lineup_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        tables = soup.select("table.table-hover")
        if len(tables) < 2:
            continue
        for side, table in [("home", tables[0]), ("away", tables[1])]:
            team_name = home_team if side == "home" else away_team
            seen_names: set[str] = set()
            for anchor in table.select("a[href*='/stats/players/'][href*='/player/']"):
                player_name = _normalize_roster_player_name(anchor.get_text(" ", strip=True))
                if not player_name or player_name in seen_names:
                    continue
                seen_names.add(player_name)
                href = str(anchor.get("href") or "")
                match = re.search(r"/player/(\d+)", href)
                source_person_id = match.group(1) if match else ""
                records.append(
                    {
                        "player_uid": _canonical_player_uid(player_name),
                        "source_player_id": "",
                        "source_person_id": source_person_id,
                        "player": player_name,
                        "team": team_name,
                        "games": 1,
                        "goals": 0,
                        "assists": 0,
                        "points": 0,
                        "pim": 0,
                        "penalties": 0,
                    }
                )
    stats = pd.DataFrame.from_records(records)
    return _finalize_rows(stats, season=season, phase=phase, league="Slovakia", source_system="slovakia")


def _rows_from_latvia_rosters(matches: pd.DataFrame, season: str, phase: str) -> pd.DataFrame:
    from src.scrape_latvia import _fetch_calendar_matches, _new_session

    configs = _load_league_configs_for("latvia", season, phase)
    calendar_url = None
    season_start_year = None
    for cfg in configs:
        lat = cfg.get("latvia") or {}
        calendar_url = calendar_url or ((lat.get("calendar_urls") or [None])[0] if isinstance(lat.get("calendar_urls"), list) else None)
        calendar_url = calendar_url or lat.get("calendar_url")
        season_start_year = season_start_year or lat.get("season_start_year")
    if not calendar_url or not season_start_year:
        return _finalize_rows(pd.DataFrame(), season=season, phase=phase, league="Latvia", source_system="latvia")

    session = _new_session()
    calendar_matches = _fetch_calendar_matches(
        session=session,
        calendar_url=calendar_url,
        season_start_year=int(season_start_year),
        phase=phase,
    )
    proto_url_by_id = {m.game_id: m.proto_url for m in calendar_matches}

    records: list[dict] = []
    for row in matches.itertuples(index=False):
        game_id = int(getattr(row, "game_id"))
        home_team = str(getattr(row, "home_team_name", "") or "").strip()
        away_team = str(getattr(row, "away_team_name", "") or "").strip()
        proto_url = proto_url_by_id.get(game_id)
        if not proto_url or not home_team or not away_team:
            continue
        response = session.get(proto_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        roster_tables = soup.select("table.speletaji")
        if len(roster_tables) < 2:
            continue
        team_names = [home_team, away_team]
        wrap_first_row = soup.select_one("table.speletaji_wrap tr")
        if wrap_first_row:
            wrap_cells = [c.get_text(" ", strip=True) for c in wrap_first_row.find_all("td")]
            if len(wrap_cells) >= 2:
                team_names = [wrap_cells[0] or home_team, wrap_cells[1] or away_team]
        for idx, table in enumerate(roster_tables[:2]):
            team_name = team_names[idx]
            seen_names: set[str] = set()
            for tr in table.select("tr"):
                cells = tr.find_all("td")
                if len(cells) < 2:
                    continue
                player_text = cells[1].get_text(" ", strip=True)
                player_name = _normalize_roster_player_name(re.sub(r"#\s*\d+.*$", "", player_text).strip())
                if not player_name or player_name in seen_names:
                    continue
                seen_names.add(player_name)
                records.append(
                    {
                        "player_uid": _canonical_player_uid(player_name),
                        "source_player_id": "",
                        "source_person_id": "",
                        "player": player_name,
                        "team": team_name,
                        "games": 1,
                        "goals": 0,
                        "assists": 0,
                        "points": 0,
                        "pim": 0,
                        "penalties": 0,
                    }
                )
    stats = pd.DataFrame.from_records(records)
    return _finalize_rows(stats, season=season, phase=phase, league="Latvia", source_system="latvia")


def _fetch_swiss_players_block(game_id: int, is_home: bool, session: requests.Session) -> str:
    params = {
        "view": "short",
        "game_id": str(game_id),
        "is_home": "1" if is_home else "0",
        "block_type": "players",
        "ID_Block": "SU_2886",
        "locale": "de-CH",
    }
    response = session.get(SWISS_RENDER_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.text


def _extract_swiss_players(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    players: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in soup.select("table.su-result tbody tr"):
        player_cell = row.select_one("td:nth-of-type(3)")
        if player_cell is None:
            continue
        anchor = player_cell.select_one("a")
        player_name = (anchor or player_cell).get_text(" ", strip=True)
        player_name = str(player_name or "").strip()
        if not player_name:
            continue
        href = str(anchor.get("href") if anchor else "")
        match = re.search(r"player_id=(\d+)", href)
        source_person_id = match.group(1) if match else ""
        key = (player_name, source_person_id)
        if key in seen:
            continue
        seen.add(key)
        players.append(key)
    return players


def _rows_from_swiss_rosters(matches: pd.DataFrame, season: str, phase: str) -> pd.DataFrame:
    records: list[dict] = []
    session = requests.Session()
    for row in matches.itertuples(index=False):
        game_id = int(row.game_id)
        home_team = str(getattr(row, "home_team_name", "") or "").strip()
        away_team = str(getattr(row, "away_team_name", "") or "").strip()
        if not home_team or not away_team:
            continue
        # is_home=1 on the Swiss API returns the visiting (away) roster; swap to match home/away labels.
        home_html = _fetch_swiss_players_block(game_id=game_id, is_home=False, session=session)
        away_html = _fetch_swiss_players_block(game_id=game_id, is_home=True, session=session)
        for player_name, source_person_id in _extract_swiss_players(home_html):
            records.append(
                {
                    "player_uid": _canonical_player_uid(player_name),
                    "source_player_id": "",
                    "source_person_id": source_person_id,
                    "player": player_name,
                    "team": home_team,
                    "games": 1,
                    "goals": 0,
                    "assists": 0,
                    "points": 0,
                    "pim": 0,
                    "penalties": 0,
                }
            )
        for player_name, source_person_id in _extract_swiss_players(away_html):
            records.append(
                {
                    "player_uid": _canonical_player_uid(player_name),
                    "source_player_id": "",
                    "source_person_id": source_person_id,
                    "player": player_name,
                    "team": away_team,
                    "games": 1,
                    "goals": 0,
                    "assists": 0,
                    "points": 0,
                    "pim": 0,
                    "penalties": 0,
                }
            )
    stats = pd.DataFrame.from_records(records)
    return _finalize_rows(stats, season=season, phase=phase, league="Switzerland", source_system="switzerland")


def _merge_finalized_rows(
    rows: list[pd.DataFrame], season: str, phase: str, league: str, source_system: str
) -> pd.DataFrame:
    compact: list[pd.DataFrame] = []
    for frame in rows:
        if frame is None or frame.empty:
            continue
        compact.append(
            frame[
                [
                    "player_uid",
                    "source_player_id",
                    "source_person_id",
                    "player",
                    "team",
                    "games",
                    "goals",
                    "assists",
                    "points",
                    "pim",
                    "penalties",
                ]
            ].copy()
        )
    if not compact:
        return _finalize_rows(pd.DataFrame(), season=season, phase=phase, league=league, source_system=source_system)
    stats = pd.concat(compact, ignore_index=True)
    stats["player"] = (
        stats.get("player", pd.Series(dtype=str))
        .fillna("")
        .astype(str)
        .map(_normalize_player_name_for_identity)
    )
    stats = stats[stats["player"] != ""].copy()
    if source_system == "slovakia":
        # Harmonize cross-source name ordering (e.g. "Rantala Juho" vs "Juho Rantala")
        # before grouping, otherwise games can be doubled for the same player.
        stats = _harmonize_slovakia_player_names(stats)
    # Identity must always be derived from canonicalized names.
    stats["player_uid"] = stats["player"].map(_canonical_player_uid)
    for col in ["games", "goals", "assists", "points", "pim", "penalties"]:
        stats[col] = stats[col].fillna(0).astype(int)

    # Merge multiple sources (events + lineups) without double-counting.
    # Each source is already season-aggregated per player, so merge by player_uid only.
    # Team labels may differ slightly between sources; merging by team can inflate games.
    # Use max (not sum) for stats: some lineup sources (e.g. Sweden) already carry
    # cumulative season totals, so summing with event-derived totals would double-count.
    # When one source has 0 and the other has the real value, max still picks correctly.
    stats = (
        stats.groupby(["player_uid"], as_index=False)
        .agg(
            {
                "player": _aggregate_player_name,
                "team": _aggregate_team_names,
                "games": "max",
                "goals": "max",
                "assists": "max",
                "pim": "max",
                "penalties": "max",
                "source_player_id": _aggregate_source_ids,
                "source_person_id": _aggregate_source_ids,
            }
        )
        .reset_index(drop=True)
    )
    stats["points"] = stats["goals"] + stats["assists"]
    return _finalize_rows(stats, season=season, phase=phase, league=league, source_system=source_system)


def _get_api_root_and_headers() -> tuple[str, dict[str, str]]:
    payload = requests.get(STARTKIT_URL, timeout=30).json()
    api_root = payload.get("apiRoot") or DEFAULT_API_ROOT
    token = payload.get("accessToken")
    if not token:
        raise RuntimeError("Startkit response did not include accessToken")
    return api_root, {"Authorization": f"Bearer {token}"}


def _fetch_match_lineups(match_id: int, api_root: str, headers: dict[str, str]) -> dict:
    response = requests.get(f"{api_root}matches/{match_id}/lineups", headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def _safe_int(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            return None


def _find_first_nested_list(payload: object, candidate_keys: tuple[str, ...]) -> list[dict]:
    if isinstance(payload, dict):
        for key in candidate_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        for value in payload.values():
            result = _find_first_nested_list(value, candidate_keys)
            if result:
                return result
    elif isinstance(payload, list):
        for item in payload:
            result = _find_first_nested_list(item, candidate_keys)
            if result:
                return result
    return []


def _extract_wfc_player_name(row: dict) -> str:
    for key in ("Name", "PlayerName", "FullName", "DisplayName"):
        value = _normalize_player_name_for_identity(row.get(key))
        if value:
            return value
    first_name = str(row.get("FirstName") or "").strip()
    last_name = str(row.get("LastName") or "").strip()
    return _normalize_player_name_for_identity(" ".join(part for part in [first_name, last_name] if part))


def _fetch_wfc_game_lineups(game_id: int, auth) -> dict:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(
                WFC_GAME_LINEUPS_URL,
                params={"GameID": game_id},
                headers=_wfc_auth_headers(auth.access_token),
                timeout=30,
            )
            if response.status_code == 401:
                last_error = requests.HTTPError(f"WFC lineups returned HTTP 401 for game {game_id}.")
                if attempt < 2:
                    _refresh_wfc_access_token(auth)
                    time.sleep(1 + attempt)
                    continue
                break
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(1 + attempt)
                continue
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
                continue
            break
    if last_error:
        raise last_error
    return {}


def _rows_from_wfc_lineups(matches: pd.DataFrame, season: str, phase: str) -> pd.DataFrame:
    auth = _load_wfc_auth_from_env()
    if auth is None:
        return _finalize_rows(pd.DataFrame(), season=season, phase=phase, league="IFF WFC", source_system="wfc")

    records: list[dict] = []
    failed_game_ids: list[int] = []
    for match in matches.to_dict("records"):
        game_id = _safe_int(match.get("game_id"))
        if game_id is None:
            continue
        try:
            payload = _fetch_wfc_game_lineups(game_id, auth)
        except Exception as exc:
            failed_game_ids.append(game_id)
            print(f"warning: failed to fetch WFC lineups for game {game_id}: {exc}", file=sys.stderr)
            continue
        home_team_name = _normalize_wfc_team_name(match.get("home_team_name")) or str(match.get("home_team_name") or "").strip()
        away_team_name = _normalize_wfc_team_name(match.get("away_team_name")) or str(match.get("away_team_name") or "").strip()

        home_roster = payload.get("HomeTeamGameTeamRoster") if isinstance(payload, dict) else {}
        away_roster = payload.get("AwayTeamGameTeamRoster") if isinstance(payload, dict) else {}
        home_lineup = payload.get("HomeTeamLineUp") if isinstance(payload, dict) else {}
        away_lineup = payload.get("AwayTeamLineUp") if isinstance(payload, dict) else {}

        side_lists = [
            (
                home_team_name,
                [
                    *([item for item in (home_roster.get("Players") or []) if isinstance(item, dict)] if isinstance(home_roster, dict) else []),
                    *([item for item in (home_roster.get("Substitutes") or []) if isinstance(item, dict)] if isinstance(home_roster, dict) else []),
                    *([item for item in (home_lineup.get("GameLineUpPlayers") or []) if isinstance(item, dict)] if isinstance(home_lineup, dict) else []),
                    *_find_first_nested_list(payload, ("HomeTeamPlayers", "HomePlayers")),
                ],
            ),
            (
                away_team_name,
                [
                    *([item for item in (away_roster.get("Players") or []) if isinstance(item, dict)] if isinstance(away_roster, dict) else []),
                    *([item for item in (away_roster.get("Substitutes") or []) if isinstance(item, dict)] if isinstance(away_roster, dict) else []),
                    *([item for item in (away_lineup.get("GameLineUpPlayers") or []) if isinstance(item, dict)] if isinstance(away_lineup, dict) else []),
                    *_find_first_nested_list(payload, ("AwayTeamPlayers", "AwayPlayers")),
                ],
            ),
        ]

        for team_name, player_rows in side_lists:
            for row in player_rows:
                player_name = _extract_wfc_player_name(row)
                if not player_name or not team_name:
                    continue
                records.append(
                    {
                        "game_id": str(game_id),
                        "player_uid": _canonical_player_uid(player_name),
                        "source_player_id": str(row.get("PlayerID") or row.get("MemberID") or "").strip(),
                        "source_person_id": str(row.get("PersonID") or "").strip(),
                        "player": player_name,
                        "team": team_name,
                        "games": 1,
                        "goals": 0,
                        "assists": 0,
                        "points": 0,
                        "pim": 0,
                        "penalties": 0,
                    }
                )

    if failed_game_ids:
        print(
            f"warning: WFC lineup fetch skipped {len(failed_game_ids)} game(s) for {season} {phase}: {', '.join(str(game_id) for game_id in failed_game_ids)}",
            file=sys.stderr,
        )
    stats = pd.DataFrame.from_records(records).drop_duplicates(
        subset=["game_id", "player_uid", "team", "source_player_id", "source_person_id"]
    )
    return _finalize_rows(stats, season=season, phase=phase, league="IFF WFC", source_system="wfc")


def _rows_from_sweden_lineups(match_ids: list[int], season: str, phase: str) -> pd.DataFrame:
    api_root, headers = _get_api_root_and_headers()
    records: list[dict] = []
    for match_id in sorted(set(match_ids)):
        lineups = _fetch_match_lineups(match_id, api_root=api_root, headers=headers)
        team_name_by_id = {
            int(lineups.get("HomeTeamID") or 0): str(lineups.get("HomeTeam") or "").strip(),
            int(lineups.get("AwayTeamID") or 0): str(lineups.get("AwayTeam") or "").strip(),
        }
        for side in ["HomeTeamPlayers", "AwayTeamPlayers"]:
            for row in lineups.get(side, []) or []:
                player = str(row.get("Name") or "").strip()
                if not player:
                    continue
                team_id = int(row.get("TeamID") or 0)
                team_name = team_name_by_id.get(team_id) or str(row.get("LicensedAssociationName") or "").strip()
                goals = int(row.get("Goals") or 0)
                assists = int(row.get("Assists") or 0)
                points = int(row.get("Points") or goals + assists)
                pim = int(row.get("PenaltyMinutes") or 0)
                records.append(
                    {
                        "player_uid": _canonical_player_uid(player),
                        "source_player_id": str(int(row.get("PlayerID") or 0) or ""),
                        "source_person_id": str(int(row.get("PersonID") or 0) or ""),
                        "player": player,
                        "team": team_name,
                        "games": int(row.get("Matches") or 0) or 1,
                        "goals": goals,
                        "assists": assists,
                        "points": points,
                        "pim": pim,
                        "penalties": pim // 2,
                    }
                )

    stats = pd.DataFrame.from_records(records)
    return _finalize_rows(stats, season=season, phase=phase, league="Sweden", source_system="sweden")


def _load_played_matches(path: Path, required_columns: list[str]) -> pd.DataFrame:
    available_columns = set(pd.read_csv(path, nrows=0).columns)
    missing_required = [column for column in required_columns if column not in available_columns]
    if missing_required:
        raise ValueError(f"Missing required columns {missing_required} in {path}")

    usecols = list(required_columns)
    if "game_status" in available_columns and "game_status" not in usecols:
        usecols.append("game_status")
    matches = pd.read_csv(path, usecols=usecols)
    if "game_status" in matches.columns:
        statuses = matches["game_status"].fillna("").astype(str).str.strip().str.lower()
        unplayed_statuses = {
            "scheduled",
            "postponed",
            "canceled",
            "cancelled",
            "not played",
            "to be played",
            "upcoming",
        }
        matches = matches[~statuses.isin(unplayed_statuses)]
    matches = matches.dropna(subset=required_columns).drop_duplicates(subset=["game_id"])
    return matches[required_columns]


def build_player_stats(data_dir: str, output_csv: str, season_prefixes: set[str] | None = None) -> int:
    directory = Path(data_dir)
    include_prefixes = season_prefixes or set()

    existing_exports = _load_existing_player_stats_exports(directory, include_prefixes, output_csv)
    export_target = Path(output_csv).name
    raw_prefixes_present: set[str] = set()
    for candidate in sorted(directory.glob("data_*.csv")):
        match = FILE_PATTERN.match(candidate.name)
        if not match:
            continue
        prefix = (match.group("prefix") or "").lower()
        if include_prefixes and prefix not in include_prefixes:
            continue
        if prefix in LEAGUE_INFO:
            raw_prefixes_present.add(prefix)

    missing_export_prefixes = {
        prefix
        for prefix in raw_prefixes_present
        if _player_stats_export_name(prefix) != export_target and not (directory / _player_stats_export_name(prefix)).exists()
    }

    all_rows: list[pd.DataFrame] = []
    if existing_exports:
        all_rows.extend(existing_exports)
    if existing_exports and not missing_export_prefixes:
        result = pd.concat(existing_exports, ignore_index=True)
        result = result.sort_values(
            ["season", "phase", "league", "points", "goals", "assists", "player"],
            ascending=[True, True, True, False, False, False, True],
        ).reset_index(drop=True)
        result.to_csv(output_csv, index=False)
        return len(result)

    for candidate in sorted(directory.glob("data_*.csv")):
        match = FILE_PATTERN.match(candidate.name)
        if not match:
            continue
        prefix = (match.group("prefix") or "").lower()
        if include_prefixes and prefix not in include_prefixes:
            continue
        if existing_exports and prefix not in missing_export_prefixes:
            continue
        years = match.group("years")
        phase_token = match.group("phase")
        info = LEAGUE_INFO.get(prefix)
        if not info:
            continue
        season = _season_token(prefix, years)
        phase = _phase_from_file_token(phase_token)

        if prefix == "se":
            try:
                match_ids = (
                    pd.read_csv(candidate, usecols=["game_id"])["game_id"]
                    .dropna()
                    .astype(int)
                    .drop_duplicates()
                    .tolist()
                )
                context_rows = _rows_from_sweden_lineups(match_ids, season=season, phase=phase)
            except Exception:
                context_rows = _rows_from_event_csv(
                    candidate,
                    season=season,
                    phase=phase,
                    league=info["league"],
                    source_system=info["source_system"],
                )
        elif prefix == "":
            event_rows = _rows_from_event_csv(
                candidate,
                season=season,
                phase=phase,
                league=info["league"],
                source_system=info["source_system"],
            )
            try:
                match_ids = (
                    pd.read_csv(candidate, usecols=["game_id"])["game_id"]
                    .dropna()
                    .astype(int)
                    .drop_duplicates()
                    .tolist()
                )
                lineup_rows = _rows_from_germany_lineups(match_ids=match_ids, season=season, phase=phase)
                context_rows = _merge_finalized_rows(
                    [event_rows, lineup_rows],
                    season=season,
                    phase=phase,
                    league=info["league"],
                    source_system=info["source_system"],
                )
            except Exception:
                context_rows = event_rows
        elif prefix == "cz":
            event_rows = _rows_from_event_csv(
                candidate,
                season=season,
                phase=phase,
                league=info["league"],
                source_system=info["source_system"],
            )
            try:
                matches = _load_played_matches(candidate, ["game_id", "home_team_name", "away_team_name"])
                roster_rows = _rows_from_czech_rosters(
                    matches,
                    season=season,
                    phase=phase,
                    league=info["league"],
                    source_system=info["source_system"],
                )
                context_rows = _merge_finalized_rows(
                    [event_rows, roster_rows],
                    season=season,
                    phase=phase,
                    league=info["league"],
                    source_system=info["source_system"],
                )
            except Exception:
                context_rows = event_rows
        elif prefix == "ch":
            event_rows = _rows_from_event_csv(
                candidate,
                season=season,
                phase=phase,
                league=info["league"],
                source_system=info["source_system"],
            )
            try:
                matches = _load_played_matches(candidate, ["game_id", "home_team_name", "away_team_name"])
                roster_rows = _rows_from_swiss_rosters(matches=matches, season=season, phase=phase)
                context_rows = _merge_finalized_rows(
                    [event_rows, roster_rows],
                    season=season,
                    phase=phase,
                    league=info["league"],
                    source_system=info["source_system"],
                )
            except Exception:
                context_rows = event_rows
        elif prefix == "fi":
            event_rows = _rows_from_event_csv(
                candidate,
                season=season,
                phase=phase,
                league=info["league"],
                source_system=info["source_system"],
            )
            try:
                matches = _load_played_matches(candidate, ["game_id", "home_team_name", "away_team_name"])
                roster_rows = _rows_from_finland_rosters(matches=matches, season=season, phase=phase)
                context_rows = _merge_finalized_rows(
                    [event_rows, roster_rows],
                    season=season,
                    phase=phase,
                    league=info["league"],
                    source_system=info["source_system"],
                )
            except Exception:
                context_rows = event_rows
        elif prefix == "sk":
            event_rows = _rows_from_event_csv(
                candidate,
                season=season,
                phase=phase,
                league=info["league"],
                source_system=info["source_system"],
            )
            try:
                matches = _load_played_matches(candidate, ["game_id", "home_team_name", "away_team_name"])
                roster_rows = _rows_from_slovakia_rosters(matches=matches, season=season, phase=phase)
                context_rows = _merge_finalized_rows(
                    [event_rows, roster_rows],
                    season=season,
                    phase=phase,
                    league=info["league"],
                    source_system=info["source_system"],
                )
            except Exception:
                context_rows = event_rows
        elif prefix == "lv":
            event_rows = _rows_from_event_csv(
                candidate,
                season=season,
                phase=phase,
                league=info["league"],
                source_system=info["source_system"],
            )
            try:
                matches = _load_played_matches(candidate, ["game_id", "home_team_name", "away_team_name"])
                roster_rows = _rows_from_latvia_rosters(matches=matches, season=season, phase=phase)
                context_rows = _merge_finalized_rows(
                    [event_rows, roster_rows],
                    season=season,
                    phase=phase,
                    league=info["league"],
                    source_system=info["source_system"],
                )
            except Exception:
                context_rows = event_rows
        elif prefix == "wfc":
            event_rows = _rows_from_event_csv(
                candidate,
                season=season,
                phase=phase,
                league=info["league"],
                source_system=info["source_system"],
            )
            try:
                matches = _load_played_matches(candidate, ["game_id", "home_team_name", "away_team_name"])
                lineup_rows = _rows_from_wfc_lineups(matches=matches, season=season, phase=phase)
                context_rows = _merge_finalized_rows(
                    [event_rows, lineup_rows],
                    season=season,
                    phase=phase,
                    league=info["league"],
                    source_system=info["source_system"],
                )
            except Exception:
                context_rows = event_rows
        else:
            context_rows = _rows_from_event_csv(
                candidate,
                season=season,
                phase=phase,
                league=info["league"],
                source_system=info["source_system"],
            )

        all_rows.append(context_rows)

    if not all_rows:
        raise RuntimeError(f"No league files found in {directory} matching pattern {FILE_PATTERN.pattern}")

    result = pd.concat(all_rows, ignore_index=True)
    result.to_csv(output_csv, index=False)
    return len(result)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build player stats CSV from all available season event files.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-csv", default="data/player_stats.csv")
    parser.add_argument(
        "--season-prefixes",
        default="",
        help="Optional comma-separated season prefixes to include (e.g. sk,fi,se,cz,ch,lv,de,wfc).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_player_stats(
        data_dir=args.data_dir,
        output_csv=args.output_csv,
        season_prefixes=_normalize_prefix_tokens(args.season_prefixes),
    )
    print(f"player-stats: wrote {rows} rows to {args.output_csv}")


if __name__ == "__main__":
    main()
