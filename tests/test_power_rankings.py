from datetime import date

import pytest

from src import power_rankings as pr


def _game(game_id, day, home, away, home_goals=0, away_goals=0, played=True, decision=pr.REGULATION, season="26-27", phase="regular-season", points=None):
    if points is None and played:
        if home_goals == away_goals:
            points = (1, 1)
        elif decision == pr.REGULATION:
            points = (3, 0) if home_goals > away_goals else (0, 3)
        else:
            points = (2, 1) if home_goals > away_goals else (1, 2)
    return pr.GameResult(
        game_id=str(game_id),
        season=season,
        phase=phase,
        day=day,
        order="18:00",
        home=home,
        away=away,
        played=played,
        home_goals=home_goals,
        away_goals=away_goals,
        decision=decision,
        home_points=points[0] if points else None,
        away_points=points[1] if points else None,
    )


def test_win_probability_includes_home_advantage():
    assert pr.win_probability(1500, 1500) == pytest.approx(1 / (1 + 10 ** (-45 / 400)))
    assert pr.win_probability(1500, 1500, home_advantage=0) == pytest.approx(0.5)
    assert pr.win_probability(1700, 1500) > 0.75


def test_elo_rewards_bigger_margins_and_discounts_extra_time_wins():
    big = pr.run_elo([_game(1, date(2026, 9, 1), "A", "B", 10, 2)])
    small = pr.run_elo([_game(1, date(2026, 9, 1), "A", "B", 4, 3)])
    overtime = pr.run_elo([_game(1, date(2026, 9, 1), "A", "B", 4, 3, decision=pr.OVERTIME)])
    assert big.ratings["A"] > small.ratings["A"] > overtime.ratings["A"]
    # Zero sum: what one team gains the other loses.
    assert big.ratings["A"] + big.ratings["B"] == pytest.approx(3000)


def test_pregame_view_uses_ratings_before_the_game_and_skips_unplayed_updates():
    games = [
        _game(1, date(2026, 9, 1), "A", "B", 6, 1),
        _game(2, date(2026, 9, 8), "B", "A", played=False),
    ]
    run = pr.run_elo(games)
    home_rating, away_rating, p_home = run.pregame["2"]
    assert (home_rating, away_rating) == (run.ratings["B"], run.ratings["A"])
    assert p_home < 0.5
    assert len(run.history["A"]) == 1


def test_ratings_regress_between_seasons_and_newcomers_start_lower():
    games = [
        _game(1, date(2025, 9, 1), "A", "B", 8, 1, season="25-26"),
        _game(2, date(2026, 9, 1), "A", "C", played=False, season="26-27"),
    ]
    run = pr.run_elo(games)
    first_season = pr.run_elo(games[:1]).ratings["A"]
    expected = pr.BASE_RATING + (first_season - pr.BASE_RATING) * (1 - pr.SEASON_REGRESSION)
    assert run.ratings["A"] == pytest.approx(expected)
    assert run.ratings["C"] == pr.NEWCOMER_RATING


def test_league_model_reads_points_and_extra_time_share_from_results():
    day = date(2026, 9, 1)
    games = [_game(i, day, "A", "B", 3, 1) for i in range(16)] + [
        _game(100 + i, day, "A", "B", 3, 2, decision=pr.OVERTIME) for i in range(4)
    ]
    model = pr.league_model(games)
    assert model.points == {"win": 3, "extra_win": 2, "extra_loss": 1, "loss": 0, "draw": 1}
    assert model.extra_time_rate == pytest.approx(0.2)
    assert model.draw_rate == 0


def test_simulation_is_reproducible_and_respects_points_already_won():
    model = pr.LeagueModel(points=dict(pr.DEFAULT_POINTS), extra_time_rate=0.15, draw_rate=0.0)
    day = date(2026, 10, 1)
    remaining = [_game(i, day, home, away, played=False) for i, (home, away) in enumerate([("A", "B"), ("C", "D"), ("B", "C")])]
    args = dict(
        ratings={"A": 1600, "B": 1500, "C": 1500, "D": 1400},
        points_now={"A": 30, "B": 10, "C": 9, "D": 0},
        goal_diff_now={"A": 20, "B": 0, "C": 0, "D": -20},
        remaining=remaining,
        model=model,
        playoff_teams=2,
        simulations=500,
        seed="test",
    )
    first = pr.simulate_season(**args)
    again = pr.simulate_season(**args)
    assert [(item.team, item.playoffs) for item in first] == [(item.team, item.playoffs) for item in again]
    by_team = {item.team: item for item in first}
    # Three games left, at most nine points: A cannot be caught, D cannot reach the top two.
    assert by_team["A"].first == 1.0
    assert by_team["D"].playoffs == 0.0
    assert by_team["A"].title is None
    assert sum(item.top4 for item in first) == pytest.approx(4.0)


def test_playoff_bracket_with_play_in_crowns_one_champion_per_simulation():
    model = pr.LeagueModel(points=dict(pr.DEFAULT_POINTS), extra_time_rate=0.15, draw_rate=0.0)
    teams = [f"T{index}" for index in range(10)]
    rounds = [
        pr.PlayoffRound("Play-in", 4, 2),
        pr.PlayoffRound("Quarter-finals", 8, 4),
        pr.PlayoffRound("Semi-finals", 4, 4),
        pr.PlayoffRound("Final", 2, 1),
    ]
    projections = pr.simulate_season(
        ratings={team: 1700 - 30 * index for index, team in enumerate(teams)},
        points_now={team: 60 - 3 * index for index, team in enumerate(teams)},
        goal_diff_now={team: 0 for team in teams},
        remaining=[],
        model=model,
        playoff_teams=10,
        rounds=rounds,
        simulations=800,
        seed="bracket",
    )
    titles = {item.team: item.title for item in projections}
    assert sum(titles.values()) == pytest.approx(1.0)
    assert titles["T0"] > titles["T9"]
    assert all(item.playoffs == 1.0 for item in projections)
