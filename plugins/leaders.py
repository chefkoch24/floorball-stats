"""Cross-league leaderboards for the leaders page (templates/leaders.html).

Reads the regular-season player stats pages and team pages of CURRENT_SEASON
for every league in LEAGUES and builds top lists per division (men, women):
player points, goals, assists, penalty minutes and points per game; team
power play, box play, scoring, goals against and penalties. The result is
exposed to templates as LEADERBOARDS.
"""

from __future__ import annotations

from pelican import signals

TOP = 10
# Rates need a few games so one strong night does not top a season list.
MIN_GAMES = 3
# Special-teams percentages need a minimum sample of power plays / box plays.
MIN_SPECIAL_TEAMS = 5


def _value(article, key, default=None):
    value = getattr(article, key, default)
    if isinstance(value, list):
        value = value[0] if value else default
    return value


def _number(value, default=0.0):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _player_rows(article, league, settings):
    crest_index = settings["JINJA_FILTERS"]["crest_index"]
    initials = settings["JINJA_FILTERS"]["team_initials"]
    rows = []
    for raw in str(_value(article, "player_rows_csv", "") or "").split("||"):
        cols = raw.split("|")
        if len(cols) < 9 or not cols[2].strip():
            continue
        games = int(_number(cols[4]))
        goals = int(_number(cols[5]))
        assists = int(_number(cols[6]))
        points = int(_number(cols[7]))
        pim = int(_number(cols[8]))
        team = cols[3].strip()
        rows.append({
            "name": cols[2].strip(),
            "url": f"{cols[1].strip()}.html",
            "team": team,
            "crest": crest_index(team),
            "initials": initials(team),
            "league": league["title"].split(" · ")[-1],
            "country": league["name"],
            "games": games,
            "goals": goals,
            "assists": assists,
            "points": points,
            "pim": pim,
            "ppg": points / games if games else 0.0,
        })
    return rows


def _team_row(article, league, settings):
    team = str(_value(article, "team", "") or _value(article, "title", "")).strip()
    return {
        "name": team,
        "url": article.url,
        "team": team,
        "crest": settings["JINJA_FILTERS"]["crest_index"](team),
        "initials": settings["JINJA_FILTERS"]["team_initials"](team),
        "league": league["title"].split(" · ")[-1],
        "country": league["name"],
        "games": int(_number(_value(article, "games"))),
        "pp": _number(_value(article, "powerplay_efficiency"), None),
        "pp_count": int(_number(_value(article, "powerplay"))),
        "bp": _number(_value(article, "boxplay_efficiency"), None),
        "bp_count": int(_number(_value(article, "boxplay"))),
        "gf": _number(_value(article, "goals_per_game"), None),
        "ga": _number(_value(article, "goals_against_per_game"), None),
        "pen": _number(_value(article, "penalties_per_game"), None),
    }


def _board(key, title, unit, kind, rows, value, sort_value, fmt, detail):
    ranked = sorted(rows, key=sort_value)[:TOP]
    entries = []
    for index, row in enumerate(ranked, start=1):
        entries.append({**row, "rank": index, "value": fmt(value(row)), "detail": detail(row)})
    return {"key": key, "title": title, "unit": unit, "kind": kind, "entries": entries}


def build_leaderboards(player_rows, team_rows):
    played = [row for row in player_rows if row["games"] > 0]
    rated = [row for row in played if row["games"] >= MIN_GAMES]
    teams = [row for row in team_rows if row["games"] > 0]
    whole = lambda v: str(int(v))
    two = lambda v: f"{v:.2f}"
    one = lambda v: f"{v:.1f}"
    games_detail = lambda row: f"{row['games']} GP"
    return [
        _board("points", "Points", "P", "player", played, lambda r: r["points"],
               lambda r: (-r["points"], -r["goals"], r["games"], r["name"]), whole,
               lambda r: f"{r['goals']} G · {r['assists']} A · {r['games']} GP"),
        _board("goals", "Goals", "G", "player", played, lambda r: r["goals"],
               lambda r: (-r["goals"], r["games"], r["name"]), whole, games_detail),
        _board("assists", "Assists", "A", "player", played, lambda r: r["assists"],
               lambda r: (-r["assists"], r["games"], r["name"]), whole, games_detail),
        _board("penalty-minutes", "Penalty minutes", "PIM", "player", [r for r in played if r["pim"] > 0], lambda r: r["pim"],
               lambda r: (-r["pim"], r["games"], r["name"]), whole, games_detail),
        _board("points-per-game", "Points per game", "P/GP", "player", rated, lambda r: r["ppg"],
               lambda r: (-r["ppg"], -r["points"], r["name"]), two,
               lambda r: f"{r['points']} P in {r['games']} GP"),
        _board("power-play", "Power play", "PP%", "team", [r for r in teams if r["pp"] is not None and r["pp_count"] >= MIN_SPECIAL_TEAMS],
               lambda r: r["pp"], lambda r: (-r["pp"], -r["pp_count"], r["name"]), one,
               lambda r: f"{r['pp_count']} power plays"),
        _board("box-play", "Box play", "BP%", "team", [r for r in teams if r["bp"] is not None and r["bp_count"] >= MIN_SPECIAL_TEAMS],
               lambda r: r["bp"], lambda r: (-r["bp"], -r["bp_count"], r["name"]), one,
               lambda r: f"{r['bp_count']} box plays"),
        _board("goals-per-game", "Goals per game", "GF/GP", "team", [r for r in teams if r["gf"] is not None],
               lambda r: r["gf"], lambda r: (-r["gf"], r["name"]), two, games_detail),
        _board("goals-against", "Fewest goals against", "GA/GP", "team", [r for r in teams if r["ga"] is not None],
               lambda r: r["ga"], lambda r: (r["ga"], r["name"]), two, games_detail),
        _board("penalties", "Penalties per game", "PEN/GP", "team", [r for r in teams if r["pen"] is not None],
               lambda r: r["pen"], lambda r: (-r["pen"], r["name"]), two, games_detail),
    ]


def collect(generator) -> None:
    settings = generator.settings
    season = settings.get("CURRENT_SEASON", "")
    league_context = settings["JINJA_FILTERS"]["league_context"]
    players = {"men": [], "women": []}
    teams = {"men": [], "women": []}
    leagues = {"men": set(), "women": set()}
    for article in generator.articles:
        kind = str(_value(article, "type", "") or "")
        if kind == "player_stats":
            key = str(_value(article, "season_phase_key", "") or "")
        elif kind == "team":
            key = article.category.shortname if article.category else ""
        else:
            continue
        context = league_context(key)
        # National leagues only, current season, regular season.
        if not context or context["season"] != season or context["phase"] != "regular-season":
            continue
        if not any(context["prefix"] == league["prefix"] for league in settings.get("LEAGUES", [])):
            continue
        division = context["division"]
        if kind == "player_stats":
            players[division].extend(_player_rows(article, context, settings))
        else:
            teams[division].append(_team_row(article, context, settings))
        leagues[division].add(context["title"].split(" · ")[-1])
    generator.context["LEADERBOARDS"] = {
        division: {
            "leagues": sorted(leagues[division]),
            "boards": build_leaderboards(players[division], teams[division]),
        }
        for division in ("men", "women")
    }


def register() -> None:
    signals.article_generator_finalized.connect(collect)
