from src import special_teams as sp


def _goal(minute, side, period=1, tag="regular"):
    return {"event_kind": "goal", "minute": minute, "period": period, "side": side, "tag": tag}


def _penalty(minute, side, period=1, tag="penalty_2"):
    return {"event_kind": "penalty", "minute": minute, "period": period, "side": side, "tag": tag}


def test_goal_with_a_man_up_is_powerplay_and_goal_with_a_man_down_is_shorthanded():
    events = [_penalty("05:00", "away"), _goal("05:40", "home"), _penalty("10:00", "home"), _goal("10:30", "home")]
    assert sp.goal_situations(events) == {1: sp.POWERPLAY, 3: sp.SHORTHANDED}


def test_powerplay_goal_ends_the_minor_penalty():
    events = [_penalty("05:00", "away"), _goal("05:30", "home"), _goal("05:50", "home")]
    assert sp.goal_situations(events) == {1: sp.POWERPLAY}


def test_goal_after_the_two_minutes_is_even_strength():
    events = [_penalty("05:00", "away"), _goal("07:00", "home")]
    assert sp.goal_situations(events) == {}


def test_equal_penalties_cancel_out():
    events = [_penalty("05:00", "away"), _penalty("05:00", "home"), _goal("05:30", "home")]
    assert sp.goal_situations(events) == {}


def test_double_minor_counts_twice_and_later_periods_use_the_game_clock():
    events = [_penalty("19:00", "away", tag="penalty_2and2"), _goal("19:50", "home"), _goal("00:30", "home", period=2)]
    assert sp.goal_situations(events) == {1: sp.POWERPLAY, 2: sp.POWERPLAY}


def test_own_goals_and_shootout_are_not_special_teams_goals():
    events = [_penalty("05:00", "away"), _goal("05:10", "home", tag="own_goal"), _goal("PS", "home", period=5)]
    assert sp.goal_situations(events) == {}


def test_label_situations_copies_events_and_only_adds_the_field_where_it_applies():
    events = [_penalty("05:00", "away"), _goal("05:40", "home")]
    labelled = sp.label_situations(events)
    assert labelled[1]["situation"] == sp.POWERPLAY and "situation" not in labelled[0]
    assert "situation" not in events[1]


def _specials(team, pp_goals, pp_opportunities, bp_goals_against, bp_opportunities, sh_goals=0):
    return sp.TeamSpecials(team, f"{team}.html", 7, pp_goals, pp_opportunities, bp_goals_against, bp_opportunities, sh_goals)


def test_league_table_computes_percentages_and_scatter_positions():
    table = sp.league_table([_specials("A", 7, 9, 2, 12), _specials("B", 2, 10, 6, 12, sh_goals=1), _specials("C", 4, 10, 4, 10)])
    rows = {row["team"]: row for row in table["rows"]}
    assert round(rows["A"]["pp_percent"], 1) == 77.8 and round(rows["A"]["bp_percent"], 1) == 83.3
    assert rows["B"]["bp_percent"] == 50.0 and rows["B"]["sh_goals"] == 1
    assert rows["A"]["x"] > rows["C"]["x"] > rows["B"]["x"] and rows["A"]["y"] > rows["C"]["y"] > rows["B"]["y"]
    assert all(0 <= row[axis] <= 100 for row in rows.values() for axis in ("x", "y"))
    assert 0 < table["scatter"]["mid_x"] < 100 and round(table["league_pp"], 1) == 44.8


def test_league_table_keeps_teams_without_opportunities_out_of_the_scatter():
    table = sp.league_table([_specials("A", 1, 4, 0, 3), _specials("B", 0, 0, 0, 0)])
    rows = {row["team"]: row for row in table["rows"]}
    assert rows["B"]["pp_percent"] is None and "x" not in rows["B"] and "x" in rows["A"]


def test_league_table_is_none_before_any_powerplay():
    assert sp.league_table([_specials("A", 0, 0, 0, 0)]) is None
    assert sp.league_table([]) is None
