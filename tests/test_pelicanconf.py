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
