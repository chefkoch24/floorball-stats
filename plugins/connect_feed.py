"""Pelican plugin: connect-feed.json, the live stats block on floorballconnect.com.

The main site (connect/) is built rarely, the stats site after every data refresh. So the
stats build writes a small JSON with what the main site's home page shows, and that page
loads it in the browser: games around today with win chances, the top of every league's
power ranking and the top scorers across leagues, for men and women. netlify.toml lets
the main site read it (CORS).

It runs after all article generators finished, so the insights and leaders plugins have
put LEAGUE_INSIGHTS and LEADERBOARDS into the context whatever order they ran in.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

from pelican import signals

FEED = "connect-feed.json"
DAYS_BACK, DAYS_AHEAD = 3, 21  # the page picks today or the next matchday from these
POWER_TOP = 5
LEADERS_TOP = 5
BOARDS = ("points", "goals")


def _value(article, key, default=""):
    value = getattr(article, key, None)
    if value is None:
        value = article.metadata.get(key, default)
    return default if value is None else value


def _goals(article, key):
    value = _value(article, key, "")
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def games(articles, settings, filters, today: date) -> list[dict]:
    season = settings.get("CURRENT_SEASON", "")
    site = settings.get("SITEURL", "")
    rows = []
    for article in articles:
        category = article.category.shortname if getattr(article, "category", None) else ""
        if _value(article, "type") != "game" or season not in category or not getattr(article, "date", None):
            continue
        day = article.date.date() if isinstance(article.date, datetime) else article.date
        if not (today - timedelta(days=DAYS_BACK) <= day <= today + timedelta(days=DAYS_AHEAD)):
            continue
        league = filters["league_context"](category) or {}
        home, away = str(_value(article, "home_team", "n.a.")), str(_value(article, "away_team", "n.a."))
        ps = (_goals(article, "home_goals_in_penalty_shootout") or 0) + (_goals(article, "away_goals_in_penalty_shootout") or 0)
        ot = (_goals(article, "home_goals_in_overtime") or 0) + (_goals(article, "away_goals_in_overtime") or 0)
        chance = getattr(article, "win_probability", None)
        played = _value(article, "game_state", "scheduled") == "played"
        rows.append({
            "date": day.isoformat(),
            "day": day.strftime("%a %d %b"),
            "time": filters["fmt_time"](_value(article, "start_time", ""), "TBD"),
            "league": filters["category2string"](category),
            "division": league.get("division", "men"),
            "home": home, "away": away,
            "homeCrest": filters["crest_index"](home), "awayCrest": filters["crest_index"](away),
            "homeInitials": filters["team_initials"](home), "awayInitials": filters["team_initials"](away),
            "homeGoals": _goals(article, "home_goals"), "awayGoals": _goals(article, "away_goals"),
            "decision": "PS" if ps else ("OT" if ot else ""),
            "state": "played" if played else "scheduled",
            "homeChance": chance["home_label"] if chance and not played else None,
            "awayChance": chance["away_label"] if chance and not played else None,
            "url": f"{site}/{article.url}",
        })
    rows.sort(key=lambda row: (row["date"], row["time"], row["league"]))
    return rows


def power(league_insights, settings, filters) -> dict[str, list[dict]]:
    season = settings.get("CURRENT_SEASON", "")
    site = settings.get("SITEURL", "")
    out: dict[str, list[dict]] = {"men": [], "women": []}
    for league in settings.get("LEAGUES", []):
        category = f"{league['prefix']}{season}-regular-season"
        block = (league_insights.get(category) or {}).get("power")
        if not block or not block.get("rows"):
            continue
        out.setdefault(league["division"], []).append({
            "league": league["title"].split(" · ")[-1],
            "country": league["name"],
            "url": f"{site}/category/{category}.html",
            "teams": [
                {"rank": row["power_rank"], "team": row["team"], "rating": row["rating"], "trend": row["trend"],
                 "crest": filters["crest_index"](row["team"]), "initials": filters["team_initials"](row["team"]),
                 "url": f"{site}/{row['url']}"}
                for row in block["rows"][:POWER_TOP]
            ],
        })
    return out


def leaders(leaderboards, settings) -> dict[str, list[dict]]:
    site = settings.get("SITEURL", "")
    out = {}
    for division, data in (leaderboards or {}).items():
        boards = []
        for board in data.get("boards", []):
            if board["key"] not in BOARDS:
                continue
            boards.append({
                "key": board["key"], "title": board["title"], "unit": board["unit"],
                "entries": [
                    {"rank": entry["rank"], "name": entry["name"], "team": entry["team"], "value": entry["value"],
                     "code": entry.get("code", ""), "crest": entry.get("crest"), "initials": entry.get("initials", ""),
                     "url": f"{site}/{entry['url']}" if entry.get("url") else ""}
                    for entry in board["entries"][:LEADERS_TOP]
                ],
            })
        out[division] = boards
    return out


def write(generator, writer) -> None:
    settings = generator.settings
    if not hasattr(generator, "articles"):
        return
    context = generator.context
    filters = settings["JINJA_FILTERS"]
    feed = {
        "generated": datetime.now().isoformat(timespec="minutes"),
        "stats_url": settings.get("SITEURL", ""),
        "games": games(generator.articles, settings, filters, date.today()),
        "power": power(context.get("LEAGUE_INSIGHTS") or {}, settings, filters),
        "leaders": leaders(context.get("LEADERBOARDS"), settings),
    }
    path = os.path.join(generator.output_path, FEED)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(feed, handle, ensure_ascii=False, separators=(",", ":"))


def register():
    signals.article_writer_finalized.connect(write)
