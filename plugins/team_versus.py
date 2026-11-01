"""Direct comparison of two teams: one JSON per league for ``/head-to-head.html``.

Runs at build time on the published game articles, like ``insights``. Every league
gets ``head-to-head/<key>.json`` (key: category prefix without the dash, ``de`` for
Germany) with all pairs of teams that met in any tracked season and phase. The page
(``templates/team_versus.html``) loads one file for the chosen league and renders the
pair in the browser, so the build writes one file per league instead of one page per
pair (a league with 12 teams has 66 pairs). The calculation lives in
``src/team_versus.py``.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode

from pelican import signals

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import insights  # noqa: E402
from src import player_insights as pi  # noqa: E402
from src import power_rankings as pr  # noqa: E402
from src import team_versus as tv  # noqa: E402

OUTPUT_DIR = "head-to-head"
PAGE = "head-to-head.html"
SECONDS_FIELDS = ("powerplay_seconds", "boxplay_seconds")
DECISIONS = {pr.OVERTIME: "n.V.", pr.SHOOTOUT: "n.P."}


def league_key(prefix: str) -> str:
    return prefix.rstrip("-") or "de"


def _seconds(article, side: str, name: str, fallback: int | None) -> int | None:
    """Per-game seconds from the game's own front matter, else the one rebuilt from its events."""
    stored = insights._int(article, f"{side}_{name}")
    return stored if stored is not None else fallback


def _side_specials(article, side: str, seconds: tuple[int, int] | None) -> tv.SideSpecials:
    count = lambda name: insights._int(article, f"{side}_{name}") or 0  # noqa: E731
    own, other = (0, 1) if side == "home" else (1, 0)
    return tv.SideSpecials(
        powerplay=count("powerplay"),
        powerplay_goals=count("goals_in_powerplay"),
        boxplay=count("boxplay"),
        boxplay_goals_against=count("goals_against_in_boxplay"),
        powerplay_seconds=_seconds(article, side, "powerplay_seconds", seconds[own] if seconds else None),
        boxplay_seconds=_seconds(article, side, "boxplay_seconds", seconds[other] if seconds else None),
    )


def duel_of(article, season: str, phase: str) -> tv.Duel:
    game = insights._trend_game(article)
    events = pi.decode_events(insights._meta(article, "game_events_b64"))
    seconds = None
    if not any(insights._meta(article, f"home_{name}") for name in SECONDS_FIELDS):
        seconds = tv.man_advantage_seconds(events, game.home, game.away)
    return tv.Duel(
        game=game,
        season=season,
        phase=phase,
        decision=DECISIONS.get(insights._decision(article), ""),
        home=_side_specials(article, "home", seconds),
        away=_side_specials(article, "away", seconds),
    )


def _team_urls(teams_by_category: dict[str, list], categories: list[str]) -> dict[str, str]:
    """Each team's newest team page (categories newest first)."""
    urls: dict[str, str] = {}
    for category in categories:
        for article in teams_by_category.get(category, []):
            name = insights._meta(article, "team") or insights._meta(article, "title")
            urls.setdefault(name, article.url)
    return urls


def page_link(key: str, team: str | None = None, opponent: str | None = None) -> str:
    """Path of the comparison page with a league, and optionally two teams, preselected."""
    query = {"league": key, **({"a": team, "b": opponent} if team and opponent else {})}
    return f"{PAGE}?{urlencode(query)}"


def build(generator) -> dict:
    settings = generator.settings
    league_context = settings["JINJA_FILTERS"]["league_context"]
    leagues = {league["prefix"]: league for league in settings["LEAGUES"]}
    articles = list(generator.articles)
    player_slugs = {article.slug for article in articles if insights._meta(article, "type") == "player"}

    def player_url(player: pi.PlayerRef) -> str:
        return f"{player.uid}.html" if player.uid in player_slugs else ""

    duels: dict[str, list[tv.Duel]] = defaultdict(list)
    teams_by_category: dict[str, list] = defaultdict(list)
    categories: dict[str, set[str]] = defaultdict(set)
    for article in articles:
        kind = insights._meta(article, "type")
        category = insights._category(article)
        if kind == "team":
            teams_by_category[category].append(article)
            continue
        context = league_context(category)
        if kind != "game" or not context or context["prefix"] not in leagues or insights._meta(article, "game_state") != "played":
            continue
        if not insights._meta(article, "home_team") or not insights._meta(article, "away_team"):
            continue
        duels[context["prefix"]].append(duel_of(article, context["season"], context["phase"]))
        categories[context["prefix"]].add(category)

    payloads, index = {}, []
    for league in settings["LEAGUES"]:
        prefix = league["prefix"]
        if prefix not in duels:
            continue
        newest = sorted(categories[prefix], key=lambda category: league_context(category)["season"], reverse=True)
        key = league_key(prefix)
        payloads[key] = tv.league_payload(duels[prefix], _team_urls(teams_by_category, newest), player_url)
        index.append({"key": key, "title": league["title"], "division": league["division"], "teams": len(payloads[key]["teams"])})
    return {"payloads": payloads, "index": index, "teams": teams_by_category}


def attach_team_records(payloads: dict[str, dict], teams_by_category: dict[str, list], league_context, leagues: set[str]) -> None:
    """``article.versus`` on every team page: its record against each team of the same season phase."""
    for category, articles in teams_by_category.items():
        context = league_context(category)
        if not context or context["prefix"] not in leagues or league_key(context["prefix"]) not in payloads:
            continue
        key = league_key(context["prefix"])
        ranked = sorted(articles, key=lambda article: (insights._int(article, "rank") or 99, insights._meta(article, "team") or insights._meta(article, "title")))
        names = [insights._meta(article, "team") or insights._meta(article, "title") for article in ranked]
        for article in articles:
            team = insights._meta(article, "team") or insights._meta(article, "title")
            rows = tv.team_rows(payloads[key], team, [name for name in names if name != team])
            if rows:
                article.versus = {"rows": [{**row, "href": page_link(key, team, row["team"])} for row in rows], "league_href": page_link(key)}


def collect(generator) -> None:
    result = build(generator)
    settings = generator.settings
    attach_team_records(result["payloads"], result["teams"], settings["JINJA_FILTERS"]["league_context"], {league["prefix"] for league in settings["LEAGUES"]})
    generator.context["HEAD_TO_HEAD_LEAGUES"] = result["index"]
    generator.context["_HEAD_TO_HEAD_PAYLOADS"] = result["payloads"]


def write(generator, writer) -> None:
    payloads = generator.context.get("_HEAD_TO_HEAD_PAYLOADS") if hasattr(generator, "context") else None
    if not payloads:
        return
    folder = os.path.join(generator.output_path, OUTPUT_DIR)
    os.makedirs(folder, exist_ok=True)
    for key, payload in payloads.items():
        with open(os.path.join(folder, f"{key}.json"), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))


def register() -> None:
    signals.article_generator_finalized.connect(collect)
    signals.article_writer_finalized.connect(write)
