"""Build the outline of one country for the team map on league pages.

Reads Natural Earth GeoJSON (public domain, https://www.naturalearthdata.com), projects the
country and its first-level regions into a small SVG coordinate system and writes
config/maps/<iso2>.json. Run once per country; the output is committed, so the site build
needs neither the source files nor network access.

    python scripts/build_country_outline.py --iso3 DEU --iso2 de \
        --countries ne_50m_admin_0_countries.geojson \
        --regions ne_10m_admin_1_states_provinces.geojson
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

WIDTH = 600.0
PADDING = 12.0
TOLERANCE = 0.5  # SVG units; points closer to the simplified line are dropped


def _rings(geometry):
    if geometry["type"] == "Polygon":
        yield from geometry["coordinates"]
    elif geometry["type"] == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            yield from polygon


def _simplify(points, tolerance):
    """Douglas-Peucker on a list of (x, y)."""
    if len(points) < 3:
        return points
    (x1, y1), (x2, y2) = points[0], points[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = math.hypot(dx, dy)
    best, index = 0.0, 0
    for i in range(1, len(points) - 1):
        px, py = points[i]
        if norm == 0:
            dist = math.hypot(px - x1, py - y1)
        else:
            dist = abs(dy * px - dx * py + x2 * y1 - y2 * x1) / norm
        if dist > best:
            best, index = dist, i
    if best <= tolerance:
        return [points[0], points[-1]]
    return _simplify(points[: index + 1], tolerance)[:-1] + _simplify(points[index:], tolerance)


def _path(rings, project, min_points=4):
    parts = []
    for ring in rings:
        points = _simplify([project(lon, lat) for lon, lat in ring], TOLERANCE)
        if len(points) < min_points:
            continue
        parts.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in points) + "Z")
    return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--iso3", required=True, help="ISO 3166-1 alpha-3 code, e.g. DEU")
    parser.add_argument("--iso2", required=True, help="output name, e.g. de")
    parser.add_argument("--countries", required=True, type=Path)
    parser.add_argument("--regions", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parents[1] / "config" / "maps")
    args = parser.parse_args()

    countries = json.loads(args.countries.read_text(encoding="utf-8"))["features"]
    country = next(f for f in countries if f["properties"].get("ADM0_A3") == args.iso3)
    country_rings = list(_rings(country["geometry"]))

    # Bounding box of the mainland and islands, equirectangular projection scaled by
    # cos(mid latitude): accurate enough at the size of one country.
    lons = [lon for ring in country_rings for lon, _ in ring]
    lats = [lat for ring in country_rings for _, lat in ring]
    west, east, south, north = min(lons), max(lons), min(lats), max(lats)
    kx = math.cos(math.radians((south + north) / 2))
    scale = (WIDTH - 2 * PADDING) / ((east - west) * kx)
    height = (north - south) * scale + 2 * PADDING

    def project(lon, lat):
        return (PADDING + (lon - west) * kx * scale, PADDING + (north - lat) * scale)

    regions = []
    if args.regions:
        for feature in json.loads(args.regions.read_text(encoding="utf-8"))["features"]:
            if feature["properties"].get("adm0_a3") != args.iso3:
                continue
            path = _path(_rings(feature["geometry"]), project)
            if path:
                regions.append({"name": feature["properties"].get("name"), "path": path})
        regions.sort(key=lambda region: region["name"] or "")

    out = {
        "source": "Natural Earth (public domain), country 1:50m, regions 1:10m",
        "iso3": args.iso3,
        "width": round(WIDTH, 1),
        "height": round(height, 1),
        "projection": {
            "type": "equirectangular",
            "west": west,
            "north": north,
            "kx": kx,
            "scale": scale,
            "padding": PADDING,
        },
        "country": _path(country_rings, project),
        "regions": regions,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    target = args.out_dir / f"{args.iso2}.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{target}: {len(out['country'])} chars country, {len(regions)} regions, "
          f"{sum(len(r['path']) for r in regions)} chars regions, {WIDTH:.0f}x{height:.0f}")


if __name__ == "__main__":
    main()
