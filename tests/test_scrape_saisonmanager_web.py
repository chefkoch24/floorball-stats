from datetime import date
from pathlib import Path

import pytest

from src.scrape_saisonmanager_web import SaisonmanagerWebClient, parse_game_html, parse_schedule_html


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "saisonmanager"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_schedule_page_lists_played_and_upcoming_games_only():
    games = parse_schedule_html(_fixture("all-matches.html"))

    assert [game["game_id"] for game in games] == [58803, 58804, 58934]
    assert games[0] == {
        "game_id": 58803,
        "date": "2026-09-12",
        "start_time": "18:00",
        "home_team_name": "Blau-Weiß 96 Schenefeld",
        "guest_team_name": "Unihockey Igels Dresden",
        "result_string": "4:12",
        "played": True,
        "game_day": 1,
    }
    assert games[1]["result_string"] == "5:4 n.V."
    assert games[2]["played"] is False
    assert games[2]["result_string"] is None


def test_game_page_matches_the_former_api_payload():
    # Expectations taken from the API export of the same game (25-26 playoffs).
    game = parse_game_html(_fixture("game-45906.html"), 45906)

    assert game["home_team_name"] == "SSF Dragons Bonn"
    assert game["guest_team_name"] == "SC DHfK Leipzig"
    assert (game["date"], game["start_time"], game["audience"]) == ("2026-04-04", "18:00", 346)
    assert game["result_string"] == "6:7 n. PS"
    assert game["ingame_status"] == "penalty_shots"
    assert len(game["players"]["home"]) == 20 and len(game["players"]["guest"]) == 20

    events = game["events"]
    assert len(events) == 17
    assert [e["event_type"] for e in events].count("goal") == 13
    first_goal = next(e for e in events if e["event_type"] == "goal")
    assert (first_goal["event_team"], first_goal["sortkey"], first_goal["number"], first_goal["assist"]) == (
        "guest",
        "1-01:08",
        "47",
        "65",
    )
    penalty_shot = next(e for e in events if e["sortkey"] == "1-19:23")
    assert penalty_shot["goal_type"] == "penalty_shot"
    shootout = events[-1]
    assert (shootout["period"], shootout["sortkey"], shootout["guest_goals"], shootout["goal_type"]) == (
        5,
        "5-10:00",
        7,
        "penalty_shot",
    )
    assert events[0]["penalty_type"] == "penalty_ms_tech"
    timeout = next(e for e in events if e["event_type"] == "timeout")
    assert timeout["home_goals"] is None and timeout["guest_goals"] is None


def test_client_serves_upcoming_games_from_schedule_and_settled_games_from_cache(tmp_path):
    (tmp_path / "game-45906.html").write_text(_fixture("game-45906.html"), encoding="utf-8")
    client = SaisonmanagerWebClient(cache_dir=tmp_path, cache_only=True, today=date(2026, 10, 25))
    client.schedule = {entry["game_id"]: entry for entry in parse_schedule_html(_fixture("all-matches.html"))}

    upcoming = client.get_game(58934)
    assert upcoming["events"] == [] and upcoming["game_status"] == "Scheduled"
    assert client.get_game(45906)["result_string"] == "6:7 n. PS"
    with pytest.raises(LookupError):
        client.get_game(58803)


def test_scrape_events_uses_web_pages_without_api_key(monkeypatch, tmp_path):
    from src import scrape, scrape_saisonmanager_web

    monkeypatch.delenv("SAISONMANAGER_API_KEY", raising=False)

    class _FakeWebClient:
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return None

        def get_json(self, path):
            if path == "leagues/1963/schedule.json":
                return [{"game_id": 45906}]
            assert path == "games/45906"
            return parse_game_html(_fixture("game-45906.html"), 45906)

    monkeypatch.setattr(scrape_saisonmanager_web, "SaisonmanagerWebClient", lambda: _FakeWebClient())

    df = scrape.scrape_events("leagues/1963/schedule.json", str(tmp_path / "events.csv"))

    first_goal = df[df["event_type"] == "goal"].iloc[0]
    assert first_goal["event_team"] == "SC DHfK Leipzig"
    assert first_goal["scorer_name"] == "Lukáš Lhota"
    assert first_goal["assist_name"] == "Tuomas Hirn"
    assert "player_name_hint" not in df.columns


def test_own_goal_is_tagged_for_the_stats_engine():
    from src.scrape_saisonmanager_web import _parse_history_item
    from bs4 import BeautifulSoup

    item = BeautifulSoup(
        '<fb-match-history-item><div>'
        '<div><img alt="Berlin Rockets"></div><div>Eigentor</div><div>5:5</div><div>Tor</div>'
        '<div>07\' 54"</div></div></fb-match-history-item>',
        "html.parser",
    ).select_one("fb-match-history-item")

    event = _parse_history_item(item, "Berlin Rockets", "UHC Sparkasse Weißenfels")

    assert event["event_type"] == "goal" and event["note"] == "Eigentor" and event["player_id"] is None


def test_trimmed_cache_html_parses_like_the_full_page():
    from src.scrape_saisonmanager_web import trim_game_html

    full = parse_game_html(_fixture("game-45906.html"), 45906)
    trimmed = parse_game_html(trim_game_html(_fixture("game-45906.html")), 45906)

    assert trimmed == full
