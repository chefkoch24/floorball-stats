import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins"))

import leaders  # noqa: E402


def _player(name, games, goals, assists, pim, league="SSL"):
    return {
        "name": name, "url": f"{name}.html", "team": "Team", "crest": 1, "initials": "T",
        "league": league, "country": "Sweden", "games": games, "goals": goals,
        "assists": assists, "points": goals + assists, "pim": pim,
        "ppg": (goals + assists) / games if games else 0.0,
    }


def _team(name, games, pp=None, pp_count=0, ga=None):
    return {
        "name": name, "url": f"{name}.html", "team": name, "crest": 1, "initials": "T",
        "league": "SSL", "country": "Sweden", "games": games, "pp": pp, "pp_count": pp_count,
        "bp": None, "bp_count": 0, "gf": None, "ga": ga, "pen": None,
    }


def _boards(players=(), teams=()):
    return {board["key"]: board for board in leaders.build_leaderboards(list(players), list(teams))}


def test_points_rank_across_leagues_with_goals_as_tiebreak():
    boards = _boards([
        _player("A", 6, 4, 6, 0, league="SSL"),
        _player("B", 8, 7, 3, 0, league="1. FBL Herren"),
        _player("C", 6, 9, 0, 0, league="F-Liiga"),
    ])
    assert [e["name"] for e in boards["points"]["entries"]] == ["B", "A", "C"]
    assert [e["rank"] for e in boards["points"]["entries"]] == [1, 2, 3]
    assert boards["points"]["entries"][0]["detail"] == "7 G · 3 A · 8 GP"


def test_penalty_minutes_skip_players_without_penalties():
    boards = _boards([_player("Clean", 5, 1, 1, 0), _player("Rough", 5, 0, 0, 12)])
    assert [e["name"] for e in boards["penalty-minutes"]["entries"]] == ["Rough"]
    assert boards["penalty-minutes"]["entries"][0]["value"] == "12"


def test_rates_need_minimum_games_and_special_teams_sample():
    boards = _boards(
        [_player("OneNight", 1, 5, 0, 0), _player("Steady", 3, 4, 2, 0)],
        [_team("Small", 4, pp=80.0, pp_count=2), _team("Big", 4, pp=30.0, pp_count=10)],
    )
    assert [e["name"] for e in boards["points-per-game"]["entries"]] == ["Steady"]
    assert boards["points-per-game"]["entries"][0]["value"] == "2.00"
    assert [e["name"] for e in boards["power-play"]["entries"]] == ["Big"]


def test_fewest_goals_against_sorts_ascending_and_top_ten_only():
    teams = [_team(f"T{i}", 5, ga=float(i)) for i in range(12, 0, -1)]
    entries = _boards(teams=teams)["goals-against"]["entries"]
    assert len(entries) == leaders.TOP
    assert entries[0]["name"] == "T1"


def test_empty_division_has_empty_boards():
    assert all(not board["entries"] for board in _boards().values())
