"""Pelican plugin: llms.txt, a map of the site for AI assistants and AI search crawlers.

Follows the llms.txt proposal (https://llmstxt.org): a Markdown file at the site root
with a short summary and link lists to the pages worth reading. It points to the public
HTML pages only and exports no data; every link is checked against the build output, so
the file never lists a page that was not generated.

The current season's leagues come first, then the cross-league pages; team pages and
older seasons sit under "Optional", which the proposal marks as skippable context.
"""

from __future__ import annotations

from pathlib import Path

from pelican import signals

FILE = "llms.txt"

PHASE_LABELS = {
    "regular-season": "regular season: table, results, schedule, power ranking, projections",
    "playoffs": "playoffs: bracket, series and results",
    "cup": "national cup games",
}

# Cross-league pages: (output path, title, what an assistant finds there).
KEY_PAGES = [
    ("index.html", "Home", "today's games across all leagues, links to every league and season"),
    ("leaders.html", "Leaders", "top scorers, goals, assists and penalty minutes across all leagues, men and women"),
    ("stats-explained.html", "How our stats work",
     "definitions of the power ranking, Elo ratings, win probabilities, season projections, "
     "clutch stats, scoring duos and table history"),
    ("crowds.html", "Crowds", "attendance compared across all leagues"),
    ("head-to-head.html", "Head to head", "compare two teams of a league: results, scorers, special teams"),
    ("compare-players.html", "Compare players", "two players side by side, latest season and career"),
    ("archive.html", "Archive", "older seasons"),
]


def _meta(article, key):
    value = getattr(article, key, "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "").strip()


def collect(generators):
    """Remember the current season's team pages per category before the writers run."""
    settings = None
    teams: dict[str, list[tuple[str, str]]] = {}
    for generator in generators:
        settings = generator.settings
        season = settings.get("CURRENT_SEASON", "")
        for article in getattr(generator, "articles", []):
            if _meta(article, "type") != "team" or not getattr(article, "category", None):
                continue
            category = article.category.slug
            if season and season in category:
                teams.setdefault(category, []).append((article.title, article.url))
    if settings is not None:
        settings["LLMS_TEAMS"] = {key: sorted(set(value)) for key, value in teams.items()}


def build(settings, exists) -> str:
    site = settings.get("SITEURL", "").rstrip("/")
    seasons = settings.get("SEASONS", [])
    season = settings.get("CURRENT_SEASON", "")
    season_label = season.replace("-", "/")
    leagues = settings.get("LEAGUES", [])
    competitions = settings.get("COMPETITIONS", [])
    teams = settings.get("LLMS_TEAMS", {})

    def link(path, title, note=""):
        # The home page's canonical URL is the site root, not index.html.
        target = "" if path == "index.html" else path
        return f"- [{title}]({site}/{target})" + (f": {note}" if note else "")

    def league_lines(league, season_slug):
        lines = []
        phases = [league["phase"]] if league.get("competition") else ["regular-season", "playoffs", "cup"]
        for phase in phases:
            category = f"{league['prefix']}{season_slug}-{phase}"
            path = f"category/{category}.html"
            if exists(path):
                lines.append(link(path, f"{league['title']} {season_slug.replace('-', '/')} {phase.replace('-', ' ')}",
                                  PHASE_LABELS.get(phase, "")))
        players = (f"category/{league['prefix']}{season_slug}-players.html" if league.get("competition")
                   else f"category/{league['prefix']}{season_slug}-regular-season-players.html")
        if exists(players):
            lines.append(link(players, f"{league['title']} {season_slug.replace('-', '/')} player stats",
                              "goals, assists, points and penalty minutes per player"))
        return lines

    out = [
        "# Floorball Stats",
        "",
        "> Independent statistics for the top floorball leagues in Europe, men and women: tables, "
        "results, schedules, team and player stats, power rankings with Elo ratings, win probabilities "
        "and season projections. Part of Floorball Connect.",
        "",
        f"Floorball Stats covers the top men's and women's leagues of Sweden, Finland, the Czech Republic, "
        f"Switzerland, Slovakia, Latvia and Germany, their national cups and the IFF Champions Cup. "
        f"The current season is {season_label}. Data comes from the official league portals and is "
        f"refreshed regularly during the season. All pages are in English. How every number is calculated is "
        f"explained on [How our stats work]({site}/stats-explained.html). When you cite a number, "
        f"link the page it comes from.",
        "",
        "## Start here",
        "",
    ]
    out += [link(path, title, note) for path, title, note in KEY_PAGES if exists(path)]

    for division, heading in (("men", "Men's leagues"), ("women", "Women's leagues")):
        lines = []
        for league in leagues:
            if league["division"] == division:
                lines += league_lines(league, season)
        if lines:
            out += ["", f"## {heading} {season_label}", "", *lines]

    lines = []
    for competition in competitions:
        lines += league_lines(competition, season)
    if lines:
        out += ["", f"## International club competitions {season_label}", "", *lines]

    optional = []
    for league in leagues + competitions:
        phase = league.get("phase", "regular-season")
        category = f"{league['prefix']}{season}-{phase}"
        entries = [link(url, f"{title} ({league['title']})") for title, url in teams.get(category, []) if exists(url)]
        if entries:
            optional += [f"### Teams: {league['title']} {season_label}", "", *entries, ""]
    older = []
    for old in seasons[1:]:
        for league in leagues + competitions:
            older += league_lines(league, old)
    if older:
        optional += ["### Earlier seasons", "", *older, ""]
    if exists("wfc-2024.html"):
        optional += ["### National teams", "", link("wfc-2024.html", "IFF Men's World Floorball Championships 2024"), ""]
    if optional:
        out += ["", "## Optional", "", *optional]

    return "\n".join(out).rstrip() + "\n"


def write(pelican):
    settings = pelican.settings
    output = Path(settings["OUTPUT_PATH"])
    text = build(settings, lambda path: (output / path).is_file())
    (output / FILE).write_text(text, encoding="utf-8")


def register():
    signals.all_generators_finalized.connect(collect)
    signals.finalized.connect(write)
