import pytest

from src import game_flow as gf


def test_lead_weighs_more_as_time_runs_out_and_regulation_end_decides():
    early = gf.live_win_probability(0.5, 5, 1)
    late = gf.live_win_probability(0.5, 58, 1)
    assert 0.5 < early < late < 1
    assert gf.live_win_probability(0.5, 60, 1) == 1.0
    assert gf.live_win_probability(0.5, 60, -2) == 0.0
    # Tied after regulation: overtime keeps only a little of the pre-game edge.
    assert 0.5 < gf.live_win_probability(0.7, 60, 0) < 0.7


def test_pregame_chance_is_the_starting_point():
    assert gf.live_win_probability(0.5, 0, 0) == pytest.approx(0.5)
    assert gf.live_win_probability(0.7, 0, 0) > 0.7  # the fit trusts the ratings a bit more than they say


def test_story_counts_lead_changes_ties_and_comeback():
    goals = [
        gf.FlowGoal(5, "away", "B1"),
        gf.FlowGoal(12, "away", "B2"),
        gf.FlowGoal(30, "home", "A1"),
        gf.FlowGoal(41, "home", "A2"),
        gf.FlowGoal(55, "home", "A3"),
    ]
    story = gf.game_story(0.5, goals, 3, 2)
    assert story.lead_changes == 1
    assert story.ties == 1
    assert story.largest_lead == {"home": 1, "away": 2}
    assert story.comeback == 2
    assert story.winner == "home"
    assert story.points[0] == (0.0, pytest.approx(0.5))
    assert story.points[-1] == (60.0, 1.0)
    minutes = [moment.goal.minute for moment in story.key_moments]
    assert len(minutes) == 3 and minutes == sorted(minutes)
    assert story.excitement > 1.0


def test_overtime_goal_ends_the_line_at_certainty():
    goals = [gf.FlowGoal(10, "home"), gf.FlowGoal(50, "away"), gf.FlowGoal(63.5, "away", "OT hero")]
    story = gf.game_story(0.6, goals, 1, 2, end_minute=63.5)
    assert story.end_minute == 63.5
    assert story.goals[-1][2] == 0.0
    assert story.points[-1] == (63.5, 0.0)
    assert gf.goal_minute(4, 3.5) == 63.5
    assert gf.goal_minute(2, 5) == 25


def test_blowout_is_less_exciting_than_a_close_game():
    blowout = gf.game_story(0.5, [gf.FlowGoal(m, "home") for m in (2, 5, 9, 15, 22)], 5, 0)
    close = gf.game_story(0.5, [gf.FlowGoal(10, "home"), gf.FlowGoal(30, "away"), gf.FlowGoal(50, "home"), gf.FlowGoal(57, "away"), gf.FlowGoal(59, "home")], 3, 2)
    assert close.excitement > blowout.excitement
