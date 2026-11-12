"""Global search index (themes/my-theme/static/search/search-index.json).

Three kinds of rows, each with a ``weight`` (higher = shown first among equally good matches):

- ``player``: every player page. Subtitle ``Team · League · Season``; the weight puts players of the
  newest season first, then by points.
- ``team``: one row per club and league, not per season and phase. It links to the newest season's
  page (regular season before playoffs before cup).
- ``league``: league, playoff, cup and player-table pages of every season.

Version 2 added ``weight``, the ``league`` type and one team row per club.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Callable

SEASON = re.compile(r"(?<!\d)(\d{2})-(\d{2})(?!\d)")
PHASE_ORDER = {"regular-season": 3, "playoffs": 2, "cup": 1}


def _parse_metadata(path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if not line.strip():
                break
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key_clean = key.strip().lower()
            if not key_clean:
                continue
            metadata[key_clean] = value.strip()
    return metadata


def _season_start(slug: str) -> int:
    """First year of the season in a slug ("se-26-27-playoffs" -> 26); 0 when there is none."""
    match = SEASON.search(slug)
    return int(match.group(1)) if match else 0


def _season_label(slug: str) -> str:
    match = SEASON.search(slug)
    return f"20{match.group(1)}/{match.group(2)}" if match else ""


def _phase(slug: str) -> str:
    for phase in PHASE_ORDER:
        if slug.endswith(phase) or slug.endswith(f"{phase}-players"):
            return phase
    return ""


def _int(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _default_labels() -> tuple[Callable[[str], str], Callable[[str], str]]:
    """(label of a category page, name of the league a category belongs to) from pelicanconf."""
    try:
        import pelicanconf  # type: ignore

        filters = pelicanconf.JINJA_FILTERS
        seo_label = filters["category_seo_label"]
        league_context = filters["league_context"]

        german = next((league["title"] for league in pelicanconf.LEAGUES if league["prefix"] == ""), "")

        def league_title(slug: str) -> str:
            title = (league_context(slug) or {}).get("title")
            if not title and SEASON.match(slug):
                # Seasons before the configured ones: slugs without a country prefix are Germany's men.
                title = german
            return str(title or "")

        return seo_label, league_title
    except Exception as error:  # the index must still build without the site config
        print(f"search-index: warning, league labels fall back to slugs ({error})", file=sys.stderr)
        return (lambda slug: slug), (lambda slug: "")


def _player_entry(path: Path) -> dict | None:
    meta = _parse_metadata(path)
    slug = meta.get("slug", "")
    name = meta.get("player", "") or meta.get("title", "")
    if not slug or not name:
        return None
    season = meta.get("current_season", "")
    subtitle = " · ".join(part for part in (meta.get("team", ""), meta.get("league", ""), _season_label(season)) if part)
    # Newest season first, then by points; points stay below 1000 for one season.
    weight = _season_start(season) * 1000 + min(_int(meta.get("current_points", "")), 999)
    return {"type": "player", "name": name, "subtitle": subtitle, "url": f"/{slug}.html", "weight": weight}


def _team_entries(content_path: Path, league_title: Callable[[str], str]) -> list[dict]:
    """One row per (club, league): the newest season, regular season before playoffs before cup."""
    best: dict[tuple[str, str], tuple[tuple[int, int], dict]] = {}
    for path in sorted(content_path.glob("**/teams/*.md")):
        meta = _parse_metadata(path)
        slug = meta.get("slug", "")
        name = meta.get("team", "") or meta.get("title", "")
        category = meta.get("category", "").split(",")[0].strip()
        if not slug or not name or not category:
            continue
        league = league_title(category)
        rank = (_season_start(category), PHASE_ORDER.get(_phase(category), 0))
        key = (name, league or category)
        if key in best and best[key][0] >= rank:
            continue
        subtitle = " · ".join(part for part in (league, _season_label(category)) if part)
        best[key] = (rank, {"type": "team", "name": name, "subtitle": subtitle, "url": f"/{slug}.html",
                            "weight": rank[0] * 10 + rank[1]})
    return [entry for _, entry in best.values()]


def _league_entries(content_path: Path, seo_label: Callable[[str], str], league_title: Callable[[str], str]) -> list[dict]:
    entries = []
    for directory in sorted(content_path.iterdir()):
        if not directory.is_dir() or not ((directory / "teams").is_dir() or (directory / "games").is_dir()):
            continue
        slug = directory.name
        entries.append(_league_entry(slug, seo_label, league_title))
    for path in sorted((content_path / "player-stats").glob("*.md")):
        meta = _parse_metadata(path)
        slug = meta.get("slug", "")
        if slug and meta.get("type") == "player_stats":
            entries.append(_league_entry(slug, seo_label, league_title, players=True))
    return entries


PHASE_NAMES = {"regular-season": "Regular season", "playoffs": "Playoffs", "cup": "Cup"}


def _league_entry(slug: str, seo_label: Callable[[str], str], league_title: Callable[[str], str], players: bool = False) -> dict:
    # "Sweden · SSL" plus "2026/27 · Playoffs"; competitions without a league title (WFC) use the page label.
    name = league_title(slug) or re.sub(r" (Regular Season|Playoffs|Players)$", "", seo_label(slug))
    phase = PHASE_NAMES.get(_phase(slug), "")
    if players:
        phase = "Player stats" + (f" · {phase}" if phase and _phase(slug) != "regular-season" else "")
    subtitle = " · ".join(part for part in (_season_label(slug), phase) if part)
    # Current season first, regular season before playoffs before cup, player tables last.
    weight = _season_start(slug) * 10 + PHASE_ORDER.get(_phase(slug), 0) - (5 if players else 0)
    return {"type": "league", "name": name, "subtitle": subtitle, "url": f"/category/{slug}.html", "weight": weight}


def build_search_index(content_dir: str, output_path: str,
                       seo_label: Callable[[str], str] | None = None,
                       league_title: Callable[[str], str] | None = None) -> int:
    content_path = Path(content_dir)
    if seo_label is None or league_title is None:
        default_label, default_title = _default_labels()
        seo_label = seo_label or default_label
        league_title = league_title or default_title

    players = [entry for entry in (_player_entry(path) for path in sorted((content_path / "players").glob("*.md"))) if entry]
    teams = _team_entries(content_path, league_title)
    leagues = _league_entries(content_path, seo_label, league_title)

    items: list[dict] = []
    for group in (players, teams, leagues):
        items.extend(sorted(group, key=lambda entry: (-entry["weight"], entry["name"])))

    payload = {"version": 2, "item_count": len(items), "items": items}
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(items)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build global player/team/league search index.")
    parser.add_argument("--content-dir", default="content")
    parser.add_argument("--output-path", default="themes/my-theme/static/search/search-index.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = build_search_index(content_dir=args.content_dir, output_path=args.output_path)
    print(f"search-index: wrote {count} records to {args.output_path}")


if __name__ == "__main__":
    main()
