"""Cup games on team pages.

A team page of a league season gets ``article.cup_games``: the games its team played in the
national cup of that season (round, opponent, result, report link), read from the cup game
articles (category ``<prefix><season>-cup``). Teams without cup games get none, so the page
shows no cup section. Cups never change the team's figures: the table values, power play,
goal difference, calendar and form still come from the league games only (src/competitions.py).
"""

from __future__ import annotations

from pelican import signals

from rosters import team_key


def _value(article, key, default=""):
    value = getattr(article, key, default)
    if isinstance(value, list):
        value = value[0] if value else default
    return default if value is None else value


def _int(article, key):
    try:
        return int(float(str(_value(article, key, 0)).strip()))
    except (TypeError, ValueError):
        return 0


def cup_row(game, team):
    """One cup game seen from ``team``'s side."""
    home = team_key(_value(game, "home_team")) == team_key(team)
    scheduled = str(_value(game, "game_state", "played")).strip().lower() == "scheduled"
    own, other = ("home", "away") if home else ("away", "home")
    goals_for, goals_against = _int(game, f"{own}_goals"), _int(game, f"{other}_goals")
    result_string = str(_value(game, "result_string"))
    shootout = _int(game, "home_goals_in_penalty_shootout") + _int(game, "away_goals_in_penalty_shootout") > 0 or "n.P." in result_string
    overtime = not shootout and (_int(game, "home_goals_in_overtime") + _int(game, "away_goals_in_overtime") > 0 or "n.V." in result_string)
    return {
        "date": getattr(game, "date", None),
        "round": str(_value(game, "tournament_stage_label")),
        "group": str(_value(game, "tournament_group")),
        "opponent": str(_value(game, f"{other}_team")),
        "home": home,
        "scheduled": scheduled,
        "start_time": _value(game, "start_time"),
        "category": game.category.shortname if getattr(game, "category", None) else "",
        "goals_for": goals_for,
        "goals_against": goals_against,
        "outcome": "" if scheduled else ("W" if goals_for > goals_against else "L" if goals_for < goals_against else "D"),
        "decision": "PS" if shootout else "OT" if overtime else "",
        "competition": str(_value(game, "competition_name")),
        "url": game.url,
    }


def build(cup_games_by_season):
    """{team page category: {team key: [rows]}} for the teams that played in the cup."""
    rows = {}
    for season, games in cup_games_by_season.items():
        per_team = rows.setdefault(season, {})
        for game in games:
            for side in ("home_team", "away_team"):
                name = _value(game, side)
                if name:
                    per_team.setdefault(team_key(name), []).append(cup_row(game, name))
        for entries in per_team.values():
            entries.sort(key=lambda row: (row["date"] is None, row["date"]))
    return rows


def collect(generator):
    cup_games = {}
    for article in generator.articles:
        category = article.category.shortname if getattr(article, "category", None) else ""
        if category.endswith("-cup") and str(_value(article, "type")) == "game":
            # The cup of "ch-26-27-cup" belongs to the team pages of "ch-26-27-regular-season".
            cup_games.setdefault(f"{category[:-len('-cup')]}-regular-season", []).append(article)
    if not cup_games:
        return
    rows = build(cup_games)
    for article in generator.articles:
        if str(_value(article, "type")) != "team" or not getattr(article, "category", None):
            continue
        entries = rows.get(article.category.shortname, {}).get(team_key(_value(article, "team") or _value(article, "title")))
        if entries:
            article.cup_games = entries


def register():
    signals.article_generator_finalized.connect(collect)
