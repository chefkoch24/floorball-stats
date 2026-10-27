from datetime import datetime, time

from pelicanconf import fmt_time


def test_fmt_time_keeps_hours_and_minutes_only():
    assert fmt_time("18:30:00") == "18:30"
    assert fmt_time("18:30") == "18:30"
    assert fmt_time(time(18, 30, 45)) == "18:30"
    assert fmt_time(datetime(2026, 3, 20, 18, 30, 45)) == "18:30"


def test_fmt_time_handles_empty_values():
    assert fmt_time(None) == "TBD"
    assert fmt_time("") == "TBD"
    assert fmt_time("None") == "TBD"
    assert fmt_time("TBD") == "TBD"


def test_article_paths_cover_every_league_for_every_season():
    import pelicanconf

    for season in pelicanconf.SEASONS:
        for league in pelicanconf.LEAGUES:
            for phase in pelicanconf.SEASON_PHASES:
                assert f"{league['prefix']}{season}-{phase}/games" in pelicanconf.ARTICLE_PATHS
    assert pelicanconf.CURRENT_SEASON == pelicanconf.SEASONS[0]


def test_category_slugs_reads_pelican_category_context():
    from types import SimpleNamespace

    from pelicanconf import category_slugs

    categories = [(SimpleNamespace(slug="se-26-27-regular-season"), []), (SimpleNamespace(slug="game"), [])]

    assert category_slugs(categories) == {"se-26-27-regular-season", "game"}
    assert category_slugs(None) == set()


def test_category_labels_cover_women_leagues():
    from pelicanconf import category2breadcrumb, category2string

    assert category2string("se-26-27-regular-season") == "Sweden 26/27 Regular Season"
    assert category2string("sew-26-27-playoffs") == "Sweden Women 26/27 Playoffs"
    assert category2breadcrumb("sew-26-27-regular-season") == "Sweden Women Regular Season 26/27"
    assert category2breadcrumb("26-27-regular-season") == "Germany Regular Season 26/27"
    assert category2breadcrumb("dew-26-27-regular-season") == "Germany Women Regular Season 26/27"


def test_every_league_belongs_to_a_navigation_division():
    import pelicanconf

    divisions = {key for key, _ in pelicanconf.DIVISIONS}
    assert all(league["division"] in divisions for league in pelicanconf.LEAGUES + pelicanconf.COMPETITIONS)
    assert pelicanconf.WOMEN_LEAGUE_PREFIXES == ["sew-", "fiw-", "czw-", "chw-", "skw-", "lvw-", "dew-", "ccw-"]


def test_team_crest_helpers_are_stable():
    from pelicanconf import crest_index, team_initials

    assert team_initials("Thorengruppen IBK") == "THO"
    assert team_initials("IBK Lund Elit") == "LE"
    assert team_initials("FBC ČPP MPL STAVEBNINY OSTRAVA") == "ČMS"
    assert team_initials("") == "?"
    assert crest_index("Pixbo IBK") == crest_index("pixbo ibk ")
    assert 1 <= crest_index("Pixbo IBK") <= 8


def test_league_context_resolves_prefix_season_and_phase():
    from pelicanconf import league_context

    women = league_context("sew-26-27-regular-season")
    assert (women["prefix"], women["season_label"], women["phase"], women["division"]) == ("sew-", "26/27", "regular-season", "women")
    assert league_context("26-27-playoffs")["name"] == "Germany"
    assert league_context("se-26-27-players")["phase"] == "players"
    assert league_context("wfc-2024-regular-season") is None
