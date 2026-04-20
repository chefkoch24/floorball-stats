import argparse
from datetime import datetime
from pathlib import Path
import re
from src.player_identity import harmonize_player_display_names

try:
    import psycopg
except ImportError:  # pragma: no cover - optional when DB mode isn't used
    psycopg = None


TOURNAMENT_SEASON_PREFIXES = {"wfc"}


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
    match = re.match(r"^([a-z]{2,3})-(?:\d{2}-\d{2}|\d{4})$", str(season or "").strip().lower())
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


def _load_rows_from_postgres(database_url: str) -> list[dict[str, str]]:
    if psycopg is None:
        raise RuntimeError("psycopg is required for --database-url mode. Install dependencies first.")
    rows: list[dict[str, str]] = []
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        try:
            cur.execute(
                """
                SELECT
                    COALESCE(alias.canonical_uid, ps.player_uid) AS player_uid,
                    ps.source_system,
                    ps.source_player_id,
                    ps.source_person_id,
                    ps.player,
                    ps.title,
                    ps.slug,
                    ps.category,
                    ps.team,
                    ps.league,
                    ps.season,
                    ps.phase,
                    ps.rank,
                    ps.games,
                    ps.goals,
                    ps.assists,
                    ps.points,
                    ps.pim,
                    ps.penalties
                FROM player_stats ps
                LEFT JOIN player_identity_aliases alias
                  ON alias.alias_uid = ps.player_uid
                """
            )
        except Exception:
            cur.execute(
                """
                SELECT
                    player_uid,
                    source_system,
                    source_player_id,
                    source_person_id,
                    player,
                    title,
                    slug,
                    category,
                    team,
                    league,
                    season,
                    phase,
                    rank,
                    games,
                    goals,
                    assists,
                    points,
                    pim,
                    penalties
                FROM player_stats
                """
            )
        columns = [description.name for description in cur.description]
        for record in cur.fetchall():
            row = {columns[idx]: "" if value is None else str(value) for idx, value in enumerate(record)}
            rows.append(_clean_row(row))
    return rows


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


def _is_tournament_season(season: str) -> bool:
    return _season_prefix(season) in TOURNAMENT_SEASON_PREFIXES


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


def _combined_player_rows(rows: list[dict[str, str]], season: str) -> list[dict[str, str]]:
    grouped: dict[str, dict[str, object]] = {}

    for row in rows:
        player_uid = row.get("player_uid", "").strip()
        player_name = row.get("player", "").strip()
        if not player_uid and not player_name:
            continue
        key = player_uid or player_name.lower()
        entry = grouped.setdefault(
            key,
            {
                "player_uid": player_uid,
                "player": player_name,
                "team_values": [],
                "league": row.get("league", "").strip(),
                "season": season,
                "phase": "tournament",
                "games": 0,
                "goals": 0,
                "assists": 0,
                "points": 0,
                "pim": 0,
            },
        )

        if not entry["player_uid"] and player_uid:
            entry["player_uid"] = player_uid
        if not entry["player"] and player_name:
            entry["player"] = player_name
        if not entry["league"] and row.get("league", "").strip():
            entry["league"] = row.get("league", "").strip()

        team_name = row.get("team", "").strip()
        if team_name and team_name not in entry["team_values"]:
            entry["team_values"].append(team_name)

        for stat_key in ("games", "goals", "assists", "points", "pim"):
            try:
                entry[stat_key] += int(float(row.get(stat_key, "0") or 0))
            except (ValueError, TypeError):
                pass

    combined_rows: list[dict[str, str]] = []
    sorted_rows = sorted(
        grouped.values(),
        key=lambda row: (
            -int(row["points"]),
            -int(row["goals"]),
            -int(row["assists"]),
            str(row["player"]).lower(),
        ),
    )
    for idx, row in enumerate(sorted_rows, start=1):
        combined_rows.append(
            {
                "rank": str(idx),
                "player_uid": str(row["player_uid"]),
                "player": str(row["player"]),
                "team": " / ".join(row["team_values"]),
                "league": str(row["league"]),
                "season": str(row["season"]),
                "phase": str(row["phase"]),
                "games": str(row["games"]),
                "goals": str(row["goals"]),
                "assists": str(row["assists"]),
                "points": str(row["points"]),
                "pim": str(row["pim"]),
            }
        )
    return combined_rows


def _write_if_changed(path: Path, content: str) -> bool:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return False
    path.write_text(content, encoding="utf-8")
    return True


def _matches_prefix_scope(filename: str, include_prefixes: set[str]) -> bool:
    stem = Path(filename).stem
    for prefix in include_prefixes:
        if prefix:
            if stem.startswith(f"{prefix}-"):
                return True
        else:
            if re.match(r"^\d{2}-\d{2}(?:-.+)?$", stem):
                return True
    return False


def _prune_stale_markdown(directory: Path, expected_filenames: set[str]) -> int:
    removed = 0
    for candidate in directory.glob("*.md"):
        if candidate.name in expected_filenames:
            continue
        candidate.unlink()
        removed += 1
    return removed


def _prune_stale_markdown_for_prefixes(directory: Path, expected_filenames: set[str], include_prefixes: set[str]) -> int:
    removed = 0
    for candidate in directory.glob("*.md"):
        if candidate.name in expected_filenames:
            continue
        if not _matches_prefix_scope(candidate.name, include_prefixes):
            continue
        candidate.unlink()
        removed += 1
    return removed


def generate_player_stats_index_markdown(
    output_dir: str,
    season_prefixes: set[str] | None = None,
    prune_stale: bool = True,
    database_url: str = "",
) -> tuple[int, int]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    metadata_date = datetime.now().strftime("%Y-%m-%d")

    grouped_rows: dict[tuple[str, str], list[dict[str, str]]] = {}
    include_prefixes = season_prefixes or set()
    if not database_url:
        raise RuntimeError(
            "Missing --database-url (or NEON_DATABASE_URL / DATABASE_URL env var). "
            "CSV fallback is disabled for player stats index generation."
        )
    source_rows = harmonize_player_display_names(_load_rows_from_postgres(database_url))
    if not source_rows:
        return 0, 0
    for row in source_rows:
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
        if _is_tournament_season(season):
            if phase != "regular-season":
                continue
            rows = _combined_player_rows(
                grouped_rows.get((season, "regular-season"), []) + grouped_rows.get((season, "playoffs"), []),
                season=season,
            )
            if not rows:
                continue
            first = rows[0]
            category = f"{season}-players"
            slug = category
            page_phase = "tournament"
        else:
            rows = sorted(
                grouped_rows[(season, phase)],
                key=lambda row: int(float(row.get("rank", "999999"))),
            )
            first = rows[0]
            category = f"{season}-{phase}-players"
            slug = category
            page_phase = phase
        filename = f"{slug}.md"
        expected_files.add(filename)

        lines = [
            f"Date: {metadata_date}",
            f"Title: {_format_title(first.get('league', 'Player'), season, page_phase)}",
            f"Category: {category}",
            f"Slug: {slug}",
            "type: player_stats",
            f"season_phase_key: {season}-{page_phase}",
            f"league: {first.get('league', '')}",
            f"season: {season}",
            f"phase: {page_phase}",
            f"player_count: {len(rows)}",
            f"player_rows_csv: {_rows_to_csv(rows)}",
        ]
        if _write_if_changed(output_path / filename, "\n".join(lines)):
            written += 1

    if prune_stale:
        removed = _prune_stale_markdown(output_path, expected_files)
    elif include_prefixes:
        removed = _prune_stale_markdown_for_prefixes(output_path, expected_files, include_prefixes)
    else:
        removed = 0
    return written, removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate season player-stats index markdown pages from Postgres.")
    parser.add_argument("--database-url", default="")
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
        database_url=args.database_url,
        output_dir=args.output_dir,
        season_prefixes=_normalize_prefix_tokens(args.season_prefixes),
        prune_stale=not args.no_prune,
    )
    print(f"player-stats-index: wrote={written} removed={removed}")


if __name__ == "__main__":
    main()
