"""Links players and teams both ways.

Team pages get article.roster: the players of that team in the same league,
season and phase, read from the player stats page of that phase and sorted by
points. Player pages get article.team_page_url for the current team and
article.history_team_urls (one entry per history_rows_csv row, "" when no
team page exists). Leaderboard rows can use team_page_urls() the same way.
"""

from __future__ import annotations

import re

from pelican import signals
from unidecode import unidecode


def _value(article, key, default=None):
    value = getattr(article, key, default)
    if isinstance(value, list):
        value = value[0] if value else default
    return value


def _int(value):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def team_key(team):
    """Loose team name key: accents, case and punctuation do not matter."""
    return re.sub(r"[^a-z0-9]+", "", unidecode(str(team or "")).lower())


def parse_player_rows(csv):
    rows = []
    for raw in str(csv or "").split("||"):
        cols = raw.split("|")
        if len(cols) < 9 or not cols[2].strip():
            continue
        rows.append({
            "name": cols[2].strip(),
            "url": f"{cols[1].strip()}.html" if cols[1].strip() else "",
            "team": cols[3].strip(),
            "games": _int(cols[4]),
            "goals": _int(cols[5]),
            "assists": _int(cols[6]),
            "points": _int(cols[7]),
            "pim": _int(cols[8]),
        })
    return rows


def build_rosters(player_rows_by_phase):
    """{(phase key, team key): [player rows sorted by points]}."""
    rosters = {}
    for phase, rows in player_rows_by_phase.items():
        for row in rows:
            rosters.setdefault((phase, team_key(row["team"])), []).append(row)
    for players in rosters.values():
        players.sort(key=lambda r: (-r["points"], -r["goals"], -r["games"], r["name"]))
    return rosters


def collect(generator) -> None:
    player_rows = {}
    teams = []
    players = []
    for article in generator.articles:
        kind = str(_value(article, "type", "") or "")
        if kind == "player_stats":
            phase = str(_value(article, "season_phase_key", "") or "")
            if phase:
                player_rows.setdefault(phase, []).extend(parse_player_rows(_value(article, "player_rows_csv")))
        elif kind == "team" and article.category:
            teams.append(article)
        elif kind == "player":
            players.append(article)

    rosters = build_rosters(player_rows)
    # (phase key, team key) -> team page url, for links from players and leaderboards.
    team_pages = {}
    for article in teams:
        phase = article.category.shortname
        name = _value(article, "team", "") or _value(article, "title", "")
        key = (phase, team_key(name))
        team_pages[key] = article.url
        article.roster = rosters.get(key, [])

    for article in players:
        history = []
        for raw in str(_value(article, "history_rows_csv", "") or "").split("||"):
            cols = raw.split("|")
            if len(cols) >= 4:
                history.append(team_pages.get((f"{cols[0]}-{cols[1]}", team_key(cols[3])), ""))
            else:
                history.append("")
        article.history_team_urls = history
        season = _value(article, "current_season", "")
        article.team_page_url = team_pages.get(
            (f"{season}-regular-season", team_key(_value(article, "team", ""))), ""
        ) or next((url for url in history if url), "")

    generator.context["TEAM_PAGES"] = team_pages


def register() -> None:
    signals.article_generator_finalized.connect(collect)
