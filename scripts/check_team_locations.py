"""Check the town coordinates in config/team_locations.json against OpenStreetMap Nominatim.

Run by hand (not in the build), e.g. after adding promoted teams:

    .venv/bin/python scripts/check_team_locations.py

One request per town, at most one per second (Nominatim usage policy), cached in
--cache so a re-run only asks for new towns. Prints every town whose stored point
is more than --max-km from Nominatim's, or that Nominatim cannot find.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCATIONS_PATH = ROOT / "config" / "team_locations.json"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "floorball-stats-location-check/1.0"

# League prefix (without the women's "w") -> ISO country code; "" is the German men's league.
PREFIX_COUNTRY = {"": "de", "de": "de", "se": "se", "fi": "fi", "cz": "cz", "ch": "ch", "sk": "sk", "lv": "lv"}
# Swiss canton suffixes in town names ("Rüti ZH") are not part of the place name.
CANTONS = {"ZH": "Zürich", "BE": "Bern"}
# Checked by hand: Nominatim's first hit is a different place, or a district is meant.
KNOWN_OK = {
    "Blau-Weiß 96 Schenefeld": "Schenefeld near Hamburg (Pinneberg), OSM finds the one in Steinburg",
    "FBK Nižná": "Nižná in Orava, OSM finds the one near Piešťany",
    "Mullsjö AIS": "town centre, OSM returns the municipality centroid",
    "FAT PIPE FLORBAL CHODOV": "Prague district Chodov",
    "FbŠ Bohemians": "Prague district Vršovice",
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = phi2 - phi1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def country_of(record: dict) -> str | None:
    for prefix in record.get("league_prefixes") or []:
        key = prefix.rstrip("-")
        key = key[:-1] if key.endswith("w") and len(key) == 3 else key
        if key in PREFIX_COUNTRY:
            return PREFIX_COUNTRY[key]
    return None


def query_for(town: str) -> str:
    head, _, suffix = town.rpartition(" ")
    return f"{head}, {CANTONS[suffix]}" if head and suffix in CANTONS else town


def lookup(town: str, country: str) -> dict | None:
    params = urllib.parse.urlencode({"q": query_for(town), "countrycodes": country, "format": "jsonv2", "limit": 1})
    request = urllib.request.Request(f"{NOMINATIM}?{params}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        results = json.load(response)
    if not results:
        return None
    hit = results[0]
    return {"lat": float(hit["lat"]), "lon": float(hit["lon"]), "name": hit.get("display_name", "")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--max-km", type=float, default=5.0)
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache" / "nominatim_towns.json")
    args = parser.parse_args()

    locations = json.loads(LOCATIONS_PATH.read_text(encoding="utf-8"))["locations"]
    cache = json.loads(args.cache.read_text(encoding="utf-8")) if args.cache.exists() else {}

    towns: dict[tuple[str, str], list[dict]] = {}
    for record in locations:
        country = country_of(record)
        if country:
            towns.setdefault((record["town"], country), []).append(record)

    problems = 0
    for (town, country), records in sorted(towns.items()):
        key = f"{country}|{town}"
        if key not in cache:
            cache[key] = lookup(town, country)
            time.sleep(1.1)
        hit = cache[key]
        teams = ", ".join(sorted({r["team"] for r in records}))
        if hit is None:
            problems += 1
            print(f"NOT FOUND  {country} {town}  ({teams})")
            continue
        for record in records:
            km = haversine_km(record["lat"], record["lon"], hit["lat"], hit["lon"])
            if km > args.max_km and record["team"] not in KNOWN_OK:
                problems += 1
                print(f"{km:7.1f} km  {country} {town}: stored {record['lat']}, {record['lon']} "
                      f"/ OSM {hit['lat']:.4f}, {hit['lon']:.4f}  ({record['team']})  [{hit['name']}]")

    args.cache.parent.mkdir(parents=True, exist_ok=True)
    args.cache.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(towns)} towns checked, {problems} problems (> {args.max_km:g} km or not found)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
