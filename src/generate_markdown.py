import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from src.utils import dict_to_markdown_game_stats, dict_to_markdown_league_stats, dict_to_markdown_team_stats, normalize_slug_fragment


def _write_if_changed(path: Path, content: str) -> bool:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return False
    path.write_text(content, encoding="utf-8")
    return True


def _extract_slug(content: str) -> Optional[str]:
    for line in content.splitlines():
        if line.startswith("Slug:"):
            value = line.split(":", 1)[1].strip()
            return value or None
    return None


def _remove_slug_aliases(directory: Path, canonical_path: Path, slug: Optional[str]) -> int:
    if not slug:
        return 0
    removed = 0
    for candidate in directory.glob("*.md"):
        if candidate == canonical_path:
            continue
        try:
            candidate_content = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        if _extract_slug(candidate_content) != slug:
            continue
        candidate.unlink()
        removed += 1
    return removed


def _remove_game_id_aliases(directory: Path, canonical_path: Path, game_id: object) -> int:
    game_id_text = str(game_id or "").strip()
    if not game_id_text:
        return 0
    prefix = normalize_slug_fragment(game_id_text)
    if not prefix:
        return 0
    removed = 0
    for candidate in directory.glob(f"{prefix}*.md"):
        if candidate == canonical_path:
            continue
        candidate.unlink()
        removed += 1
    return removed


def _prune_stale_markdown(directory: Path, expected_filenames: set[str]) -> int:
    removed = 0
    for candidate in directory.glob("*.md"):
        if candidate.name in expected_filenames:
            continue
        candidate.unlink()
        removed += 1
    return removed


def _resolve_metadata_date(game_stats: list[dict]) -> str:
    valid_dates = []
    for game in game_stats:
        value = game.get("date")
        if not value:
            continue
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            continue
        valid_dates.append(value)
    if valid_dates:
        return max(valid_dates)
    return datetime.now().strftime("%Y-%m-%d")


def generate_markdown_files(
    game_stats_path: str,
    team_stats_path: str,
    league_stats_path: str,
    output_games_dir: str,
    output_teams_dir: str,
    output_liga_dir: str,
    season: str,
    phase: str,
    playoff_averages_path: Optional[str] = None,
    playdown_averages_path: Optional[str] = None,
    top4_averages_path: Optional[str] = None,
) -> Tuple[int, int, int]:
    games_out = Path(output_games_dir)
    teams_out = Path(output_teams_dir)
    liga_out = Path(output_liga_dir)
    games_out.mkdir(parents=True, exist_ok=True)
    teams_out.mkdir(parents=True, exist_ok=True)
    liga_out.mkdir(parents=True, exist_ok=True)

    with open(game_stats_path, "r", encoding="utf-8") as f:
        game_stats = json.load(f)
    metadata_date = _resolve_metadata_date(game_stats)

    games_written = 0
    expected_game_files: set[str] = set()
    for gs in game_stats:
        title = normalize_slug_fragment(f"{gs['game_id']} {gs['home_team']} vs {gs['away_team']}")
        md = dict_to_markdown_game_stats(gs, title, season, phase, metadata_date=metadata_date)
        target_path = games_out / f"{title}.md"
        expected_game_files.add(target_path.name)
        _remove_game_id_aliases(games_out, target_path, gs.get("game_id"))
        _remove_slug_aliases(games_out, target_path, _extract_slug(md))
        if _write_if_changed(target_path, md):
            games_written += 1
    _prune_stale_markdown(games_out, expected_game_files)

    with open(team_stats_path, "r", encoding="utf-8") as f:
        team_stats = json.load(f)

    teams_written = 0
    expected_team_files: set[str] = set()
    for team, stats in team_stats.items():
        title = normalize_slug_fragment(f"{team}-{season}-{phase}")
        md = dict_to_markdown_team_stats(stats, team, season, phase, metadata_date=metadata_date)
        target_path = teams_out / f"{title}.md"
        expected_team_files.add(target_path.name)
        _remove_slug_aliases(teams_out, target_path, _extract_slug(md))
        if _write_if_changed(target_path, md):
            teams_written += 1
    _prune_stale_markdown(teams_out, expected_team_files)

    with open(league_stats_path, "r", encoding="utf-8") as f:
        league_stats = json.load(f)

    league_written = 0
    expected_liga_files: set[str] = set()
    league_title = "League Average"
    league_md = dict_to_markdown_league_stats(league_stats, league_title, season, phase, metadata_date=metadata_date)
    league_slug = normalize_slug_fragment(f"{league_title}-{season}-{phase}")
    league_target_path = liga_out / f"{league_slug}.md"
    expected_liga_files.add(league_target_path.name)
    _remove_slug_aliases(liga_out, league_target_path, _extract_slug(league_md))
    if _write_if_changed(league_target_path, league_md):
        league_written += 1

    def _write_extra(path: str | None, title: str) -> None:
        nonlocal league_written
        if not path:
            return
        extra_path = Path(path)
        if not extra_path.exists():
            return
        with extra_path.open("r", encoding="utf-8") as f:
            extra_stats = json.load(f)
        extra_md = dict_to_markdown_league_stats(extra_stats, title, season, phase, metadata_date=metadata_date)
        extra_slug = normalize_slug_fragment(f"{title}-{season}-{phase}")
        target_path = liga_out / f"{extra_slug}.md"
        expected_liga_files.add(target_path.name)
        _remove_slug_aliases(liga_out, target_path, _extract_slug(extra_md))
        if _write_if_changed(target_path, extra_md):
            league_written += 1

    _write_extra(playoff_averages_path, "Playoffs")
    _write_extra(top4_averages_path, "Top 4 Teams")
    _prune_stale_markdown(liga_out, expected_liga_files)

    return games_written, teams_written, league_written


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game_stats_path", default="data/game_stats.json")
    parser.add_argument("--team_stats_path", default="data/team_stats_enhanced.json")
    parser.add_argument("--league_stats_path", default="data/league_averages.json")
    parser.add_argument("--output_games_dir", default="content/25-26-regular-season/games")
    parser.add_argument("--output_teams_dir", default="content/25-26-regular-season/teams")
    parser.add_argument("--output_liga_dir", default="content/25-26-regular-season/liga")
    parser.add_argument("--season", default="25-26")
    parser.add_argument("--phase", default="regular-season")
    return parser.parse_args()


def main():
    args = parse_args()
    generate_markdown_files(
        game_stats_path=args.game_stats_path,
        team_stats_path=args.team_stats_path,
        league_stats_path=args.league_stats_path,
        output_games_dir=args.output_games_dir,
        output_teams_dir=args.output_teams_dir,
        output_liga_dir=args.output_liga_dir,
        season=args.season,
        phase=args.phase,
    )


if __name__ == "__main__":
    main()
