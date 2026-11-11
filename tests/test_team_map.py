import json
import math
from pathlib import Path

from src.team_map import build_team_map, find_location, spread

ROOT = Path(__file__).resolve().parents[1]
GERMANY_MEN = {"prefix": "", "name": "Germany", "season": "26-27"}


def test_spread_separates_markers_on_the_same_spot():
    points = [(100.0, 100.0)] * 3 + [(300.0, 300.0)]
    positions = spread(points, radius=10, width=600, height=600)
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            assert math.dist(positions[i], positions[j]) >= 20
    assert positions[3] == (300.0, 300.0)


def test_find_location_respects_league_prefix():
    locations = [{"team": "MFBC Leipzig", "league_prefixes": ["dew-"], "town": "Leipzig", "lat": 51.3, "lon": 12.4}]
    assert find_location("mfbc leipzig", "dew-", locations)["town"] == "Leipzig"
    assert find_location("MFBC Leipzig", "", locations) is None


def test_build_team_map_places_teams_and_reports_missing():
    teams = [{"team": "Berlin Rockets", "url": "berlin.html", "points": 9},
             {"team": "Unknown FC", "url": "x.html", "points": 3}]
    data = build_team_map(teams, GERMANY_MEN, logo_for=lambda team: "logo.png")
    assert data["missing"] == ["Unknown FC"]
    (marker,) = data["markers"]
    assert marker["place"] == 1 and marker["town"] == "Berlin" and marker["logo"] == "logo.png"
    assert 0 < marker["x"] < data["width"] and 0 < marker["y"] < data["height"]


def test_build_team_map_without_outline_returns_none():
    assert build_team_map([{"team": "A"}], {"prefix": "se-", "name": "Sweden"}) is None


def test_every_national_league_team_has_a_location():
    logos = json.loads((ROOT / "config" / "team_logos.json").read_text(encoding="utf-8"))["logos"]
    locations = json.loads((ROOT / "config" / "team_locations.json").read_text(encoding="utf-8"))["locations"]
    missing = []
    for record in logos:
        for prefix in record["league_prefixes"]:
            if prefix in ("cc-", "ccw-"):  # Champions Cup: no country map
                continue
            if not find_location(record["team"], prefix, locations):
                missing.append((prefix, record["team"]))
    assert missing == []


def test_every_country_outline_exists():
    from src.team_map import COUNTRY_MAPS, load_outline

    assert {iso2: bool(load_outline(iso2)) for iso2 in COUNTRY_MAPS.values()} == {iso2: True for iso2 in COUNTRY_MAPS.values()}
