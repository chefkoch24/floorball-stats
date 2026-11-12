"""Kick-off times in the local time of the league's country, with the German equivalent.

The scrapers store ``start_time`` as a plain ``HH:MM`` in the time of the country the game is
played in (src/scrape_*.py). This module knows which zone that is, so the pages can say
"18:30 EET (17:30 CET)" instead of an unlabelled "18:30". The site's home zone is Berlin: a
league that shares Berlin's offset on the game day shows just "18:30".
"""

from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

HOME_ZONE = ZoneInfo("Europe/Berlin")
UTC_ZONE = ZoneInfo("UTC")

# Country part of the league prefix (women's leagues append "w") -> local time zone.
COUNTRY_TIMEZONES = {
    "se": "Europe/Stockholm",
    "fi": "Europe/Helsinki",
    "cz": "Europe/Prague",
    "ch": "Europe/Zurich",
    "sk": "Europe/Bratislava",
    "lv": "Europe/Riga",
    "": "Europe/Berlin",
}

# The IFF feed (src/scrape_wfc.py) stores tournament kick-offs in UTC. Category slug prefix ->
# time zone of the host city; add the next tournament here. An unlisted "wfc-" tournament is shown in UTC.
UTC_TOURNAMENT_ZONES = {"wfc-2024": "Europe/Stockholm"}  # Malmö

_CLOCK = re.compile(r"(\d{2}):(\d{2})(?::\d{2})?")


def timezone_for_prefix(prefix: str) -> ZoneInfo:
    """Zone of the league prefix ("fi-", "sew-", ""). Competitions and unknown prefixes use Berlin."""
    prefix = (prefix or "").rstrip("-")
    country = prefix[:-1] if len(prefix) == 3 and prefix.endswith("w") else prefix
    return ZoneInfo(COUNTRY_TIMEZONES.get(country, "Europe/Berlin"))


def kickoff_parts(day: date | datetime, start_time: object, prefix: str, *, always_label: bool = False) -> dict | None:
    """Local clock time, zone name and German equivalent of a kick-off, or None without a valid time.

    ``zone``/``home``/``home_zone`` are empty when the local time already is German time
    (and ``always_label`` is off); ``home_note`` flags a German time on the previous or next day.
    """
    return _parts(day, start_time, timezone_for_prefix(prefix), None, always_label)


def tournament_kickoff_parts(day: date | datetime, start_time: object, slug: str) -> dict | None:
    """Like :func:`kickoff_parts` for a tournament category slug whose times are stored in UTC.

    Returns None for every other category, so callers can fall back to :func:`kickoff_parts`.
    """
    slug = str(slug or "")
    if not slug.startswith("wfc-"):
        return None
    host = next((ZoneInfo(zone) for key, zone in UTC_TOURNAMENT_ZONES.items() if slug.startswith(key)), UTC_ZONE)
    return _parts(day, start_time, host, UTC_ZONE, True)


def _parts(day, start_time, local_zone: ZoneInfo, stored_zone: ZoneInfo | None, always_label: bool) -> dict | None:
    match = _CLOCK.fullmatch(str(start_time or "").strip())
    if not match or day is None:
        return None
    if isinstance(day, datetime):
        day = day.date()
    try:
        stored = datetime(day.year, day.month, day.day, int(match.group(1)), int(match.group(2)),
                          tzinfo=stored_zone or local_zone)
    except ValueError:
        return None
    local = stored.astimezone(local_zone)
    home = local.astimezone(HOME_ZONE)
    same_clock = local.utcoffset() == home.utcoffset()
    note = ""
    if home.date() != local.date():
        note = "day before" if home.date() < local.date() else "next day"
    return {
        "local": local.strftime("%H:%M"),
        "zone": "" if same_clock and not always_label else local.tzname(),
        "home": "" if same_clock else home.strftime("%H:%M"),
        "home_zone": "" if same_clock else home.tzname(),
        "home_note": note,
    }


def kickoff_label(parts: dict | None) -> str:
    """"18:30", "18:30 CET" or "18:30 EET (17:30 CET)" for :func:`kickoff_parts`."""
    if not parts:
        return ""
    label = parts["local"] + (f" {parts['zone']}" if parts["zone"] else "")
    if parts["home"]:
        note = f", {parts['home_note']}" if parts["home_note"] else ""
        label += f" ({parts['home']} {parts['home_zone']}{note})"
    return label

