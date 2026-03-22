import json

from src.scrape import scrape_events


class _FakeResponse:
    def __init__(self, payload):
        self.content = json.dumps(payload).encode("utf-8")


def test_scrape_events_uses_event_team_player_roster(monkeypatch, tmp_path):
    game_payload = {
        "game_id": 123,
        "home_team_name": "Home Team",
        "guest_team_name": "Away Team",
        "date": "2026-03-21",
        "start_time": "18:00",
        "audience": 100,
        "game_status": "match_record_closed",
        "ingame_status": "period3",
        "result_string": "1:1",
        "players": {
            "home": [
                {"trikot_number": "7", "player_firstname": "Home", "player_name": "Seven"},
                {"trikot_number": "8", "player_firstname": "Home", "player_name": "Eight"},
            ],
            "guest": [
                {"trikot_number": "7", "player_firstname": "Away", "player_name": "Seven"},
                {"trikot_number": "8", "player_firstname": "Away", "player_name": "Eight"},
            ],
        },
        "events": [
            {
                "event_id": 1,
                "event_type": "goal",
                "event_team": "home",
                "period": 1,
                "home_goals": 1,
                "guest_goals": 0,
                "time": "10:00",
                "sortkey": "1-10:00",
                "number": "7",
                "assist": "8",
            },
            {
                "event_id": 2,
                "event_type": "penalty",
                "event_team": "guest",
                "period": 2,
                "home_goals": 1,
                "guest_goals": 1,
                "time": "12:00",
                "sortkey": "2-12:00",
                "number": "7",
                "assist": None,
                "penalty_type": "penalty_2",
            },
        ],
    }

    def _fake_request(method, url):
        if url.endswith("leagues/test/schedule.json"):
            return _FakeResponse([{"game_id": 123}])
        if url.endswith("games/123"):
            return _FakeResponse(game_payload)
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("src.scrape.requests.request", _fake_request)

    output_path = tmp_path / "events.csv"
    df = scrape_events(
        input_path="leagues/test/schedule.json",
        output_path=str(output_path),
        api_base="https://example.test/api/v2/",
    )

    home_goal = df[df["event_id"] == 1].iloc[0]
    away_penalty = df[df["event_id"] == 2].iloc[0]

    assert home_goal["event_team"] == "Home Team"
    assert home_goal["scorer_name"] == "Home Seven"
    assert home_goal["assist_name"] == "Home Eight"

    assert away_penalty["event_team"] == "Away Team"
    assert away_penalty["scorer_name"] == "Away Seven"
    assert away_penalty["penalty_player_name"] == "Away Seven"
