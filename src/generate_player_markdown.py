import argparse
from datetime import datetime
from pathlib import Path
import re
from src.utils import generate_player_uid, normalize_slug_fragment
from src.player_identity import harmonize_player_display_names, is_abbreviated_player_name

try:
    import psycopg
except ImportError:  # pragma: no cover - optional when DB mode isn't used
    psycopg = None

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


def _is_tournament_season(season: str) -> bool:
    return _season_prefix(season) in TOURNAMENT_SEASON_PREFIXES


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


def _dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    best_rows: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
    ordered_keys: list[tuple[str, str, str, str, str]] = []
    for row in rows:
        marker = (
            row.get("player_uid", "").strip().lower(),
            row.get("season", "").strip().lower(),
            row.get("phase", "").strip().lower(),
            row.get("team", "").strip().lower(),
            row.get("league", "").strip().lower(),
        )
        candidate_score = (
            1 if row.get("source_person_id", "").strip() else 0,
            1 if row.get("source_player_id", "").strip() else 0,
            len(row.get("history_rows_csv", "").strip()),
            len(row.get("slug", "").strip()),
        )
        existing = best_rows.get(marker)
        if existing is None:
            ordered_keys.append(marker)
            best_rows[marker] = row
            continue
        existing_score = (
            1 if existing.get("source_person_id", "").strip() else 0,
            1 if existing.get("source_player_id", "").strip() else 0,
            len(existing.get("history_rows_csv", "").strip()),
            len(existing.get("slug", "").strip()),
        )
        if candidate_score > existing_score:
            best_rows[marker] = row
    return [best_rows[key] for key in ordered_keys]


def _dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    best_rows: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
    ordered_keys: list[tuple[str, str, str, str, str]] = []
    for row in rows:
        marker = (
            row.get("player_uid", "").strip().lower(),
            row.get("season", "").strip().lower(),
            row.get("phase", "").strip().lower(),
            row.get("team", "").strip().lower(),
            row.get("league", "").strip().lower(),
        )
        candidate_score = (
            1 if row.get("source_person_id", "").strip() else 0,
            1 if row.get("source_player_id", "").strip() else 0,
            len(row.get("history_rows_csv", "").strip()),
            len(row.get("slug", "").strip()),
        )
        existing = best_rows.get(marker)
        if existing is None:
            ordered_keys.append(marker)
            best_rows[marker] = row
            continue
        existing_score = (
            1 if existing.get("source_person_id", "").strip() else 0,
            1 if existing.get("source_player_id", "").strip() else 0,
            len(existing.get("history_rows_csv", "").strip()),
            len(existing.get("slug", "").strip()),
        )
        if candidate_score > existing_score:
            best_rows[marker] = row
    return [best_rows[key] for key in ordered_keys]


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


def _load_alias_pairs_from_postgres(database_url: str) -> list[tuple[str, str]]:
    if psycopg is None:
        return []
    pairs: list[tuple[str, str]] = []
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        try:
            cur.execute(
                """
                SELECT alias_uid, canonical_uid
                FROM player_identity_aliases
                """
            )
        except Exception:
            return []
        for alias_uid, canonical_uid in cur.fetchall():
            alias = str(alias_uid or "").strip().lower()
            canonical = str(canonical_uid or "").strip().lower()
            if not alias or not canonical or alias == canonical:
                continue
            pairs.append((alias, canonical))
    return pairs


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
    current_is_tournament = _is_tournament_season(current_season)

    current_rows = [row for row in rows if row.get("season", "").strip() == current_season]
    regular_rows = [] if current_is_tournament else [row for row in current_rows if row.get("phase", "").strip() == "regular-season"]
    playoff_rows = [] if current_is_tournament else [row for row in current_rows if row.get("phase", "").strip() == "playoffs"]
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
    if is_abbreviated_player_name(title) and not is_abbreviated_player_name(player):
        title = player
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
        f"current_season_is_tournament: {'yes' if current_is_tournament else 'no'}",
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
    history_source_rows = sorted_rows
    if any(_is_tournament_season(row.get("season", "")) for row in sorted_rows):
        grouped_history: dict[tuple[str, str, str], list[dict[str, str]]] = {}
        ordered_history_keys: list[tuple[str, str, str]] = []
        for row in sorted_rows:
            season = row.get("season", "")
            if _is_tournament_season(season):
                key = (
                    season,
                    row.get("league", ""),
                    row.get("team", ""),
                )
            else:
                key = (
                    season,
                    row.get("phase", ""),
                    row.get("team", ""),
                )
            if key not in grouped_history:
                ordered_history_keys.append(key)
                grouped_history[key] = []
            grouped_history[key].append(row)

        history_source_rows = []
        for key in ordered_history_keys:
            group = grouped_history[key]
            first_group_row = group[0]
            if _is_tournament_season(first_group_row.get("season", "")):
                history_source_rows.append(
                    {
                        "season": first_group_row.get("season", ""),
                        "phase": "tournament",
                        "league": first_group_row.get("league", ""),
                        "team": first_group_row.get("team", ""),
                        "games": str(_sum(group, "games")),
                        "goals": str(_sum(group, "goals")),
                        "assists": str(_sum(group, "assists")),
                        "points": str(_sum(group, "points")),
                        "pim": str(_sum(group, "pim")),
                    }
                )
            else:
                history_source_rows.append(first_group_row)

    for row in history_source_rows:
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
    output_dir: str,
    default_category: str = "players",
    season_prefixes: set[str] | None = None,
    prune_stale: bool = True,
    database_url: str = "",
    merge_csv_path: str = "",
) -> tuple[int, int]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    metadata_date = datetime.now().strftime("%Y-%m-%d")

    written = 0
    expected_files: set[str] = set()
    grouped_rows: dict[str, list[dict[str, str]]] = {}
    include_prefixes = season_prefixes or set()

    if not database_url:
        raise RuntimeError(
            "Missing --database-url (or NEON_DATABASE_URL / DATABASE_URL env var). "
            "CSV fallback is disabled for player markdown generation."
        )
    source_rows = harmonize_player_display_names(_load_rows_from_postgres(database_url))
    if not source_rows:
        return 0, 0

    target_uids: set[str] = set()
    for row in source_rows:
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
        target_uids.add(uid)
        grouped_rows.setdefault(uid, []).append(row)

    if database_url and include_prefixes:
        for row in source_rows:
            if not row:
                continue
            player = row.get("player") or row.get("name") or row.get("full_name")
            if not player:
                continue
            uid = _canonical_player_uid(row, player)
            if uid not in target_uids:
                continue
            grouped_rows.setdefault(uid, []).append(row)

    for uid in list(grouped_rows.keys()):
        grouped_rows[uid] = _dedupe_rows(grouped_rows[uid])

    alias_pairs = _load_alias_pairs_from_postgres(database_url)
    aliases_by_canonical: dict[str, set[str]] = {}
    for alias_uid, canonical_uid in alias_pairs:
        if canonical_uid not in grouped_rows:
            continue
        aliases_by_canonical.setdefault(canonical_uid, set()).add(alias_uid)

    for uid, rows in grouped_rows.items():
        markdown, filename = _rows_to_markdown(rows, default_category=default_category, metadata_date=metadata_date)
        if filename != f"{uid}.md":
            filename = f"{uid}.md"
            target_path = output_path / filename
        target_path = output_path / filename
        expected_files.add(filename)
        if _write_if_changed(target_path, markdown):
            written += 1

        for alias_uid in sorted(aliases_by_canonical.get(uid, set())):
            alias_filename = f"{alias_uid}.md"
            alias_markdown = markdown.replace(f"Slug: {uid}", f"Slug: {alias_uid}", 1)
            # Keep canonical identity in metadata while exposing alias URL.
            alias_markdown = alias_markdown.replace(f"player_uid: {uid}", f"player_uid: {uid}", 1)
            alias_path = output_path / alias_filename
            expected_files.add(alias_filename)
            if _write_if_changed(alias_path, alias_markdown):
                written += 1

    removed = _prune_stale_markdown(output_path, expected_files) if prune_stale else 0
    return written, removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Pelican player markdown pages from Postgres.")
    parser.add_argument("--database-url", default="")
    parser.add_argument("--output-dir", default="content/players")
    parser.add_argument("--default-category", default="players")
    parser.add_argument(
        "--merge-csv-path",
        default="",
        help="Optional secondary CSV to merge additional season rows for players found in the primary CSV.",
    )
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
        database_url=args.database_url,
        output_dir=args.output_dir,
        default_category=args.default_category,
        season_prefixes=_normalize_prefix_tokens(args.season_prefixes),
        prune_stale=not args.no_prune,
        merge_csv_path=args.merge_csv_path,
    )
    print(f"player-markdown: wrote={written} removed={removed}")


if __name__ == "__main__":
    main()
