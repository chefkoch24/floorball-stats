from datetime import date

from src import crowd_stats as cs


def _game(attendance, home="A", day=date(2026, 10, 31), start="18:00", season="26-27", phase="regular-season", away="Z"):
    return cs.CrowdGame("ch-", season, phase, day, start, home, away, attendance, f"{home}-{attendance}.html")


def test_season_line_average_median_total_and_highest():
    line = cs.season_line([_game(100, "A"), _game(300, "B"), _game(200, "A"), _game(1000, "C")])
    assert line["games"] == 4 and line["total"] == 1600 and line["average"] == 400 and line["median"] == 250
    assert line["highest"] == 1000 and line["highest_game"]["home"] == "C"
    assert line["teams"] == 3 and round(line["gradient"], 2) == 6.67  # C 1000 against A 150


def test_top_share_needs_more_teams_than_the_top_group():
    few = cs.season_line([_game(100, "A"), _game(200, "B"), _game(300, "C")])
    assert few["top_share"] is None
    many = cs.season_line([_game(400, "A"), _game(300, "B"), _game(200, "C"), _game(100, "D")])
    assert many["top_share"] == 0.9


def test_league_analysis_compares_with_the_previous_season_that_has_data():
    games = [_game(200, season="26-27"), _game(300, season="26-27"), _game(200, season="24-25")]
    analysis = cs.league_analysis(games, ["26-27", "25-26", "24-25"])
    assert analysis["season"] == "26-27" and analysis["current"]["previous_season"] == "24-25"
    assert analysis["current"]["change"] == 0.25
    assert [row["season"] for row in analysis["seasons"]] == ["26-27", "24-25"]


def test_league_analysis_without_games_is_none_and_a_first_season_has_no_change():
    assert cs.league_analysis([], ["26-27"]) is None
    analysis = cs.league_analysis([_game(100)], ["26-27", "25-26"])
    assert analysis["current"]["change"] is None and analysis["current"]["previous_season"] is None


def test_weekday_kickoff_and_phase_buckets():
    games = [
        _game(100, day=date(2026, 10, 31), start="14:00"),  # Saturday
        _game(300, day=date(2026, 10, 31), start="19:30"),
        _game(500, day=date(2026, 11, 1), start="16:00", phase="playoffs"),  # Sunday
    ]
    weekdays = {row["label"]: row for row in cs.weekday_rows(games)}
    assert weekdays["Sat"]["average"] == 200 and weekdays["Sun"]["games"] == 1 and not weekdays["Sun"]["enough"]
    kickoffs = {row["label"]: row["average"] for row in cs.kickoff_rows(games)}
    assert kickoffs == {"14:00–16:59": 300, "19:00 or later": 300}
    phases = {row["label"]: row["average"] for row in cs.phase_rows(games)}
    assert phases == {"Regular season": 200, "Playoffs": 500}


def test_kickoff_band_ignores_unparsable_times():
    assert cs.kickoff_band("TBD") is None and cs.kickoff_band("") is None and cs.kickoff_band("09:30") == "Before 14:00"


def test_change_compares_the_same_number_of_first_regular_season_games():
    current = [_game(300, day=date(2026, 10, 3)), _game(300, day=date(2026, 10, 10))]
    previous = [
        _game(100, day=date(2025, 10, 4), season="25-26"),
        _game(200, day=date(2025, 10, 11), season="25-26"),
        _game(900, day=date(2025, 12, 6), season="25-26"),  # later in the season: not compared
        _game(5000, day=date(2026, 4, 1), season="25-26", phase="playoffs"),
    ]
    change, games = cs.like_for_like_change(current, previous)
    assert games == 2 and change == 1.0  # 300 against 150


def test_change_is_none_without_regular_season_games_on_either_side():
    assert cs.like_for_like_change([_game(100)], []) == (None, 0)
    assert cs.like_for_like_change([_game(100, phase="playoffs")], [_game(100, season="25-26")]) == (None, 0)
