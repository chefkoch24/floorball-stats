"""Away travel distances for league pages, from the home towns in config/team_locations.json.

Distances are great-circle ("as the crow flies") between town centres, computed at build
time. Nothing is fetched: the only input besides the games is the committed locations file.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional

from src.team_map import _attr, find_location, load_locations

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = phi2 - phi1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def build_travel(teams: Iterable, games: Iterable, league: Optional[dict], *,
                 locations: Optional[list[dict]] = None) -> Optional[dict]:
    """Away travel per team, or None without any located team.

    `teams` are the standings rows in table order, `games` the league's game articles
    (home_team, away_team, game_state). Unplayed games count toward the season total,
    not the travelled total.
    """
    if not league:
        return None
    locations = load_locations() if locations is None else locations
    prefix = league.get("prefix", "")
    teams = list(teams)

    place, url, where = {}, {}, {}
    for index, team in enumerate(teams, start=1):
        name = str(_attr(team, "team", "") or "")
        location = find_location(name, prefix, locations) if name else None
        if location:
            place[name], url[name], where[name] = index, _attr(team, "url", "") or "", location
    if not where:
        return None

    def km(a: str, b: str) -> float:
        return haversine_km(where[a]["lat"], where[a]["lon"], where[b]["lat"], where[b]["lon"])

    travel = {name: {"team": name, "url": url[name], "town": where[name]["town"], "place": place[name],
                     "played_km": 0.0, "season_km": 0.0, "trips": 0, "trips_played": 0, "longest": None}
              for name in where}

    for game in games:
        home, away = str(_attr(game, "home_team", "") or ""), str(_attr(game, "away_team", "") or "")
        if home not in where or away not in where or home == away:
            continue
        distance = km(home, away)
        played = _attr(game, "game_state", "") != "scheduled"
        row = travel[away]
        row["season_km"] += distance
        row["trips"] += 1
        if played:
            row["played_km"] += distance
            row["trips_played"] += 1
        if not row["longest"] or distance > row["longest"]["km"]:
            row["longest"] = {"opponent": home, "town": where[home]["town"], "km": round(distance)}

    rows = [row for row in travel.values() if row["trips"]]
    for row in rows:
        row["played_km"], row["season_km"] = round(row["played_km"]), round(row["season_km"])
        row["average_km"] = round(row["season_km"] / row["trips"])
    rows.sort(key=lambda row: (-row["season_km"], row["place"]))
    most = rows[0]["season_km"] if rows else 0
    for row in rows:
        row["share"] = round(100 * row["season_km"] / most, 1) if most else 0

    return {
        "rows": rows,
        "total_km": sum(row["season_km"] for row in rows),
        "missing": [str(_attr(t, "team", "")) for t in teams if str(_attr(t, "team", "") or "") not in where],
    }
