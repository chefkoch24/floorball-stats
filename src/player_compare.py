"""Data behind the player comparison page (``/compare-players.html``).

The page does not carry the 4,600 players. The build writes one slim search index
(``compare-players/index.json``: one short row per player) and one small file per
player (``compare-players/<player uid>.json``) that the page loads when a player is
chosen. This module turns the front matter of a player page (plus the clutch and
goal-share facts ``plugins/insights.py`` attaches to it) into those two shapes; the
plugin ``plugins/player_compare.py`` collects the pages and writes the files, the
comparison itself runs in ``themes/my-theme/static/js/player-compare.js``.
"""

from __future__ import annotations

import re
from typing import Mapping

# Column order of the rows in index.json; the page reads the same list from the file.
INDEX_FIELDS = ("uid", "name", "team", "league", "season", "games")

COUNT_KEYS = ("games", "goals", "assists", "points", "pim")
CLUTCH_KEYS = ("gwg", "clutch_points", "game_changing")

_SEASON_PAIR = re.compile(r"(\d{2})-(\d{2})$")
_SEASON_YEAR = re.compile(r"(\d{4})$")


def season_label(season: str) -> str:
    """'fi-26-27' and '26-27' -> '2026/27'; a tournament season such as 'wfc-2024' -> '2024'."""
    text = str(season or "").strip()
    pair = _SEASON_PAIR.search(text)
    if pair:
        return f"20{pair.group(1)}/{pair.group(2)}"
    year = _SEASON_YEAR.search(text)
    return year.group(1) if year else text


def _count(value: object) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _text(value: object) -> str:
    text = str(value if value is not None else "").strip()
    return "" if text in {"None", "nan", "n.a."} else text


def _places(value: object) -> str:
    """'A / B / A' -> 'A / B': the pages join the clubs and leagues of a season, which repeats a club that has several rows."""
    parts = [part.strip() for part in _text(value).split(" / ")]
    return " / ".join(dict.fromkeys(part for part in parts if part))


def _page_id(meta: Mapping[str, object]) -> str:
    """The id of the player page: its slug, which is also the page's file name and is unique (``player_uid`` can repeat)."""
    return _text(meta.get("slug")) or _text(meta.get("player_uid"))


def _counts(meta: Mapping[str, object], scope: str) -> dict[str, int]:
    return {key: _count(meta.get(f"{scope}_{key}")) for key in COUNT_KEYS}


def index_row(meta: Mapping[str, object]) -> list:
    """One search-index row, in INDEX_FIELDS order, from a player page's front matter."""
    games = _count(meta.get("career_games")) or _count(meta.get("current_games"))
    return [
        _page_id(meta),
        _text(meta.get("player")) or _text(meta.get("title")),
        _places(meta.get("team")),
        _places(meta.get("league")),
        _text(meta.get("current_season")),
        games,
    ]


def _clutch_line(line: Mapping[str, object] | None) -> dict[str, int] | None:
    if not line:
        return None
    return {key: _count(line.get(key)) for key in CLUTCH_KEYS}


def player_payload(
    meta: Mapping[str, object],
    clutch: Mapping[str, object] | None = None,
    trends: Mapping[str, object] | None = None,
    team_url: str = "",
) -> dict:
    """What the page needs for one player: latest season and career totals, clutch and goal share.

    ``clutch`` is ``article.clutch`` (``season_line`` and ``all`` from player_insights),
    ``trends`` is ``article.player_trends`` (points, team goals and share of the latest phase).
    """
    uid = _page_id(meta)
    season = _text(meta.get("current_season"))
    current = _counts(meta, "current")
    career = _counts(meta, "career")
    # Pages of players with a single season may lack the career_ keys.
    if not career["games"] and current["games"]:
        career = dict(current)

    share = None
    if trends and trends.get("share") is not None:
        share = {
            "share": _count(trends.get("share")),
            "points": _count(trends.get("points")),
            "team_goals": _count(trends.get("team_goals")),
        }

    return {
        "uid": uid,
        "name": _text(meta.get("player")) or _text(meta.get("title")),
        "url": f"{uid}.html",
        "team": _places(meta.get("team")),
        "team_url": team_url,
        "league": _places(meta.get("league")),
        "season": season,
        "season_label": season_label(season),
        "seasons": _count(meta.get("season_count")),
        "current": current,
        "career": career,
        "clutch": {
            "current": _clutch_line((clutch or {}).get("season_line")),
            "all": _clutch_line((clutch or {}).get("all")),
        },
        "share": share,
    }


def index_payload(rows: list[list]) -> dict:
    """Search index: players with most career games first, so suggestions lead with regulars."""
    ordered = sorted(rows, key=lambda row: (-row[5], row[1], row[0]))
    return {"fields": list(INDEX_FIELDS), "players": ordered}
