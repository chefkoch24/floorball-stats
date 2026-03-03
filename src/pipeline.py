import argparse
from pathlib import Path

from src.generate_markdown import generate_markdown_files
from src.run_stats_engine import run_stats_pipeline
from src.scrape import scrape_events


def run_pipeline(
    league_id: int,
    season: str,
    phase: str,
    data_dir: str = "data",
    content_dir: str = "content",
    skip_scrape: bool = False,
) -> dict:
    data_path = Path(data_dir)
    content_path = Path(content_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    (content_path / f"{season}-{phase}" / "games").mkdir(parents=True, exist_ok=True)
    (content_path / f"{season}-{phase}" / "teams").mkdir(parents=True, exist_ok=True)

    raw_csv = data_path / f"data_{season}_{phase.replace('-', '_')}.csv"

    if not skip_scrape:
        scrape_events(
            input_path=f"leagues/{league_id}/schedule.json",
            output_path=str(raw_csv),
        )

    if not raw_csv.exists():
        raise FileNotFoundError(f"Expected input CSV at {raw_csv} but file does not exist.")

    run_stats_pipeline(input_csv_path=str(raw_csv), output_dir=str(data_path))
    games_written, teams_written = generate_markdown_files(
        game_stats_path=str(data_path / "game_stats.json"),
        team_stats_path=str(data_path / "team_stats_enhanced.json"),
        output_games_dir=str(content_path / f"{season}-{phase}" / "games"),
        output_teams_dir=str(content_path / f"{season}-{phase}" / "teams"),
        season=season,
        phase=phase,
    )
    return {
        "raw_csv": str(raw_csv),
        "games_written": games_written,
        "teams_written": teams_written,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league_id", type=int, default=1890)
    parser.add_argument("--season", default="25-26")
    parser.add_argument("--phase", default="regular-season")
    parser.add_argument("--data_dir", default="data")
    parser.add_argument("--content_dir", default="content")
    parser.add_argument("--skip_scrape", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    run_pipeline(
        league_id=args.league_id,
        season=args.season,
        phase=args.phase,
        data_dir=args.data_dir,
        content_dir=args.content_dir,
        skip_scrape=args.skip_scrape,
    )


if __name__ == "__main__":
    main()
