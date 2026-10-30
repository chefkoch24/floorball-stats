from datetime import date

from src import power_rankings as pr
from src import stakes as st


def _stakes(home_playoffs=None, away_playoffs=None, home_title=None, away_title=None, home_first=(0.1, 0.1, 0.1), away_first=(0.1, 0.1, 0.1)):
    def side(playoffs, title, first):
        values = {"first": first}
        if playoffs:
            values["playoffs"] = playoffs
        if title:
            values["title"] = title
        return values

    return {"home": side(home_playoffs, home_title, home_first), "away": side(away_playoffs, away_title, away_first)}


def test_situations_follow_their_priority():
    clinch = st.describe("1", "A", "B", _stakes((0.9, 1.0, 0.8), (0.5, 0.6, 0.4)))
    assert clinch.situation == "clinch" and "A" in clinch.sentence
    out = st.describe("2", "A", "B", _stakes((0.9, 0.95, 0.85), (0.08, 0.2, 0.0)))
    assert out.situation == "out" and "B" in out.sentence
    duel = st.describe("3", "A", "B", _stakes((0.45, 0.6, 0.3), (0.4, 0.55, 0.25)))
    assert duel.situation == "duel" and "45%" in duel.sentence and "40%" in duel.sentence
    # B is already all but through, so going from 99% to 99.5% is no "secures".
    swing = st.describe("4", "A", "B", _stakes((0.4, 0.58, 0.27), (0.99, 0.995, 0.98)))
    assert swing.situation == "swing" and "58%" in swing.sentence and "27%" in swing.sentence
    title = st.describe("5", "A", "B", _stakes((1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (0.6, 0.66, 0.55)))
    assert title.situation == "title"
    first = st.describe("6", "A", "B", _stakes((1.0, 1.0, 1.0), (1.0, 1.0, 1.0), home_first=(0.3, 0.4, 0.2)))
    assert first.situation == "first"
    assert st.describe("7", "A", "B", _stakes((1.0, 1.0, 1.0), (0.0, 0.0, 0.0))) is None


def test_wording_is_stable_per_game_and_varies_between_games():
    stakes = _stakes((0.4, 0.58, 0.27), (0.99, 0.995, 0.98))
    assert st.describe("10", "A", "B", stakes).sentence == st.describe("10", "A", "B", stakes).sentence
    assert len({st.describe(str(game_id), "A", "B", stakes).sentence for game_id in range(30)}) == len(st.TEMPLATES["swing"])


def test_simulation_reports_chances_after_a_win_and_a_loss():
    model = pr.LeagueModel(points=dict(pr.DEFAULT_POINTS), extra_time_rate=0.15, draw_rate=0.0)
    day = date(2026, 11, 1)
    remaining = [pr.GameResult("g1", "26-27", "regular-season", day, "18:00", "B", "C", False)]
    stakes = {}
    pr.simulate_season(
        ratings={"A": 1600, "B": 1500, "C": 1500},
        points_now={"A": 30, "B": 10, "C": 10},
        goal_diff_now={"A": 0, "B": 0, "C": 0},
        remaining=remaining,
        model=model,
        playoff_teams=2,
        simulations=600,
        seed="stakes",
        stakes=stakes,
    )
    now, win, loss = stakes["g1"]["home"]["playoffs"]
    # B and C fight for the second place: winning this game decides it.
    assert win == 1.0 and loss == 0.0 and 0.3 < now < 0.7
    assert "title" not in stakes["g1"]["home"]
