import argparse
import json
from pathlib import Path

from src.utils import dict_to_markdown_game_stats, dict_to_markdown_team_stats


def _slugify(value: str) -> str:
    value = value.replace(" ", "_").replace("/", "-").lower()
    value = value.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return value


def generate_markdown_files(
    game_stats_path: str,
    team_stats_path: str,
    output_games_dir: str,
    output_teams_dir: str,
    season: str,
    phase: str,
) -> tuple[int, int]:
    games_out = Path(output_games_dir)
    teams_out = Path(output_teams_dir)
    games_out.mkdir(parents=True, exist_ok=True)
    teams_out.mkdir(parents=True, exist_ok=True)

    with open(game_stats_path, "r", encoding="utf-8") as f:
        game_stats = json.load(f)

    games_written = 0
    for gs in game_stats:
        title = _slugify(f"{gs['game_id']}_{gs['home_team']}_vs_{gs['away_team']}")
        md = dict_to_markdown_game_stats(gs, title, season, phase)
        with open(games_out / f"{title}.md", "w", encoding="utf-8") as f:
            f.write(md)
        games_written += 1

    with open(team_stats_path, "r", encoding="utf-8") as f:
        team_stats = json.load(f)

    teams_written = 0
    for team, stats in team_stats.items():
        title = _slugify(f"{team}-{season}-{phase}".replace(" ", "-"))
        md = dict_to_markdown_team_stats(stats, team, season, phase)
        with open(teams_out / f"{title}.md", "w", encoding="utf-8") as f:
            f.write(md)
        teams_written += 1

    return games_written, teams_written


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game_stats_path", default="data/game_stats.json")
    parser.add_argument("--team_stats_path", default="data/team_stats_enhanced.json")
    parser.add_argument("--output_games_dir", default="content/25-26-regular-season/games")
    parser.add_argument("--output_teams_dir", default="content/25-26-regular-season/teams")
    parser.add_argument("--season", default="25-26")
    parser.add_argument("--phase", default="regular-season")
    return parser.parse_args()


def main():
    args = parse_args()
    generate_markdown_files(
        game_stats_path=args.game_stats_path,
        team_stats_path=args.team_stats_path,
        output_games_dir=args.output_games_dir,
        output_teams_dir=args.output_teams_dir,
        season=args.season,
        phase=args.phase,
    )


if __name__ == "__main__":
    main()
