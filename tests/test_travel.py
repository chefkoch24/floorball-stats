from src.travel import build_travel, haversine_km

LOCATIONS = [
    {"team": "Leipzig A", "league_prefixes": [""], "town": "Leipzig", "lat": 51.34, "lon": 12.375},
    {"team": "Leipzig B", "league_prefixes": [""], "town": "Leipzig", "lat": 51.34, "lon": 12.375},
    {"team": "Munich", "league_prefixes": [""], "town": "München", "lat": 48.137, "lon": 11.575},
]
LEAGUE = {"prefix": "", "name": "Germany"}
TEAMS = [{"team": "Leipzig A", "url": "a.html"}, {"team": "Munich", "url": "m.html"},
         {"team": "Leipzig B", "url": "b.html"}, {"team": "Nowhere", "url": "n.html"}]


def game(home, away, state="played", hp=3, ap=0, date="2026-10-01"):
    return {"home_team": home, "away_team": away, "game_state": state, "home_points": hp,
            "away_points": ap, "home_goals": hp, "away_goals": ap, "date": date, "url": f"{home}-{away}.html"}


def test_haversine_berlin_munich():
    assert round(haversine_km(52.52, 13.405, 48.137, 11.575)) == 504


def test_travel_counts_only_away_games_and_splits_played_from_season():
    games = [game("Munich", "Leipzig A"), game("Leipzig A", "Munich"),
             game("Munich", "Leipzig A", state="scheduled", hp=None, ap=None)]
    data = build_travel(TEAMS, games, LEAGUE, locations=LOCATIONS)
    rows = {row["team"]: row for row in data["rows"]}
    leg = round(haversine_km(51.34, 12.375, 48.137, 11.575))
    assert rows["Leipzig A"]["season_km"] == round(2 * haversine_km(51.34, 12.375, 48.137, 11.575))
    assert rows["Leipzig A"]["played_km"] == leg
    assert rows["Leipzig A"]["trips"] == 2 and rows["Leipzig A"]["trips_played"] == 1
    assert rows["Munich"]["season_km"] == leg
    assert data["rows"][0]["team"] == "Leipzig A" and data["rows"][0]["share"] == 100
    assert data["missing"] == ["Nowhere"]


def test_no_located_team_returns_none():
    assert build_travel([{"team": "Nowhere"}], [], LEAGUE, locations=LOCATIONS) is None
