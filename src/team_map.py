"""Team map for league pages: club logos at their home towns on the country outline.

Inputs are committed files, nothing is fetched at build time:
- config/maps/<iso2>.json, built once by scripts/build_country_outline.py (Natural Earth)
- config/team_locations.json, the curated home town per team

`build_team_map` projects every team of a league onto the outline and spreads markers
that would overlap (several clubs in one town or neighbouring towns), keeping a short
leader line to the real location.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Callable, Iterable, Optional

ROOT = Path(__file__).resolve().parents[1]
MAPS_DIR = ROOT / "config" / "maps"
LOCATIONS_PATH = ROOT / "config" / "team_locations.json"

# League name (pelicanconf LEAGUES "name") -> outline file in config/maps.
COUNTRY_MAPS = {
    "Germany": "de",
    "Sweden": "se",
    "Finland": "fi",
    "Czech Republic": "cz",
    "Switzerland": "ch",
    "Slovakia": "sk",
    "Latvia": "lv",
}

# Maps render with their longer side at DISPLAY_SIZE px (narrower on phones). Markers are
# sized against that longer side, so a logo looks the same on a tall and a wide country.
DISPLAY_SIZE = 640.0
MARKER_RADIUS = 16.0  # px at full display size
MARKER_GAP = 1.08  # minimum centre distance, in marker diameters


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_outline(iso2: str, maps_dir: Path = MAPS_DIR) -> Optional[dict]:
    outline = _load_json(maps_dir / f"{iso2}.json")
    if not isinstance(outline, dict) or not outline.get("country"):
        return None
    return outline


def load_locations(path: Path = LOCATIONS_PATH) -> list[dict]:
    data = _load_json(path)
    records = data.get("locations") if isinstance(data, dict) else None
    return [r for r in records or [] if isinstance(r, dict)]


def find_location(team: str, prefix: str, locations: Iterable[dict]) -> Optional[dict]:
    key = str(team or "").strip().casefold()
    for record in locations:
        if str(record.get("team", "")).strip().casefold() != key:
            continue
        if prefix not in (record.get("league_prefixes") or []):
            continue
        try:
            lat, lon = float(record["lat"]), float(record["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        return {"town": record.get("town") or "", "lat": lat, "lon": lon}
    return None


def project(lat: float, lon: float, projection: dict) -> tuple[float, float]:
    padding = projection["padding"]
    x = padding + (lon - projection["west"]) * projection["kx"] * projection["scale"]
    y = padding + (projection["north"] - lat) * projection["scale"]
    return x, y


def spread(points: list[tuple[float, float]], radius: float, width: float, height: float,
           iterations: int = 300) -> list[tuple[float, float]]:
    """Move markers apart until no two overlap, each pulled lightly back to its anchor.

    Deterministic: markers that start on the same spot get evenly spaced start angles.
    """
    n = len(points)
    positions = [list(p) for p in points]
    seen: dict[tuple[float, float], list[int]] = {}
    for index, (x, y) in enumerate(points):
        seen.setdefault((round(x, 1), round(y, 1)), []).append(index)
    for group in seen.values():
        if len(group) < 2:
            continue
        for k, index in enumerate(group):
            angle = -math.pi / 2 + 2 * math.pi * k / len(group)
            positions[index][0] += math.cos(angle) * radius * 0.6
            positions[index][1] += math.sin(angle) * radius * 0.6

    minimum = 2 * radius * MARKER_GAP
    for _ in range(iterations):
        moved = False
        for i in range(n):
            for j in range(i + 1, n):
                dx = positions[j][0] - positions[i][0]
                dy = positions[j][1] - positions[i][1]
                dist = math.hypot(dx, dy)
                if dist >= minimum:
                    continue
                if dist < 1e-6:
                    dx, dy, dist = 1.0, 0.0, 1.0
                push = (minimum - dist) / 2
                ux, uy = dx / dist, dy / dist
                positions[i][0] -= ux * push
                positions[i][1] -= uy * push
                positions[j][0] += ux * push
                positions[j][1] += uy * push
                moved = True
        if not moved:
            break
        for i, (ax, ay) in enumerate(points):
            positions[i][0] += (ax - positions[i][0]) * 0.02
            positions[i][1] += (ay - positions[i][1]) * 0.02
            positions[i][0] = min(max(positions[i][0], radius + 1), width - radius - 1)
            positions[i][1] = min(max(positions[i][1], radius + 1), height - radius - 1)
    return [(round(x, 1), round(y, 1)) for x, y in positions]


def _attr(team, name, default=None):
    if isinstance(team, dict):
        return team.get(name, default)
    return getattr(team, name, default)


def build_team_map(teams: Iterable, league: Optional[dict], *,
                   logo_for: Callable[[str], Optional[str]] = lambda _team: None,
                   maps_dir: Path = MAPS_DIR,
                   locations: Optional[list[dict]] = None) -> Optional[dict]:
    """Map data for one league page, or None when the country has no outline yet.

    `teams` are the standings rows in table order (objects or dicts with team, url,
    points). `league` is pelicanconf's league_context for the page.
    """
    if not league:
        return None
    iso2 = COUNTRY_MAPS.get(league.get("name", ""))
    outline = load_outline(iso2, maps_dir) if iso2 else None
    if not outline:
        return None
    locations = load_locations() if locations is None else locations
    prefix = league.get("prefix", "")

    rows, anchors, missing = [], [], []
    for place, team in enumerate(teams, start=1):
        name = str(_attr(team, "team", "") or "")
        if not name:
            continue
        location = find_location(name, prefix, locations)
        if not location:
            missing.append(name)
            continue
        anchors.append(project(location["lat"], location["lon"], outline["projection"]))
        rows.append({
            "team": name,
            "url": _attr(team, "url", "") or "",
            "logo": logo_for(name),
            "town": location["town"],
            "place": place,
            "points": _attr(team, "points", ""),
        })
    if not rows:
        return None

    longest = max(outline["width"], outline["height"])
    radius = round(MARKER_RADIUS * longest / 600.0, 1)
    positions = spread(anchors, radius, outline["width"], outline["height"])
    markers = []
    for row, (ax, ay), (x, y) in zip(rows, anchors, positions):
        markers.append({**row, "ax": round(ax, 1), "ay": round(ay, 1), "x": x, "y": y,
                        "moved": math.hypot(x - ax, y - ay) > 2})
    # Draw the table leader last, so it sits on top where markers touch.
    markers.sort(key=lambda marker: -marker["place"])
    return {
        "width": outline["width"],
        "height": outline["height"],
        "country": outline["country"],
        "regions": [region["path"] for region in outline.get("regions", [])],
        "radius": radius,
        "display_width": round(DISPLAY_SIZE * outline["width"] / longest),
        "markers": markers,
        "missing": missing,
    }
