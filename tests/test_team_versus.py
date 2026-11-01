import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins"))

import team_versus as plugin  # noqa: E402
from src import player_insights as pi  # noqa: E402
from src import run_stats_engine as engine  # noqa: E402
from src import team_trends as tt  # noqa: E402
from src import team_versus as tv  # noqa: E402

ANNA = pi.PlayerRef("p-anna", "Anna", "p-anna")
BEA = pi.PlayerRef("p-bea", "Bea", "p-bea")
CARA = pi.PlayerRef("p-cara", "Cara", "p-cara")


def _duel(game_id, home, away, hg, ag, day, goals=(), penalties=(), decision="", home_sp=None, away_sp=None, phase="regular-season"):
    game = tt.Game(str(game_id), f"g{game_id}.html", date(2026, 10, day), home, away, hg, ag, bool(decision), tuple(goals), penalties=tuple(penalties))
    return tv.Duel(game, "26-27", phase, decision, home_sp or tv.SideSpecials(), away_sp or tv.SideSpecials())


def test_results_are_newest_first_and_overtime_counts_as_an_overtime_win():
    duels = [
        _duel(1, "A", "B", 3, 1, day=1),
        _duel(2, "B", "A", 4, 3, day=9, decision="n.V."),
        _duel(3, "A", "B", 2, 2 + 1, day=5, decision="n.P.", phase="playoffs"),
    ]
    result = tv.versus(duels, ("A", "B"))
    assert [row["url"] for row in result["results"]] == ["g2.html", "g3.html", "g1.html"]
    assert result["results"][0]["decision"] == "n.V." and result["results"][1]["phase"] == "playoffs"
    assert result["results"][0]["season"] == "26/27" and result["results"][0]["score"] == "4:3"
    record_a, record_b = result["record"]["A"], result["record"]["B"]
    assert (record_a["W"], record_a["OTW"], record_a["OTL"], record_a["L"]) == (1, 0, 2, 0)
    assert (record_b["W"], record_b["OTW"], record_b["OTL"], record_b["L"]) == (0, 2, 0, 1)
    assert (record_a["goals_for"], record_a["goals_against"]) == (8, 8)


def test_scorers_count_only_the_teams_own_players_and_skip_own_goals():
    goals = [
        tt.Goal(5, "home", ANNA, BEA),
        tt.Goal(12, "home", ANNA, None),
        tt.Goal(30, "away", CARA, None),
        tt.Goal(31, "home", None, None),  # own goal of B
        tt.Goal(40, "home", BEA, ANNA),
    ]
    result = tv.versus([_duel(1, "A", "B", 4, 1, 1, goals)], ("A", "B"), lambda player: f"{player.uid}.html")
    rows = result["scorers"]["A"]
    assert [(row["name"], row["goals"], row["assists"], row["points"]) for row in rows] == [("Anna", 2, 1, 3), ("Bea", 1, 1, 2)]
    assert rows[0]["url"] == "p-anna.html"
    assert [row["name"] for row in result["scorers"]["B"]] == ["Cara"]


def test_a_player_without_an_id_in_some_games_is_one_row():
    anna_plain = pi.PlayerRef("A|Anna", "Anna", "")
    goals = [tt.Goal(5, "home", ANNA, None), tt.Goal(9, "home", anna_plain, None)]
    penalties = [tt.Penalty(3, "home", "2 min", anna_plain), tt.Penalty(9, "home", "2 min", ANNA)]
    result = tv.versus([_duel(1, "A", "B", 2, 0, 1, goals, penalties)], ("A", "B"), lambda player: f"{player.uid}.html" if player.uid else "")
    assert [(row["name"], row["goals"], row["url"]) for row in result["scorers"]["A"]] == [("Anna", 2, "p-anna.html")]
    assert [(row["name"], row["count"], row["url"]) for row in result["penalties"]["A"]["players"]] == [("Anna", 2, "p-anna.html")]


def test_scorer_ranking_breaks_ties_by_goals_then_name_and_is_limited():
    goals = [tt.Goal(minute, "home", PlayerRefFactory.make(index), None) for index, minute in enumerate(range(1, 9))]
    result = tv.versus([_duel(1, "A", "B", 8, 0, 1, goals)], ("A", "B"))
    assert len(result["scorers"]["A"]) == tv.TOP_PLAYERS
    assert [row["name"] for row in result["scorers"]["A"]] == ["P0", "P1", "P2", "P3", "P4"]


class PlayerRefFactory:
    @staticmethod
    def make(index):
        return pi.PlayerRef(f"p{index}", f"P{index}", f"p{index}")


def test_penalties_by_team_kind_and_player():
    penalties = [
        tt.Penalty(3, "home", "2 min", ANNA),
        tt.Penalty(9, "home", "2 min", ANNA),
        tt.Penalty(20, "home", "5 min", BEA),
        tt.Penalty(25, "away", "2+2", CARA),
        tt.Penalty(26, "away", "2 min", None),
    ]
    result = tv.versus([_duel(1, "A", "B", 0, 0, 1, penalties=penalties)], ("A", "B"))
    a, b = result["penalties"]["A"], result["penalties"]["B"]
    assert (a["total"], a["per_game"]) == (3, 3.0)
    assert a["kinds"] == {"2 min": 2, "5 min": 1}
    assert [(row["name"], row["count"]) for row in a["players"]] == [("Anna", 2), ("Bea", 1)]
    assert (b["total"], b["kinds"], [row["name"] for row in b["players"]]) == (2, {"2 min": 1, "2+2": 1}, ["Cara"])


def test_goal_timing_uses_five_minute_blocks_and_keeps_overtime_apart():
    goals = [tt.Goal(0.5, "home"), tt.Goal(4.99, "home"), tt.Goal(5.0, "away"), tt.Goal(59.9, "away"), tt.Goal(62.0, "home")]
    result = tv.versus([_duel(1, "A", "B", 3, 2, 1, goals, decision="n.V.")], ("A", "B"))["timing"]
    assert result["labels"][0] == "0–5" and result["labels"][-1] == "55–60" and len(result["labels"]) == 12
    assert result["goals"]["A"][0] == 2 and result["goals"]["B"][1] == 1 and result["goals"]["B"][11] == 1
    assert result["overtime"] == {"A": 1, "B": 0}


def test_special_teams_percentages_and_time():
    home = tv.SideSpecials(powerplay=4, powerplay_goals=1, boxplay=2, boxplay_goals_against=1, powerplay_seconds=300, boxplay_seconds=120)
    away = tv.SideSpecials(powerplay=2, powerplay_goals=1, boxplay=4, boxplay_goals_against=3, powerplay_seconds=120, boxplay_seconds=300)
    result = tv.versus([_duel(1, "A", "B", 1, 1, 1, home_sp=home, away_sp=away)], ("A", "B"))["special"]
    assert result["A"]["powerplay_pct"] == 25.0 and result["A"]["boxplay_pct"] == 50.0
    assert result["B"]["powerplay_pct"] == 50.0 and result["B"]["boxplay_pct"] == 25.0
    assert (result["A"]["powerplay_time"], result["A"]["boxplay_time"]) == ("5:00", "2:00")
    assert (result["B"]["powerplay_time"], result["B"]["boxplay_time"]) == ("2:00", "5:00")


def test_special_teams_without_chances_have_no_percentage_and_partial_time_is_hidden():
    first = _duel(1, "A", "B", 1, 0, 1, home_sp=tv.SideSpecials(powerplay_seconds=60, boxplay_seconds=0), away_sp=tv.SideSpecials(powerplay_seconds=0, boxplay_seconds=60))
    second = _duel(2, "A", "B", 1, 0, 2)  # seconds unknown
    result = tv.versus([first, second], ("A", "B"))["special"]["A"]
    assert result["powerplay_pct"] is None and result["boxplay_pct"] is None
    assert result["powerplay_time"] is None and result["boxplay_time"] is None


def test_time_of_a_team_falls_back_to_the_opponents_other_side():
    # Only the home side carries seconds: its man-up time is the away side's man-down time.
    duel = _duel(1, "A", "B", 1, 0, 1, home_sp=tv.SideSpecials(powerplay_seconds=90, boxplay_seconds=30))
    result = tv.versus([duel], ("A", "B"))["special"]
    assert (result["A"]["powerplay_time"], result["A"]["boxplay_time"]) == ("1:30", "0:30")
    assert (result["B"]["powerplay_time"], result["B"]["boxplay_time"]) == ("0:30", "1:30")


def test_league_payload_indexes_pairs_and_opponents_by_team():
    duels = [_duel(1, "Zed", "Ann", 2, 1, 1), _duel(2, "Ann", "Zed", 1, 0, 2), _duel(3, "Bob", "Zed", 3, 3 + 1, 3, decision="n.V.")]
    payload = tv.league_payload(duels, {"Ann": "ann.html"})
    assert [team["name"] for team in payload["teams"]] == ["Ann", "Bob", "Zed"]
    assert payload["teams"][0]["url"] == "ann.html" and payload["teams"][1]["url"] == ""
    assert set(payload["pairs"]) == {"0-2", "1-2"}
    assert payload["opponents"] == {"0": [2], "1": [2], "2": [0, 1]}
    assert len(payload["pairs"]["0-2"]["results"]) == 2


def _events():
    return [
        {"minute": "05:00", "period": 1, "side": "home", "event_kind": "penalty", "tag": "penalty_2"},
        {"minute": "06:00", "period": 1, "side": "away", "event_kind": "goal", "tag": "goal"},
        {"minute": "01:00", "period": 2, "side": "away", "event_kind": "penalty", "tag": "penalty_2and2"},
        {"minute": "40:00", "period": 2, "side": "break", "event_kind": "break"},
        {"minute": "00:30", "period": 5, "side": "home", "event_kind": "goal", "tag": "goal"},
    ]


def test_man_advantage_seconds_is_none_while_the_engine_lacks_the_stat(monkeypatch):
    monkeypatch.delattr(engine, "stat_powerplay_seconds", raising=False)
    assert tv.man_advantage_seconds(_events(), "A", "B") is None


def test_man_advantage_seconds_calls_the_engine_with_a_frame_of_the_payload(monkeypatch):
    seen = {}

    def fake(frame, team):
        seen[team] = frame
        return {"A": 10, "B": 20}[team]

    monkeypatch.setattr(engine, "stat_powerplay_seconds", fake, raising=False)
    assert tv.man_advantage_seconds(_events(), "A", "B") == (10, 20)
    frame = seen["A"]
    assert list(frame["event_type"]) == [engine.EVENT_PENALTY, engine.EVENT_GOAL, engine.EVENT_PENALTY]
    assert list(frame["event_team"]) == ["A", "B", "B"]
    assert list(frame["time_in_s"]) == [300, 360, 1200 + 60]
    assert list(frame["penalty_type"])[0] == "penalty_2" and list(frame["period"]) == [1, 1, 2]
    assert tv.man_advantage_seconds([{"event_kind": "break", "side": "break"}], "A", "B") is None


def _article(**extra):
    events = [
        {"minute": "05:00", "period": 1, "team": "Alpha", "side": "home", "event_kind": "goal", "title": "Anna", "title_uid": "p-anna", "assist": "Bea", "assist_uid": "p-bea", "tag": "goal"},
        {"minute": "10:00", "period": 1, "team": "Beta", "side": "away", "event_kind": "penalty", "title": "2 min penalty", "assist": "Cara", "assist_uid": "p-cara", "tag": "penalty_2"},
    ]
    fields = {
        "url": "g1.html", "slug": "g1", "date": date(2026, 10, 1), "type": "game", "game_id": "1", "game_state": "played",
        "home_team": "Alpha", "away_team": "Beta", "home_goals": "3", "away_goals": "4", "result_string": "3:4 (1:1, 1:1, 1:1, 0:1) n.V.",
        "game_events_b64": pi.encode_events(events),
        "home_powerplay": "0", "home_goals_in_powerplay": "0", "home_boxplay": "1", "home_goals_against_in_boxplay": "1",
        "away_powerplay": "1", "away_goals_in_powerplay": "1", "away_boxplay": "0", "away_goals_against_in_boxplay": "0",
    }
    return SimpleNamespace(**{**fields, **extra})


def test_plugin_reads_a_game_article_into_a_duel(monkeypatch):
    monkeypatch.delattr(engine, "stat_powerplay_seconds", raising=False)
    duel = plugin.duel_of(_article(), "26-27", "playoffs")
    assert (duel.game.home, duel.game.away, duel.decision, duel.phase) == ("Alpha", "Beta", "n.V.", "playoffs")
    assert [goal.scorer.name for goal in duel.game.goals] == ["Anna"] and duel.game.penalties[0].player.name == "Cara"
    assert (duel.home.boxplay, duel.home.boxplay_goals_against, duel.away.powerplay, duel.away.powerplay_goals) == (1, 1, 1, 1)
    assert duel.home.powerplay_seconds is None


def test_plugin_prefers_stored_seconds_and_falls_back_to_the_engine(monkeypatch):
    monkeypatch.setattr(engine, "stat_powerplay_seconds", lambda frame, team: {"Alpha": 0, "Beta": 120}[team], raising=False)
    rebuilt = plugin.duel_of(_article(), "26-27", "regular-season")
    assert (rebuilt.home.powerplay_seconds, rebuilt.home.boxplay_seconds, rebuilt.away.powerplay_seconds) == (0, 120, 120)
    stored = plugin.duel_of(_article(home_powerplay_seconds="45", home_boxplay_seconds="15"), "26-27", "regular-season")
    assert (stored.home.powerplay_seconds, stored.home.boxplay_seconds) == (45, 15)


@pytest.mark.parametrize("prefix,key", [("se-", "se"), ("", "de"), ("sew-", "sew")])
def test_league_key(prefix, key):
    assert plugin.league_key(prefix) == key


def _payload():
    duels = [_duel(1, "Zed", "Ann", 2, 1, 1), _duel(2, "Ann", "Zed", 1, 1 + 1, 2, decision="n.V."), _duel(3, "Bob", "Zed", 3, 0, 3)]
    return tv.league_payload(duels)


def test_team_rows_give_the_record_against_each_opponent_in_table_order():
    rows = tv.team_rows(_payload(), "Zed", ["Bob", "Ann", "Cid"])
    assert [row["team"] for row in rows] == ["Bob", "Ann"]  # Cid never met Zed
    assert (rows[0]["games"], rows[0]["W"], rows[0]["L"], rows[0]["goals_for"], rows[0]["goals_against"]) == (1, 0, 1, 0, 3)
    assert (rows[1]["games"], rows[1]["W"], rows[1]["OTW"], rows[1]["goals_for"], rows[1]["goals_against"]) == (2, 1, 1, 4, 2)
    assert [row["team"] for row in tv.team_rows(_payload(), "Zed")] == ["Ann", "Bob"]
    assert tv.team_rows(_payload(), "Nobody") == []


def test_plugin_links_every_row_to_the_page_with_both_teams_selected():
    assert plugin.page_link("ch") == "head-to-head.html?league=ch"
    assert plugin.page_link("sew", "IK Sirius", "Pixbo & Co") == "head-to-head.html?league=sew&a=IK+Sirius&b=Pixbo+%26+Co"


def test_team_articles_get_their_record_against_the_rest_of_their_season_phase():
    def team(name, rank):
        return SimpleNamespace(team=name, title=name, rank=str(rank), category=SimpleNamespace(slug="se-26-27-regular-season"))

    teams = {"se-26-27-regular-season": [team("Zed", 1), team("Ann", 2), team("Bob", 3)], "xx-26-27-regular-season": [team("Q", 1)]}
    context = lambda slug: {"prefix": "se-", "season": "26-27", "phase": "regular-season"} if slug.startswith("se-") else None  # noqa: E731
    plugin.attach_team_records({"se": _payload()}, teams, context, {"se-"})
    zed, ann = teams["se-26-27-regular-season"][0], teams["se-26-27-regular-season"][1]
    assert [row["team"] for row in zed.versus["rows"]] == ["Ann", "Bob"]
    assert zed.versus["rows"][0]["href"] == "head-to-head.html?league=se&a=Zed&b=Ann"
    assert [row["team"] for row in ann.versus["rows"]] == ["Zed"] and ann.versus["league_href"] == "head-to-head.html?league=se"
    assert not hasattr(teams["xx-26-27-regular-season"][0], "versus")
