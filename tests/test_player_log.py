from datetime import date

from src import player_log as pl


def _game(day, url, events, home_goals=3, away_goals=2, extra_time=False):
    return pl.LogGame(
        category="ch-26-27-regular-season",
        season="26/27",
        phase="regular-season",
        competition="L-UPL",
        day=date(2026, 10, day),
        url=url,
        home="A",
        away="B",
        home_goals=home_goals,
        away_goals=away_goals,
        extra_time=extra_time,
        events=tuple(events),
    )


def _goal(side, scorer, assist=None, situation=None, tag="regular"):
    event = {"event_kind": "goal", "side": side, "title_uid": scorer, "assist_uid": assist, "tag": tag}
    if situation:
        event["situation"] = situation
    return event


def test_log_counts_goals_assists_and_special_teams_goals_per_game():
    game = _game(1, "g1.html", [_goal("home", "p-anna", "p-cara", "pp"), _goal("home", "p-anna", None, "sh"), _goal("home", "p-dora", "p-anna"), _goal("away", "p-erik")])
    logs = pl.build_game_logs([game])
    anna = logs["p-anna"][0]
    assert (anna["goals"], anna["assists"], anna["points"], anna["pp"], anna["sh"]) == (2, 1, 3, 1, 1)
    assert logs["p-cara"][0]["assists"] == 1 and logs["p-cara"][0]["team"] == "A"
    assert logs["p-dora"][0]["result"] == pl.WIN
    assert logs["p-erik"][0]["team"] == "B" and logs["p-erik"][0]["result"] == pl.LOSS


def test_player_on_both_sides_of_a_goal_is_per_team_perspective():
    game = _game(1, "g1.html", [_goal("away", "p-dora", "p-erik")], home_goals=1, away_goals=2, extra_time=True)
    logs = pl.build_game_logs([game])
    assert logs["p-dora"][0]["score"] == "2:1" and logs["p-dora"][0]["result"] == pl.OT_WIN
    assert logs["p-erik"][0]["opponent"] == "A" and not logs["p-erik"][0]["home"]


def test_logs_are_newest_first_and_skip_own_goals_and_missing_ids():
    games = [
        _game(1, "g1.html", [_goal("home", "p-anna")]),
        _game(5, "g5.html", [_goal("home", "p-anna"), _goal("home", "", None), _goal("home", "p-own", tag="own_goal")]),
    ]
    logs = pl.build_game_logs(games)
    assert [row["url"] for row in logs["p-anna"]] == ["g5.html", "g1.html"]
    assert "p-own" not in logs and "" not in logs


def test_special_totals_add_up_over_the_rows():
    games = [_game(1, "g1.html", [_goal("home", "p-anna", None, "pp")]), _game(2, "g2.html", [_goal("home", "p-anna", None, "pp"), _goal("home", "p-anna", None, "sh")])]
    rows = pl.build_game_logs(games)["p-anna"]
    assert pl.special_totals(rows) == {"pp": 2, "sh": 1, "games": 2}
