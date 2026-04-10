import argparse
import csv
from datetime import datetime
from pathlib import Path
import re


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


def _clean_row(row: dict[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in row.items():
        normalized_key = (key or "").strip().lower()
        if not normalized_key:
            continue
        cleaned[normalized_key] = (value or "").strip()
    return cleaned


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


def _format_title(league: str, season: str, phase: str) -> str:
    parts = season.split("-")
    season_label = season
    if len(parts) >= 3 and parts[-2].isdigit() and parts[-1].isdigit():
        season_label = f"{parts[-2]}/{parts[-1]}"
    phase_label = " ".join(part.capitalize() for part in phase.split("-"))
    return f"{league} Player Stats {season_label} {phase_label}".strip()


def _rows_to_csv(rows: list[dict[str, str]]) -> str:
    serialized: list[str] = []
    for row in rows:
        serialized.append(
            "|".join(
                [
                    row.get("rank", ""),
                    row.get("player_uid", ""),
                    row.get("player", ""),
                    row.get("team", ""),
                    row.get("games", ""),
                    row.get("goals", ""),
                    row.get("assists", ""),
                    row.get("points", ""),
                    row.get("pim", ""),
                ]
            )
        )
    return "||".join(serialized)


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


def generate_player_stats_index_markdown(
    csv_path: str,
    output_dir: str,
    season_prefixes: set[str] | None = None,
    prune_stale: bool = True,
) -> tuple[int, int]:
    source_path = Path(csv_path)
    if not source_path.exists():
        print(f"player-stats-index: csv not found at {source_path}; skipping.")
        return 0, 0

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    metadata_date = datetime.now().strftime("%Y-%m-%d")

    grouped_rows: dict[tuple[str, str], list[dict[str, str]]] = {}
    include_prefixes = season_prefixes or set()
    with source_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            row = _clean_row(raw_row)
            if not row:
                continue
            season = row.get("season", "")
            phase = row.get("phase", "")
            if not season or not phase:
                continue
            if include_prefixes and _season_prefix(season) not in include_prefixes:
                continue
            grouped_rows.setdefault((season, phase), []).append(row)

    written = 0
    expected_files: set[str] = set()

    ordered_keys = sorted(
        grouped_rows.keys(),
        key=lambda item: (_season_sort_key(item[0]), _phase_priority(item[1])),
        reverse=True,
    )
    for season, phase in ordered_keys:
        rows = sorted(
            grouped_rows[(season, phase)],
            key=lambda row: int(float(row.get("rank", "999999"))),
        )
        first = rows[0]
        category = f"{season}-{phase}-players"
        slug = category
        filename = f"{slug}.md"
        expected_files.add(filename)

        lines = [
            f"Date: {metadata_date}",
            f"Title: {_format_title(first.get('league', 'Player'), season, phase)}",
            f"Category: {category}",
            f"Slug: {slug}",
            "type: player_stats",
            f"season_phase_key: {season}-{phase}",
            f"league: {first.get('league', '')}",
            f"season: {season}",
            f"phase: {phase}",
            f"player_count: {len(rows)}",
            f"player_rows_csv: {_rows_to_csv(rows)}",
        ]
        if _write_if_changed(output_path / filename, "\n".join(lines)):
            written += 1

    removed = _prune_stale_markdown(output_path, expected_files) if prune_stale else 0
    return written, removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate season player-stats index markdown pages from CSV.")
    parser.add_argument("--csv-path", default="data/player_stats.csv")
    parser.add_argument("--output-dir", default="content/player-stats")
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
    written, removed = generate_player_stats_index_markdown(
        csv_path=args.csv_path,
        output_dir=args.output_dir,
        season_prefixes=_normalize_prefix_tokens(args.season_prefixes),
        prune_stale=not args.no_prune,
    )
    print(f"player-stats-index: wrote={written} removed={removed}")


if __name__ == "__main__":
    main()
