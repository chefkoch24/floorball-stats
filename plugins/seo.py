"""Build-time SEO policy for Stats; no data refresh or database writes.

Only explicit Modified metadata is suitable for sitemap lastmod. Article Date
is a fixture date (often in the future), not the last time its content changed.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pelican import signals

from rosters import team_key
from share_assets import _timezone_for
from src.player_insights import decode_events

NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
TECHNICAL = {"archives.html", "authors.html", "categories.html", "tags.html",
             "category/game.html", "category/teams.html", "category/liga.html", "category/players.html"}


def meta(article, key, default=""):
    value = getattr(article, key, default)
    if isinstance(value, list):
        value = value[0] if value else default
    text = str(value if value is not None else default).strip()
    return "" if text in {"None", "nan", "n.a."} else text


def game_schema(article, site, label, league):
    home, away = meta(article, "home_team"), meta(article, "away_team")
    result = {"@context": "https://schema.org", "@type": "SportsEvent",
              "name": f"{home} vs {away}", "sport": "Floorball",
              "url": f"{site}/{article.url}",
              "description": f"{home} vs {away} in {label}.",
              "competitor": [{"@type": "SportsTeam", "name": name} for name in (home, away)]}
    if article.date:
        result["startDate"] = article.date.strftime("%Y-%m-%d")
        start = meta(article, "start_time")
        if league and re.fullmatch(r"\d{2}:\d{2}(?::\d{2})?", start):
            try:
                value = datetime.fromisoformat(f"{result['startDate']}T{start}")
                result["startDate"] = value.replace(tzinfo=_timezone_for(league or {})).isoformat()
            except ValueError:
                pass
    venue = meta(article, "venue") or meta(article, "arena") or meta(article, "location")
    if venue:
        result["location"] = {"@type": "Place", "name": venue}
        address = meta(article, "venue_address") or meta(article, "address")
        if address:
            result["location"]["address"] = {"@type": "PostalAddress", "streetAddress": address}
    return result


def _int(article, key):
    try:
        return int(float(meta(article, key, "0") or 0))
    except ValueError:
        return 0


def _signed(value):
    return f"+{value}" if value > 0 else str(value)


def standings_schema(teams, site, label, url):
    """The league table as an ItemList: one entry per team, in table order.

    schema.org has no standings type, so each row's numbers go into its
    description, the same figures the table on the page shows."""
    def rank(article):
        try:
            return float(meta(article, "rank"))
        except ValueError:
            return float("inf")

    items = []
    for position, team in enumerate(sorted(teams, key=rank), start=1):
        name = meta(team, "team") or getattr(team, "title", "")
        wins_ot = _int(team, "over_time_wins") + _int(team, "penalty_shootout_wins")
        losses_ot = _int(team, "over_time_losses") + _int(team, "penalty_shootout_losses")
        row = (f"{_int(team, 'games')} games, {_int(team, 'wins')} wins, {wins_ot} wins after overtime "
               f"or penalty shots, ")
        if _int(team, "draws"):
            row += f"{_int(team, 'draws')} draws, "
        row += (f"{losses_ot} losses after overtime or penalty shots, {_int(team, 'losses')} losses, "
                f"goals {_int(team, 'goals')}:{_int(team, 'goals_against')}, "
                f"goal difference {_signed(_int(team, 'goal_difference'))}, {_int(team, 'points')} points")
        items.append({"@type": "ListItem", "position": position, "name": name,
                      "description": f"Place {position}: {row}.",
                      "item": {"@type": "SportsTeam", "name": name, "sport": "Floorball",
                               "url": f"{site}/{team.url}"}})
    return {"@context": "https://schema.org", "@type": "ItemList",
            "name": f"{label} standings", "url": f"{site}/{url}",
            "numberOfItems": len(items), "itemListOrder": "https://schema.org/ItemListOrderAscending",
            "itemListElement": items}


def player_schema(article, site, path, team_url="", season_label=""):
    """Person with the club and the figures of the player page in plain words."""
    name = meta(article, "player") or getattr(article, "title", "")
    team, league = meta(article, "team"), meta(article, "league")
    parts = []
    if season_label and _int(article, "current_games"):
        line = (f"Season {season_label}: {_int(article, 'regular_games')} regular-season games, "
                f"{_int(article, 'regular_goals')} goals, {_int(article, 'regular_assists')} assists, "
                f"{_int(article, 'regular_points')} points, {_int(article, 'regular_pim')} penalty minutes")
        for phase, label in (("playoff", "playoffs"), ("cup", "cup")):
            if _int(article, f"{phase}_games"):
                line += (f"; {label}: {_int(article, f'{phase}_games')} games, "
                         f"{_int(article, f'{phase}_goals')} goals, {_int(article, f'{phase}_assists')} assists")
        parts.append(line + ".")
    if _int(article, "career_games"):
        parts.append(f"League games tracked on Floorball Stats: {_int(article, 'career_games')} games, "
                     f"{_int(article, 'career_goals')} goals, {_int(article, 'career_assists')} assists, "
                     f"{_int(article, 'career_points')} points.")
    intro = f"{name}, floorball player" + (f" for {team}" if team else "") + (f" ({league})" if league else "") + "."
    result = {"@context": "https://schema.org", "@type": "Person", "name": name,
              "url": f"{site}/{path}", "description": " ".join([intro, *parts])}
    if team:
        result["memberOf"] = {"@type": "SportsTeam", "name": team, "sport": "Floorball"}
        if team_url:
            result["memberOf"]["url"] = f"{site}/{team_url}"
    return result


def season_label(slug):
    """'ch-26-27' -> '26/27'; tournament slugs stay as they are."""
    match = re.search(r"(\d{2})-(\d{2})$", slug or "")
    return f"{match.group(1)}/{match.group(2)}" if match else ""


def collect_structured(generator, site):
    """Standings per regular-season league page and Person data per player page."""
    filters = generator.settings["JINJA_FILTERS"]
    teams_by_category = {}
    team_pages = generator.context.get("TEAM_PAGES", {})
    for article in generator.articles:
        kind = meta(article, "type")
        if kind == "team" and getattr(article, "category", None):
            league = filters["league_context"](article.category.slug)
            if league and league.get("phase") == "regular-season":
                teams_by_category.setdefault(article.category.slug, []).append(article)
        elif kind == "player":
            current = meta(article, "current_season")
            team_url = team_pages.get((f"{current}-regular-season" if current else "",
                                       team_key(meta(article, "team"))), "")
            if meta(article, "current_season_is_tournament") == "yes":
                team_url = ""
            article.seo_person = player_schema(article, site, article.seo_canonical_path,
                                               team_url, season_label(current))
    standings = {}
    for category, teams in teams_by_category.items():
        label = filters["category_seo_label"](category)
        standings[category] = standings_schema(teams, site, label, f"category/{category}.html")
    generator.context["SEO_STANDINGS"] = standings


def collect(generator):
    settings = generator.settings
    site = settings.get("SITEURL", "").rstrip("/")
    articles = generator.articles
    player_slugs = {article.slug for article in articles if meta(article, "type") == "player"}
    player_targets = {article.slug: meta(article, "player_uid") or article.slug
                      for article in articles if meta(article, "type") == "player"}
    teams = generator.context.get("TEAM_PAGES", {})
    aliases = {}
    for article in articles:
        kind = meta(article, "type")
        article.seo_canonical_path = article.url
        if kind == "player":
            uid = meta(article, "player_uid")
            if uid in player_slugs and uid != article.slug:
                article.seo_canonical_path = f"{uid}.html"
                aliases[article.url] = article.seo_canonical_path
        if kind != "game":
            continue
        category = article.category.slug if article.category else ""
        league = settings["JINJA_FILTERS"]["league_context"](category)
        label = settings["JINJA_FILTERS"]["category_seo_label"](category)
        article.seo_event = game_schema(article, site, label, league)
        regular = category.replace("-playoffs", "-regular-season")
        if category.endswith("-cup"):
            # Cups publish game pages only; their teams link to the league's team pages.
            regular = f"{category[:-len('-cup')]}-regular-season"
        for side in ("home", "away"):
            name = meta(article, f"{side}_team")
            # Link only to an actual generated article, falling back to its
            # regular-season page for classification/playout/cup games.
            url = teams.get((category, team_key(name))) or teams.get((regular, team_key(name)), "")
            setattr(article, f"seo_{side}_url", url)
        article.seo_goals = [event for event in decode_events(meta(article, "game_events_b64"))
                             if event.get("event_kind") == "goal"]
        for event in article.seo_goals:
            for field in ("title", "assist"):
                uid = player_targets.get(event.get(f"{field}_uid"))
                event[f"{field}_url"] = f"{uid}.html" if uid in player_slugs else ""
    generator.context["SEO_ALIASES"] = aliases
    settings["SEO_ALIASES"] = aliases
    collect_structured(generator, site)


def clean_sitemap(path, site, aliases, modified=None):
    """Keep canonical, useful URLs; never pretend a game date is lastmod."""
    tree = ET.parse(path)
    root = tree.getroot()
    removed = []
    today = datetime.now(ZoneInfo("Europe/Berlin")).date()
    for entry in list(root):
        location = entry.find(f"{{{NS}}}loc")
        if location is None:
            continue
        url = location.text or ""
        relative = url.removeprefix(site.rstrip("/") + "/")
        if relative in TECHNICAL or relative in aliases:
            root.remove(entry)
            removed.append(url)
            continue
        for field in list(entry):
            if field.tag in {f"{{{NS}}}lastmod", f"{{{NS}}}priority", f"{{{NS}}}changefreq"}:
                entry.remove(field)
        stamp = (modified or {}).get(relative)
        if stamp and stamp.date() <= today:
            ET.SubElement(entry, f"{{{NS}}}lastmod").text = stamp.isoformat()
    ET.register_namespace("", NS)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return removed


def remember_modified(generator):
    # Explicit Modified only. Do not clamp future fixture dates to "today".
    modified = generator.settings.setdefault("SEO_MODIFIED", {})
    for item in [*getattr(generator, "articles", []), *getattr(generator, "pages", [])]:
        if "modified" in getattr(item, "metadata", {}) and getattr(item, "modified", None):
            modified[item.url] = item.modified


def prepare(generators):
    # This signal runs after roster/insights enrichment, independent of Blinker
    # receiver ordering, and before templates are rendered.
    for generator in generators:
        remember_modified(generator)
        if not hasattr(generator, "articles"):
            continue
        collect(generator)
        urls = {"", "leaders.html"}
        urls.update(article.url for article in generator.articles)
        for entry in generator.categories:
            category = entry[0] if isinstance(entry, (tuple, list)) else entry
            urls.add(category.url)
        generator.settings["SEO_URLS"] = urls
    for generator in generators:
        generator.settings.setdefault("SEO_URLS", set()).update(
            page.url for page in getattr(generator, "pages", []))


def finalize(pelican):
    settings = pelican.settings
    output = Path(settings["OUTPUT_PATH"])
    site = settings.get("SITEURL", "").rstrip("/")
    aliases = settings.get("SEO_ALIASES", {})
    sitemap = output / "sitemap.xml"
    if settings.get("SEO_URLS"):
        root = ET.Element(f"{{{NS}}}urlset")
        for path in sorted(settings["SEO_URLS"]):
            entry = ET.SubElement(root, f"{{{NS}}}url")
            ET.SubElement(entry, f"{{{NS}}}loc").text = f"{site}/{path}"
        ET.ElementTree(root).write(sitemap, encoding="utf-8", xml_declaration=True)
        removed = clean_sitemap(sitemap, site, aliases, settings.get("SEO_MODIFIED"))
        (output / "seo-report.json").write_text(json.dumps({
            "sitemap": f"{site}/sitemap.xml", "excluded": removed,
            "player_aliases": aliases,
            "lastmod_policy": "Explicit Modified metadata only; fixture dates are not modification dates.",
        }, indent=2) + "\n", encoding="utf-8")
    (output / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {site}/sitemap.xml\n", encoding="utf-8")
    if aliases:
        with (output / "_redirects").open("a", encoding="utf-8") as handle:
            handle.write("\n# Canonical player identities (SEO)\n")
            for alias, target in sorted(aliases.items()):
                for old in (alias, alias.removesuffix(".html")):
                    handle.write(f"{site}/{old} {site}/{target} 301!\n")


def register():
    signals.all_generators_finalized.connect(prepare)
    signals.finalized.connect(finalize)
