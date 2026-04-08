from src.scrape_switzerland import GameDetails, _parse_game_events


def test_parse_game_events_reconstructs_running_score():
    html = """
    <table class="su-result">
      <tbody>
        <tr><td>10:00</td><td>Torschütze</td><td>Home</td><td>Player H2</td></tr>
        <tr><td>12:00</td><td>Strafe (2 Minuten)</td><td>Away</td><td>Player A</td></tr>
        <tr><td>05:00</td><td>Torschütze</td><td>Home</td><td>Player H1</td></tr>
        <tr><td>01:00</td><td>Torschütze</td><td>Away</td><td>Player A1</td></tr>
      </tbody>
    </table>
    """
    details = GameDetails(
        home_team="Home",
        away_team="Away",
        game_date="2026-03-01",
        game_start_time="16:00",
        result_string="2:1 (1:1, 1:0, 0:0)",
        goals_home=2,
        goals_away=1,
        header_text=None,
    )

    events = _parse_game_events(html, game_id=1, details=details)
    goals = [e for e in events if e["event_type"] == "goal" and e["period"] <= 4]
    goals = sorted(goals, key=lambda e: e["sortkey"])
    penalties = [e for e in events if e["event_type"] == "penalty"]

    assert [(g["home_goals"], g["guest_goals"]) for g in goals] == [(0, 1), (1, 1), (2, 1)]
    assert len(penalties) == 1
    assert penalties[0]["home_goals"] == 2
    assert penalties[0]["guest_goals"] == 1


def test_parse_game_events_keeps_shootout_marker_on_final_score():
    html = """
    <table class="su-result">
      <tbody>
        <tr><td>03:00</td><td>Torschütze</td><td>Home</td><td>Player H</td></tr>
        <tr><td>04:00</td><td>Torschütze</td><td>Away</td><td>Player A</td></tr>
      </tbody>
    </table>
    """
    details = GameDetails(
        home_team="Home",
        away_team="Away",
        game_date="2026-03-01",
        game_start_time="16:00",
        result_string="2:1 n.P.",
        goals_home=2,
        goals_away=1,
        header_text=None,
    )

    events = _parse_game_events(html, game_id=2, details=details)
    shootout = [e for e in events if e["period"] == 5]

    assert len(shootout) == 1
    assert shootout[0]["home_goals"] == 2
    assert shootout[0]["guest_goals"] == 1


def test_parse_game_events_expands_abbreviated_names_from_lookup():
    html = """
    <table class="su-result">
      <tbody>
        <tr><td>03:00</td><td>Torschütze</td><td>Home</td><td>D. Bürger (Assist: M. Gattnar)</td></tr>
        <tr><td>04:00</td><td>Strafe (2 Minuten)</td><td>Home</td><td>D. Bürger</td></tr>
      </tbody>
    </table>
    """
    details = GameDetails(
        home_team="Home",
        away_team="Away",
        game_date="2026-03-01",
        game_start_time="16:00",
        result_string="1:0",
        goals_home=1,
        goals_away=0,
        header_text=None,
    )
    lookup = {
        "Home": {
            "d. bürger": "Dominik Bürger",
            "m. gattnar": "Martin Gattnar",
        }
    }

    events = _parse_game_events(html, game_id=3, details=details, player_name_lookup=lookup)
    goal = next(e for e in events if e["event_type"] == "goal")
    penalty = next(e for e in events if e["event_type"] == "penalty")

    assert goal["scorer_name"] == "Dominik Bürger"
    assert goal["assist_name"] == "Martin Gattnar"
    assert penalty["penalty_player_name"] == "Dominik Bürger"
