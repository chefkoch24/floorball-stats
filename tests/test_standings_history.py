from datetime import date

from src import standings_history as sh


def _game(day, home, away, home_goals, away_goals):
    if home_goals > away_goals:
        points = (3, 0)
    elif home_goals < away_goals:
        points = (0, 3)
    else:
        points = (1, 1)
    return sh.PlayedGame(day, home, away, home_goals, away_goals, *points)


def test_weekend_is_one_round_and_midweek_starts_a_new_one():
    days = [date(2026, 10, 2), date(2026, 10, 3), date(2026, 10, 4), date(2026, 10, 7), date(2026, 10, 10)]
    rounds = sh.group_rounds(days)
    assert [(item.first_day.day, item.last_day.day) for item in rounds] == [(2, 4), (7, 7), (10, 10)]
    assert [item.number for item in rounds] == [1, 2, 3]


def test_positions_follow_points_then_goal_difference_then_goals():
    games = [
        _game(date(2026, 9, 5), "A", "B", 3, 1),
        _game(date(2026, 9, 5), "C", "D", 6, 2),
        _game(date(2026, 9, 12), "B", "C", 5, 1),
        _game(date(2026, 9, 12), "D", "A", 2, 1),
    ]
    history = sh.standings_history(games, ["A", "B", "C", "D"])
    # Round 1: C (3 pts, +4), A (3 pts, +2), B and D (0 pts): B -2 ahead of D -4.
    # Round 2: everyone has 3 points; B +2, A +1, C 0, D -3.
    assert history.positions == {"A": [2, 2], "B": [3, 1], "C": [1, 3], "D": [4, 4]}
    assert (history.best("B"), history.worst("B")) == (1, 3)


def test_latest_round_takes_the_official_table_and_idle_teams_are_ranked():
    games = [_game(date(2026, 9, 5), "A", "B", 2, 2), _game(date(2026, 9, 12), "A", "B", 1, 1)]
    history = sh.standings_history(games, ["A", "B", "C"], official_ranks={"B": 1, "A": 2, "C": 3})
    assert history.positions["A"] == [1, 2]
    assert history.positions["B"] == [2, 1]
    assert history.positions["C"] == [3, 3]


def test_no_games_means_no_rounds():
    history = sh.standings_history([], ["A", "B"])
    assert history.rounds == [] and history.positions == {"A": [], "B": []}
    assert history.best("A") is None
