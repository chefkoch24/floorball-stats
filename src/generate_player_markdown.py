import argparse
import csv
from datetime import datetime
from pathlib import Path
import re

from src.utils import generate_player_uid, normalize_slug_fragment


CONTROL_FIELDS = {
    "player",
    "title",
    "slug",
    "category",
    "team",
    "league",
    "date",
    "type",
    "content",
    "name",
    "full_name",
    "player_uid",
    "source_system",
    "source_player_id",
    "source_person_id",
    "history_rows_csv",
}


def _normalize_prefix_tokens(raw: str | None) -> set[str]:
    if not raw:
        return set()
    aliases = {
        "de": "",
        "ger": "",
        "germany": "",
    }
    normalized: set[str] = set()
    for token in str(raw).split(","):
        cleaned = token.strip().lower()
        if not cleaned:
            continue
        normalized.add(aliases.get(cleaned, cleaned))
    return normalized


def _season_prefix(season: str) -> str:
    match = re.match(r"^([a-z]{2})-\d{2}-\d{2}$", str(season or "").strip().lower())
    if match:
        return match.group(1)
    return ""


def _write_if_changed(path: Path, content: str) -> bool:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return False
    path.write_text(content, encoding="utf-8")
    return True


def _prune_stale_markdown(directory: Path, expected_filenames: set[str]) -> int:
    removed = 0
    for candidate in directory.glob("*.md"):
        if candidate.name in expected_filenames:
            continue
        candidate.unlink()
        removed += 1
    return removed


def _clean_row(row: dict[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in row.items():
        normalized_key = (key or "").strip().lower()
        if not normalized_key:
            continue
        cleaned[normalized_key] = (value or "").strip()
    return cleaned


def _to_int(value: str | int | float | None) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return 0


def _season_sort_key(season: str) -> tuple[int, int]:
    matches = re.findall(r"(\d{2})", str(season))
    if len(matches) >= 2:
        return int(matches[-2]), int(matches[-1])
    return (0, 0)


def _phase_priority(phase: str) -> int:
    normalized = (phase or "").strip().lower()
    if normalized == "playoffs":
        return 2
    if normalized == "regular-season":
        return 1
    return 0


def _canonical_player_uid(row: dict[str, str], player: str) -> str:
    existing = row.get("player_uid", "").strip()
    if existing:
        return existing.lower()
    source_system = row.get("source_system", "").strip().lower()
    source_person_id = row.get("source_person_id", "").strip()
    if source_person_id and source_person_id != "0":
        return generate_player_uid(source_system or "unknown", "person", source_person_id)
    source_player_id = row.get("source_player_id", "").strip()
    if source_player_id and source_player_id != "0":
        return generate_player_uid(source_system or "unknown", "player", source_player_id)
    normalized_player = normalize_slug_fragment(player)
    if normalized_player:
        return normalized_player
    return generate_player_uid("player", player)


def _rows_to_markdown(rows: list[dict[str, str]], default_category: str, metadata_date: str) -> tuple[str, str]:
    if not rows:
        raise ValueError("No rows provided for player page generation.")

    first = rows[0]
    player = first.get("player") or first.get("name") or first.get("full_name")
    if not player:
        raise ValueError("CSV row is missing a player/name/full_name field.")

    uid = _canonical_player_uid(first, player)
    sorted_rows = sorted(
        rows,
        key=lambda item: (
            _season_sort_key(item.get("season", "")),
            _phase_priority(item.get("phase", "")),
        ),
        reverse=True,
    )
    current_row = sorted_rows[0]

    seasons_desc = sorted({row.get("season", "").strip() for row in rows if row.get("season", "").strip()}, key=_season_sort_key, reverse=True)
    current_season = seasons_desc[0] if seasons_desc else current_row.get("season", "").strip()
    previous_season = seasons_desc[1] if len(seasons_desc) > 1 else ""

    current_rows = [row for row in rows if row.get("season", "").strip() == current_season]
    regular_rows = [row for row in current_rows if row.get("phase", "").strip() == "regular-season"]
    playoff_rows = [row for row in current_rows if row.get("phase", "").strip() == "playoffs"]
    previous_rows = [row for row in rows if row.get("season", "").strip() == previous_season] if previous_season else []

    def _join_unique(rows_subset: list[dict[str, str]], key: str) -> str:
        values: list[str] = []
        for row in rows_subset:
            value = row.get(key, "").strip()
            if not value or value in values:
                continue
            values.append(value)
        return " / ".join(values)

    current_team = _join_unique(current_rows, "team") or current_row.get("team", "")
    current_league = _join_unique(current_rows, "league") or current_row.get("league", "")

    def _sum(rows_subset: list[dict[str, str]], key: str) -> int:
        return sum(_to_int(row.get(key)) for row in rows_subset)

    title = current_row.get("title") or player
    slug = uid
    category = default_category
    content = current_row.get("content") or ""
    date = current_row.get("date") or metadata_date

    lines = [
        f"Date: {date}",
        f"Title: {title}",
        f"Category: {category}",
        f"Slug: {slug}",
        "type: player",
        f"player: {player}",
        f"player_uid: {uid}",
        f"team: {current_team}",
        f"league: {current_league}",
        f"season_count: {len(seasons_desc)}",
        f"current_season: {current_season}",
        f"previous_season: {previous_season or 'n.a.'}",
        f"current_games: {_sum(current_rows, 'games')}",
        f"current_goals: {_sum(current_rows, 'goals')}",
        f"current_assists: {_sum(current_rows, 'assists')}",
        f"current_points: {_sum(current_rows, 'points')}",
        f"current_pim: {_sum(current_rows, 'pim')}",
        f"regular_games: {_sum(regular_rows, 'games')}",
        f"regular_goals: {_sum(regular_rows, 'goals')}",
        f"regular_assists: {_sum(regular_rows, 'assists')}",
        f"regular_points: {_sum(regular_rows, 'points')}",
        f"regular_pim: {_sum(regular_rows, 'pim')}",
        f"playoff_games: {_sum(playoff_rows, 'games')}",
        f"playoff_goals: {_sum(playoff_rows, 'goals')}",
        f"playoff_assists: {_sum(playoff_rows, 'assists')}",
        f"playoff_points: {_sum(playoff_rows, 'points')}",
        f"playoff_pim: {_sum(playoff_rows, 'pim')}",
        f"previous_games: {_sum(previous_rows, 'games')}",
        f"previous_goals: {_sum(previous_rows, 'goals')}",
        f"previous_assists: {_sum(previous_rows, 'assists')}",
        f"previous_points: {_sum(previous_rows, 'points')}",
        f"previous_pim: {_sum(previous_rows, 'pim')}",
        f"career_games: {_sum(rows, 'games')}",
        f"career_goals: {_sum(rows, 'goals')}",
        f"career_assists: {_sum(rows, 'assists')}",
        f"career_points: {_sum(rows, 'points')}",
        f"career_pim: {_sum(rows, 'pim')}",
    ]

    history_rows = []
    for row in sorted_rows:
        history_rows.append(
            "|".join(
                [
                    row.get("season", ""),
                    row.get("phase", ""),
                    row.get("league", ""),
                    row.get("team", ""),
                    str(_to_int(row.get("games"))),
                    str(_to_int(row.get("goals"))),
                    str(_to_int(row.get("assists"))),
                    str(_to_int(row.get("points"))),
                    str(_to_int(row.get("pim"))),
                ]
            )
        )
    lines.append(f"history_rows_csv: {'||'.join(history_rows)}")

    for key in sorted(current_row):
        if key in CONTROL_FIELDS:
            continue
        value = current_row[key]
        lines.append(f"{key}: {value}")

    if content:
        lines.append("")
        lines.append(content)

    return "\n".join(lines), f"{slug}.md"


def generate_player_markdown(
    csv_path: str,
    output_dir: str,
    default_category: str = "players",
    season_prefixes: set[str] | None = None,
    prune_stale: bool = True,
) -> tuple[int, int]:
    source_path = Path(csv_path)
    if not source_path.exists():
        print(f"player-markdown: csv not found at {source_path}; skipping.")
        return 0, 0

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    metadata_date = datetime.now().strftime("%Y-%m-%d")

    written = 0
    expected_files: set[str] = set()
    grouped_rows: dict[str, list[dict[str, str]]] = {}
    include_prefixes = season_prefixes or set()

    with source_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            row = _clean_row(raw_row)
            if not row:
                continue
            if include_prefixes:
                season = row.get("season", "")
                if _season_prefix(season) not in include_prefixes:
                    continue
            player = row.get("player") or row.get("name") or row.get("full_name")
            if not player:
                continue
            uid = _canonical_player_uid(row, player)
            grouped_rows.setdefault(uid, []).append(row)

    for uid, rows in grouped_rows.items():
        markdown, filename = _rows_to_markdown(rows, default_category=default_category, metadata_date=metadata_date)
        if filename != f"{uid}.md":
            filename = f"{uid}.md"
            target_path = output_path / filename
        target_path = output_path / filename
        expected_files.add(filename)
        if _write_if_changed(target_path, markdown):
            written += 1

    removed = _prune_stale_markdown(output_path, expected_files) if prune_stale else 0
    return written, removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Pelican player markdown pages from CSV.")
    parser.add_argument("--csv-path", default="data/player_stats.csv")
    parser.add_argument("--output-dir", default="content/players")
    parser.add_argument("--default-category", default="players")
    parser.add_argument(
        "--season-prefixes",
        default="",
        help="Optional comma-separated season prefixes to include (e.g. sk,fi,se,cz,ch,lv,de).",
    )
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="Do not delete existing markdown files that are not part of this generation run.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    written, removed = generate_player_markdown(
        csv_path=args.csv_path,
        output_dir=args.output_dir,
        default_category=args.default_category,
        season_prefixes=_normalize_prefix_tokens(args.season_prefixes),
        prune_stale=not args.no_prune,
    )
    print(f"player-markdown: wrote={written} removed={removed}")


if __name__ == "__main__":
    main()
