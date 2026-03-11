import argparse
from pathlib import Path

from src.generate_markdown import generate_markdown_files
from src.league_config import apply_league_config, load_league_config
from src.run_stats_engine import run_stats_pipeline
from src.scrape import scrape_events
from src.scrape_sweden import scrape_competition_events
from src.scrape_finland import scrape_matches as scrape_finland_matches
from src.scrape_czech import scrape_competition as scrape_czech_competition
from src.scrape_switzerland import (
    fetch_game_ids_by_rounds,
    fetch_game_ids_from_renderengine,
    fetch_game_ids_from_url,
    scrape_games,
)


def run_pipeline(
    league_id: int,
    season: str,
    phase: str,
    backend: str = "saisonmanager",
    competition_id: int | None = None,
    swiss_game_ids: list[int] | None = None,
    swiss_schedule_urls: list[str] | None = None,
    swiss_league: int | None = None,
    swiss_season: int | None = None,
    swiss_game_class: int | None = None,
    swiss_mode: str = "list",
    swiss_group: str | None = None,
    swiss_start_round: int | None = None,
    czech_schedule_urls: list[str] | None = None,
    czech_season_start_year: int | None = None,
    finland_schedule_urls: list[str] | None = None,
    data_dir: str = "data",
    content_dir: str = "content",
    skip_scrape: bool = False,
) -> dict:
    data_path = Path(data_dir)
    content_path = Path(content_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    (content_path / f"{season}-{phase}" / "games").mkdir(parents=True, exist_ok=True)
    (content_path / f"{season}-{phase}" / "teams").mkdir(parents=True, exist_ok=True)
    (content_path / f"{season}-{phase}" / "liga").mkdir(parents=True, exist_ok=True)

    raw_csv = data_path / f"data_{season}_{phase.replace('-', '_')}.csv"

    if not skip_scrape:
        if backend == "sweden":
            if competition_id is None:
                raise ValueError("competition_id is required when backend=sweden")
            scrape_competition_events(
                competition_id=competition_id,
                output_path=str(raw_csv),
            )
        elif backend == "switzerland":
            game_ids = set(swiss_game_ids or [])
            for url in swiss_schedule_urls or []:
                game_ids.update(fetch_game_ids_from_url(url))
            if swiss_league and swiss_season and swiss_game_class:
                game_ids.update(
                    fetch_game_ids_from_renderengine(
                        league=swiss_league,
                        season=swiss_season,
                        game_class=swiss_game_class,
                        mode=swiss_mode,
                    )
                )
            if swiss_league and swiss_season and swiss_game_class and swiss_group:
                game_ids.update(
                    fetch_game_ids_by_rounds(
                        league=swiss_league,
                        season=swiss_season,
                        game_class=swiss_game_class,
                        group=swiss_group,
                        start_round=swiss_start_round,
                    )
                )
            if not game_ids:
                raise ValueError(
                    "swiss_game_ids, swiss_schedule_urls, or swiss_league/season/game_class are required when backend=switzerland"
                )
            scrape_games(game_ids=sorted(game_ids), output_path=str(raw_csv), phase_filter=phase)
        elif backend == "czech":
            if not czech_schedule_urls:
                raise ValueError("czech_schedule_urls are required when backend=czech")
            if not czech_season_start_year:
                raise ValueError("czech_season_start_year is required when backend=czech")
            scrape_czech_competition(
                schedule_urls=czech_schedule_urls,
                output_path=str(raw_csv),
                season_start_year=czech_season_start_year,
            )
        elif backend == "finland":
            if not finland_schedule_urls:
                raise ValueError("finland_schedule_urls are required when backend=finland")
            scrape_finland_matches(
                schedule_urls=finland_schedule_urls,
                output_path=str(raw_csv),
            )
        else:
            scrape_events(
                input_path=f"leagues/{league_id}/schedule.json",
                output_path=str(raw_csv),
            )

    if not raw_csv.exists():
        raise FileNotFoundError(f"Expected input CSV at {raw_csv} but file does not exist.")

    run_stats_pipeline(input_csv_path=str(raw_csv), output_dir=str(data_path))
    games_written, teams_written, league_written = generate_markdown_files(
        game_stats_path=str(data_path / "game_stats.json"),
        team_stats_path=str(data_path / "team_stats_enhanced.json"),
        league_stats_path=str(data_path / "league_averages.json"),
        playoff_averages_path=str(data_path / "playoff_averages.json"),
        playdown_averages_path=str(data_path / "playdown_averages.json"),
        top4_averages_path=str(data_path / "top4_averages.json"),
        output_games_dir=str(content_path / f"{season}-{phase}" / "games"),
        output_teams_dir=str(content_path / f"{season}-{phase}" / "teams"),
        output_liga_dir=str(content_path / f"{season}-{phase}" / "liga"),
        season=season,
        phase=phase,
    )
    return {
        "raw_csv": str(raw_csv),
        "games_written": games_written,
        "teams_written": teams_written,
        "league_written": league_written,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backend",
        default="saisonmanager",
        choices=["saisonmanager", "sweden", "switzerland", "czech", "finland"],
    )
    parser.add_argument("--league_id", type=int, default=1890)
    parser.add_argument("--competition_id", type=int, default=None)
    parser.add_argument("--league_config", type=str, default=None)
    parser.add_argument("--swiss_game_ids", type=str, default=None)
    parser.add_argument("--swiss_schedule_url", action="append", default=None)
    parser.add_argument("--swiss_league", type=int, default=None)
    parser.add_argument("--swiss_season", type=int, default=None)
    parser.add_argument("--swiss_game_class", type=int, default=None)
    parser.add_argument("--swiss_mode", type=str, default="list")
    parser.add_argument("--swiss_group", type=str, default=None)
    parser.add_argument("--swiss_start_round", type=int, default=None)
    parser.add_argument("--czech_schedule_url", action="append", default=None)
    parser.add_argument("--czech_season_start_year", type=int, default=None)
    parser.add_argument("--finland_schedule_url", action="append", default=None)
    parser.add_argument("--season", default="25-26")
    parser.add_argument("--phase", default="regular-season")
    parser.add_argument("--data_dir", default="data")
    parser.add_argument("--content_dir", default="content")
    parser.add_argument("--skip_scrape", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.league_config:
        cfg = load_league_config(args.league_config)
        apply_league_config(args, cfg)
    swiss_game_ids = None
    if args.swiss_game_ids:
        swiss_game_ids = []
        if isinstance(args.swiss_game_ids, list):
            swiss_game_ids = [int(v) for v in args.swiss_game_ids]
        else:
            for part in str(args.swiss_game_ids).split(","):
                part = part.strip()
                if part.isdigit():
                    swiss_game_ids.append(int(part))
    run_pipeline(
        league_id=args.league_id,
        season=args.season,
        phase=args.phase,
        backend=args.backend,
        competition_id=args.competition_id,
        swiss_game_ids=swiss_game_ids,
        swiss_schedule_urls=args.swiss_schedule_url,
        swiss_league=args.swiss_league,
        swiss_season=args.swiss_season,
        swiss_game_class=args.swiss_game_class,
        swiss_mode=args.swiss_mode,
        swiss_group=args.swiss_group,
        swiss_start_round=args.swiss_start_round,
        czech_schedule_urls=args.czech_schedule_url,
        czech_season_start_year=args.czech_season_start_year,
        finland_schedule_urls=args.finland_schedule_url,
        data_dir=args.data_dir,
        content_dir=args.content_dir,
        skip_scrape=args.skip_scrape,
    )


if __name__ == "__main__":
    main()
