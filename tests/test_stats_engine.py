from src.stats_engine import StatsEngine
from src.team_stats import TeamStats


def _team_stats(team: str, points: int, goal_difference: int, goals: int) -> TeamStats:
    return TeamStats(
        team=team,
        stats={
            "points": points,
            "goal_difference": goal_difference,
            "goals": goals,
            "non_numeric": "ignored",
        },
    )


def test_aggregate_stats_averages_only_numeric_fields():
    engine = StatsEngine()
    stats = [_team_stats("A", 10, 5, 20), _team_stats("B", 4, -1, 10)]

    aggregated = engine.aggregate_stats(stats)

    assert aggregated["points"] == 7.0
    assert aggregated["goal_difference"] == 2.0
    assert aggregated["goals"] == 15.0
    assert "non_numeric" not in aggregated


def test_split_by_rank_orders_by_points_then_goal_difference():
    engine = StatsEngine()
    all_stats = [
        _team_stats("A", points=10, goal_difference=2, goals=20),
        _team_stats("B", points=10, goal_difference=5, goals=18),
        _team_stats("C", points=7, goal_difference=4, goals=15),
    ]

    playoff, playdown, top4 = engine.split_by_rank(all_stats, playoff_cut=2, top4_cut=2)

    assert [t.team for t in playoff] == ["B", "A"]
    assert [t.team for t in playdown] == ["C"]
    assert [t.team for t in top4] == ["B", "A"]


def test_split_by_rank_uses_playoff_eligibility_when_provided():
    engine = StatsEngine()
    all_stats = [
        _team_stats("A", points=12, goal_difference=8, goals=25),
        _team_stats("B", points=10, goal_difference=5, goals=18),
        _team_stats("C", points=9, goal_difference=3, goals=16),
    ]

    playoff, playdown, top4 = engine.split_by_rank(
        all_stats,
        playoff_cut=2,
        top4_cut=2,
        playoff_eligible_teams={"B"},
    )

    assert [t.team for t in playoff] == ["B"]
    assert [t.team for t in playdown] == ["A", "C"]
    assert [t.team for t in top4] == ["B"]
