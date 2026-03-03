import pandas as pd

from src.utils import add_penalties, add_points, safe_div, transform_in_seconds


def test_transform_in_seconds_creates_expected_values_without_mutating_input():
    original = pd.DataFrame({"sortkey": ["1-00:30", "2-01:10", "4-00:05"]})

    transformed = transform_in_seconds(original)

    assert "time_in_s" not in original.columns
    assert transformed["time_in_s"].tolist() == [30, 1270, 3605]


def test_add_points_regular_and_overtime_outcomes():
    regular_win = {
        "home_team_name": "A",
        "home_goals": 5,
        "guest_goals": 3,
        "period": 3,
    }
    overtime_loss = {
        "home_team_name": "A",
        "home_goals": 2,
        "guest_goals": 3,
        "period": 4,
    }
    shootout_win = {
        "home_team_name": "A",
        "home_goals": 5,
        "guest_goals": 4,
        "period": 5,
    }

    assert add_points("A", regular_win) == (3, "wins", 2)
    assert add_points("A", overtime_loss) == (1, "over_time_losses", -1)
    assert add_points("A", shootout_win) == (2, "over_time_wins", 1)


def test_safe_div_handles_percent_and_default():
    assert safe_div(3, 2, rounding=2) == 1.5
    assert safe_div(1, 4, rounding=2, in_percent=True) == 25.0
    assert safe_div(1, 0, default="n.a.") == "n.a."


def test_add_penalties_expands_double_minors_and_match_penalties():
    assert add_penalties("penalty_2", [], 100) == [100]
    assert add_penalties("penalty_2and2", [], 100) == [100, 100]
    assert add_penalties("penalty_ms_full", [], 100) == [100, 100]
