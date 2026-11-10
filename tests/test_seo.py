"""SEO output contracts: identity, crawlability and honest structured data."""

import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as Obj

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "plugins"))
sys.path.append(str(ROOT / "connect"))

import connect_content as cc
import seo
from pelicanconf import category_seo_label, league_context
from scripts.check_seo import Page


def test_competition_labels_identify_league_division_and_full_season():
    label = category_seo_label("se-26-27-regular-season")
    assert "SSL" in label and "2026/2027" in label and "Men" in label
    women = category_seo_label("sew-26-27-regular-season-players")
    assert "Damer" in women and "Women" in women and "2026/2027" in women
    assert "WFC" in category_seo_label("wfc-2024-playoffs")


def test_sitemap_excludes_aliases_and_technical_pages_without_faking_freshness(tmp_path):
    ns = seo.NS
    root = ET.Element(f"{{{ns}}}urlset")
    site = "https://stats.example.com"
    for path in ("", "game.html", "player-alias.html", "category/game.html", "archives.html"):
        entry = ET.SubElement(root, f"{{{ns}}}url")
        ET.SubElement(entry, f"{{{ns}}}loc").text = f"{site}/{path}"
        ET.SubElement(entry, f"{{{ns}}}lastmod").text = "2099-03-01"
    path = tmp_path / "sitemap.xml"
    ET.ElementTree(root).write(path)
    removed = seo.clean_sitemap(path, site, {"player-alias.html": "player-main.html"},
                                {"game.html": datetime(2026, 1, 1)})
    doc = ET.parse(path)
    assert len(removed) == 3
    assert [x.text for x in doc.findall(".//{*}loc")] == [site + "/", site + "/game.html"]
    assert [x.text for x in doc.findall(".//{*}lastmod")] == ["2026-01-01T00:00:00"]
    first = path.read_bytes()
    seo.clean_sitemap(path, site, {}, {"game.html": datetime(2026, 1, 1)})
    assert path.read_bytes() == first  # rebuilding alone never changes freshness


def test_player_aliases_and_game_links_resolve_to_existing_entities():
    category = Obj(slug="se-26-27-playoffs")
    main = Obj(type="player", slug="player-main", player_uid="player-main", url="player-main.html")
    alias = Obj(type="player", slug="player-old", player_uid="player-main", url="player-old.html")
    game = Obj(type="game", slug="g", url="g.html", category=category,
               home_team="Malmö", away_team="Missing", date=datetime(2026, 3, 20), start_time="18:30")
    settings = {"SITEURL": "https://stats.example.com", "JINJA_FILTERS": {
        "league_context": league_context, "category_seo_label": category_seo_label}}
    generator = Obj(articles=[main, alias, game], settings=settings,
                    context={"TEAM_PAGES": {("se-26-27-regular-season", "malmo"): "malmo.html"}})
    seo.collect(generator)
    assert alias.seo_canonical_path == main.url
    assert settings["SEO_ALIASES"] == {"player-old.html": "player-main.html"}
    assert game.seo_home_url == "malmo.html" and game.seo_away_url == ""
    assert game.seo_event["startDate"] == "2026-03-20T18:30:00+01:00"
    assert "location" not in game.seo_event


def test_future_explicit_modification_is_omitted(tmp_path):
    path = tmp_path / "sitemap.xml"
    path.write_text(f'<urlset xmlns="{seo.NS}"><url><loc>https://example.com/g.html</loc></url></urlset>')
    seo.clean_sitemap(path, "https://example.com", {}, {"g.html": datetime(2099, 1, 1)})
    assert "lastmod" not in path.read_text()


def test_visible_review_average_and_product_schema_use_the_same_real_reviews():
    collection = cc.BY_KEY["sticks"]
    record = {"id": "p", "fields": {"Name": 'A "Pro"', "Brand": "B", "Overall Rating": 5},
              "reviews": [
                  {"fields": {"Display Name": "Player", "Overall Rating": 3, "Review": "Good control"}},
                  {"fields": {"Anonymous": "Anonymous", "Overall Rating": 4, "Review": "Light"}},
                  {"fields": {"Display Name": "No score", "Review": "Nice"}},
              ]}
    item = cc.normalize(collection, record)
    assert cc.review_average(item)["Overall"] == 3.5
    graph = cc.structured_data("https://example.com", "sticks/a/", collection, item)["@graph"]
    product = next(node for node in graph if node["@type"] == "Product")
    assert product["aggregateRating"]["ratingValue"] == 3.5
    assert product["aggregateRating"]["ratingCount"] == 2
    assert len(product["review"]) == 1  # no invented identity for anonymous ratings
    item.reviews = []
    graph = cc.structured_data("https://example.com", "a/", collection, item)["@graph"]
    assert not any(node['@type'] == 'Product' for node in graph)


def test_text_summaries_preserve_boundaries_and_placeholder_urls_are_not_links():
    assert cc.plain_text("<h2>Setup</h2><p>3 players</p>") == "Setup 3 players"
    assert cc.safe_link("-") == "" and cc.safe_link("javascript:alert(1)") == ""
    assert cc.safe_link("https://example.com/book") == "https://example.com/book"
    item = cc.normalize(cc.BY_KEY["books"], {"id": "b", "fields": {"Name": "Book", "Link": "-"}})
    assert item.link == ""


def test_published_connect_pages_have_consistent_canonicals_and_linked_lexicon(tmp_path):
    import subprocess

    result = subprocess.run([sys.executable, "-m", "pelican", "connect/content", "-s",
                             "connect/publishconf.py", "-o", str(tmp_path)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    sitemap = ET.parse(tmp_path / "sitemap.xml")
    urls = [x.text for x in sitemap.findall(".//{*}loc")]
    assert not any("/confirmation" in url or "/coming-soon/" in url for url in urls)
    site = "https://www.floorballconnect.com/"
    for url in urls:
        path = tmp_path / url.removeprefix(site) / "index.html"
        page = Page(path.read_text())
        assert page.canonical == url, url
        assert page.schemas and not page.schema_errors, url
        assert "noindex" not in page.robots, url
    overview = Page((tmp_path / "floorball-lexicon/index.html").read_text())
    assert site + "floorball-lexicon/powerplay/" in overview.links
    confirm = Page((tmp_path / "confirmation/index.html").read_text())
    assert "noindex" in confirm.robots


def test_prepare_accepts_pelican_category_pairs_and_keeps_static_pages():
    settings = {'SITEURL': '', 'JINJA_FILTERS': {}}
    articles = Obj(articles=[], categories=[(Obj(url='category/se.html'), [])],
                   context={}, settings=settings)
    pages = Obj(pages=[Obj(url='archive.html', metadata={})], settings=settings)
    seo.prepare([articles, pages])
    assert settings['SEO_URLS'] == {'', 'leaders.html', 'category/se.html', 'archive.html'}


def test_homepage_keeps_next_matchday_without_dumping_the_whole_season():
    from datetime import timedelta
    from pelicanconf import BUILD_DATE, homepage_games
    def game(days, slug):
        return Obj(type='game', category=Obj(slug=slug),
                   date=datetime.combine(BUILD_DATE + timedelta(days=days), datetime.min.time()))
    next_men = game(5, 'se-26-27-regular-season')
    next_women = game(7, 'sew-26-27-regular-season')
    season = [next_men, next_women, game(50, 'se-26-27-regular-season')]
    assert homepage_games(season) == [next_men, next_women]


def test_metadata_reader_does_not_mistake_svg_tooltips_for_page_title():
    page = Page('<html><head><title>SSL standings</title></head><body><svg><title>Chart tooltip</title></svg></body></html>')
    assert page.title == 'SSL standings'


def test_standings_list_teams_in_table_order_with_their_numbers():
    def team(name, rank, **extra):
        values = dict(type="team", team=name, rank=str(rank), games=7, wins=4, over_time_wins=1,
                      penalty_shootout_wins=1, over_time_losses=0, penalty_shootout_losses=1, losses=0,
                      draws=0, goals=30, goals_against=20, goal_difference=10, points=18)
        values.update(extra)
        return Obj(title=name, url=f"{name.lower()}.html", **values)

    schema = seo.standings_schema([team("Beta", 2, goal_difference=-3), team("Alpha", 1)],
                                  "https://s.example", "SSL", "category/se.html")
    assert schema["@type"] == "ItemList" and schema["numberOfItems"] == 2
    first, second = schema["itemListElement"]
    assert (first["position"], first["name"], second["name"]) == (1, "Alpha", "Beta")
    assert first["item"] == {"@type": "SportsTeam", "name": "Alpha", "sport": "Floorball",
                             "url": "https://s.example/alpha.html"}
    assert "2 wins after overtime or penalty shots" in first["description"]
    assert "goals 30:20" in first["description"] and "18 points" in first["description"]
    assert "goal difference -3" in second["description"] and "draws" not in second["description"]


def test_player_schema_states_club_season_and_tracked_career():
    player = Obj(title="A", player="Ann Example", team="IBF Falun", league="Sweden",
                 current_games=10, regular_games=7, regular_goals=3, regular_assists=2, regular_points=5,
                 regular_pim=2, playoff_games=0, cup_games=3, cup_goals=4, cup_assists=1,
                 career_games=24, career_goals=6, career_assists=5, career_points=11)
    schema = seo.player_schema(player, "https://s.example", "player-1.html", "falun.html", "26/27")
    assert schema["@type"] == "Person" and schema["url"] == "https://s.example/player-1.html"
    assert schema["memberOf"]["url"] == "https://s.example/falun.html"
    text = schema["description"]
    assert text.startswith("Ann Example, floorball player for IBF Falun (Sweden).")
    assert "Season 26/27: 7 regular-season games, 3 goals, 2 assists, 5 points" in text
    assert "cup: 3 games, 4 goals, 1 assists" in text and "playoffs" not in text
    assert "24 games, 6 goals, 5 assists, 11 points" in text
    assert seo.season_label("ch-26-27") == "26/27" and seo.season_label("wfc-2024") == ""
