from datetime import date

from src import team_trends as tt
from src.player_insights import PlayerRef

ANNA = PlayerRef("p-anna", "Anna", "p-anna")
CARA = PlayerRef("p-cara", "Cara", "p-cara")


def _game(game_id, home, away, hg, ag, goals=(), extra=False, attendance=None, day=1):
    points = (3, 0) if hg > ag else (0, 3)
    if extra:
        points = (2, 1) if hg > ag else (1, 2)
    return tt.Game(str(game_id), f"g{game_id}.html", date(2026, 10, day), home, away, hg, ag, extra, tuple(goals), attendance, *points)


def test_streaks_count_from_the_latest_game():
    games = [
        _game(1, "A", "B", 1, 3, day=1),
        _game(2, "B", "A", 2, 4, day=2),
        _game(3, "A", "C", 3, 2, extra=True, day=3),
        _game(4, "C", "A", 1, 5, day=4),
    ]
    streaks = tt.team_streaks(games, "A")
    assert (streaks.wins, streaks.losses, streaks.unbeaten, streaks.longest_wins) == (3, 0, 3, 3)
    assert streaks.home_unbeaten == 1 and streaks.form == ["L", "W", "OTW", "W"]
    assert tt.team_streaks(games, "C").losses == 2


def test_point_streaks_break_on_a_game_without_points():
    games = [
        _game(1, "A", "B", 1, 0, [tt.Goal(5, "home", ANNA, CARA)], day=1),
        _game(2, "A", "B", 1, 0, [tt.Goal(5, "home", CARA)], day=2),
        _game(3, "A", "B", 1, 0, [tt.Goal(5, "home", CARA, ANNA)], day=3),
    ]
    streaks = tt.point_streaks(games, "A")
    assert streaks["p-cara"][1:] == (3, 2)
    assert streaks["p-anna"][1:] == (1, 0)


def test_records_timing_comebacks_and_crowds():
    comeback = _game(1, "A", "B", 3, 2, [
        tt.Goal(0.5, "away", CARA), tt.Goal(10, "away"), tt.Goal(41, "home", ANNA), tt.Goal(41.2, "home", ANNA), tt.Goal(55, "home", ANNA),
    ], attendance=900, day=1)
    blowout = _game(2, "B", "A", 8, 1, [tt.Goal(m, "home") for m in (2, 4, 6, 8, 10, 12, 14)] + [tt.Goal(30, "away")], attendance=1200, day=2)
    games = [comeback, blowout]
    records = {record.key: record for record in tt.season_records(games)}
    assert records["fastest-goal"].value == "00:30"
    assert records["fastest-pair"].value == "12 s"
    assert records["longest-run"].value == "7 goals"
    assert records["most-goals-player"].value == "3 goals"
    assert records["biggest-comeback"].value == "2 goals"
    assert records["biggest-win"].value == "8:1"
    assert records["biggest-crowd"].value == "1,200"

    timing = tt.goal_timing(games, "A")
    assert timing.blocks[0] == (0, 3) and timing.blocks[8] == (2, 0) and timing.blocks[11] == (1, 0)
    assert timing.periods == [(0, 9), (1, 0), (3, 0)]

    a = tt.lead_record(games, "A")
    assert (a.trailed, a.comeback_wins, a.trailed_points, a.blown_leads) == (2, 1, 3, 0)
    # Behind 0:2 at 40:00 in the comeback and 1:7 in the blowout.
    assert (a.trailed_after_two, a.won_after_trailing_two) == (2, 1)
    assert tt.lead_record(games, "B").blown_leads == 1

    assert tt.crowds(games) == {"A": (900.0, 1), "B": (1200.0, 1)}
    assert tt.team_goals(games) == {"A": 4, "B": 9}
