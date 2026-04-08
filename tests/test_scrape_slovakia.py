from src.scrape_slovakia import MatchCard, _normalize_player_name, _parse_penalty_player, scrape_competition


class _FakeResponse:
    def __init__(self, text: str = ""):
        self.text = text

    def raise_for_status(self):
        return None


class _FakeSession:
    def get(self, url: str, timeout: int = 30):
        return _FakeResponse("<html></html>")


def _row(game_id: int, home: str, away: str, game_date: str) -> dict:
    return {
        "event_type": "goal",
        "event_team": home,
        "period": 1,
        "sortkey": "1-01:00",
        "game_id": game_id,
        "home_team_name": home,
        "away_team_name": away,
        "home_goals": 1,
        "guest_goals": 0,
        "goal_type": "goal",
        "penalty_type": None,
        "game_date": game_date,
        "game_start_time": "18:00",
        "attendance": 100,
        "game_status": "Played",
        "ingame_status": None,
        "result_string": "1:0",
        "scorer_name": "Player One",
        "assist_name": None,
        "scorer_number": None,
        "assist_number": None,
        "penalty_player_name": None,
    }


def test_scrape_competition_filters_placeholder_teams_for_regular_season(monkeypatch, tmp_path):
    schedule_urls = ["https://www.szfb.sk/sk/stats/results-date/1164/florbalova-extraliga-muzov"]
    matches = [
        MatchCard(match_id=1, match_url="https://example.test/match/1"),
        MatchCard(match_id=2, match_url="https://example.test/match/2"),
    ]

    monkeypatch.setattr("src.scrape_slovakia._new_session", lambda: _FakeSession())
    monkeypatch.setattr("src.scrape_slovakia._parse_schedule_matches", lambda html, schedule_url: matches)

    def _fake_parse_match_events(session, match):
        if match.match_id == 1:
            return [_row(1, "Real Team A", "Real Team B", "2026-02-10")]
        return [_row(2, "AAA", "DDD", "2026-02-20")]

    monkeypatch.setattr("src.scrape_slovakia._parse_match_events", _fake_parse_match_events)

    out_path = tmp_path / "slovakia.csv"
    df = scrape_competition(
        schedule_urls=schedule_urls,
        output_path=str(out_path),
        phase="regular-season",
        regular_season_end_date="2026-02-14",
        regular_season_games_per_team=22,
    )

    assert set(df["game_id"].tolist()) == {1}
    assert set(df["home_team_name"].tolist()) == {"Real Team A"}


def test_normalize_player_name_reorders_and_normalizes_casing():
    assert _normalize_player_name("PETRÁK, JAROSLAV") == "Jaroslav Petrák"
    assert _normalize_player_name("karel petrák") == "Karel Petrák"
    assert _normalize_player_name("Tomáš . Tvrdý") == "Tomáš Tvrdý"


def test_parse_penalty_player_strips_dot_separator_and_team_penalty():
    assert _parse_penalty_player("12:31 Tomáš . Tvrdý 2 Min.") == "Tomáš Tvrdý"
    assert _parse_penalty_player("2:00 Team Penalty 2 Min.") is None
