import argparse
from pathlib import Path

from src.generate_markdown import generate_markdown_files
from src.league_config import apply_league_config, load_league_config
from src.run_stats_engine import run_stats_pipeline
from src.scrape import scrape_events
from src.scrape_sweden import scrape_competition_events, scrape_competitions_events
from src.scrape_finland import scrape_matches as scrape_finland_matches
from src.scrape_czech import scrape_competition as scrape_czech_competition
from src.scrape_latvia import scrape_competition as scrape_latvia_competition
from src.scrape_slovakia import scrape_competition as scrape_slovakia_competition
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
    competition_ids: list[int] | None = None,
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
    finland_playoff_start_date: str | None = None,
    slovakia_schedule_urls: list[str] | None = None,
    slovakia_regular_season_end: str | None = None,
    slovakia_regular_season_games_per_team: int | None = None,
    latvia_calendar_urls: list[str] | None = None,
    latvia_season_start_year: int | None = None,
    playoff_teams_count: int = 8,
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
            sweden_competition_ids = competition_ids or ([competition_id] if competition_id is not None else [])
            if not sweden_competition_ids:
                raise ValueError("competition_id or competition_ids is required when backend=sweden")
            if len(sweden_competition_ids) == 1:
                scrape_competition_events(
                    competition_id=sweden_competition_ids[0],
                    output_path=str(raw_csv),
                    include_unplayed=True,
                )
            else:
                scrape_competitions_events(
                    competition_ids=sweden_competition_ids,
                    output_path=str(raw_csv),
                    include_unplayed=True,
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
            # For playoffs, traverse available rounds to avoid only scraping the
            # currently listed stage.
            if swiss_league and swiss_season and swiss_game_class and (swiss_group or phase == "playoffs"):
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
                include_unplayed=True,
                phase=phase,
            )
        elif backend == "finland":
            if not finland_schedule_urls:
                raise ValueError("finland_schedule_urls are required when backend=finland")
            scrape_finland_matches(
                schedule_urls=finland_schedule_urls,
                output_path=str(raw_csv),
                include_unplayed=True,
                phase=phase,
                playoff_start_date=finland_playoff_start_date,
            )
        elif backend == "slovakia":
            if not slovakia_schedule_urls:
                raise ValueError("slovakia_schedule_urls are required when backend=slovakia")
            scrape_slovakia_competition(
                schedule_urls=slovakia_schedule_urls,
                output_path=str(raw_csv),
                phase=phase,
                regular_season_end_date=slovakia_regular_season_end,
                regular_season_games_per_team=slovakia_regular_season_games_per_team,
            )
        elif backend == "latvia":
            if not latvia_calendar_urls:
                raise ValueError("latvia_calendar_urls are required when backend=latvia")
            if not latvia_season_start_year:
                raise ValueError("latvia_season_start_year is required when backend=latvia")
            scrape_latvia_competition(
                calendar_urls=latvia_calendar_urls,
                output_path=str(raw_csv),
                season_start_year=latvia_season_start_year,
                phase=phase,
            )
        else:
            scrape_events(
                input_path=f"leagues/{league_id}/schedule.json",
                output_path=str(raw_csv),
            )

    if not raw_csv.exists():
        raise FileNotFoundError(f"Expected input CSV at {raw_csv} but file does not exist.")

    pregame_history_csv_paths: list[str] = []
    if phase == "playoffs":
        regular_phase = "regular-season"
        regular_csv = data_path / f"data_{season}_{regular_phase.replace('-', '_')}.csv"
        if regular_csv.exists():
            pregame_history_csv_paths.append(str(regular_csv))

    run_stats_pipeline(
        input_csv_path=str(raw_csv),
        output_dir=str(data_path),
        season=season,
        phase=phase,
        pregame_history_csv_paths=pregame_history_csv_paths,
        playoff_cut=playoff_teams_count,
    )
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
        choices=["saisonmanager", "sweden", "switzerland", "czech", "finland", "slovakia", "latvia"],
    )
    parser.add_argument("--league_id", type=int, default=1890)
    parser.add_argument("--competition_id", type=int, default=None)
    parser.add_argument("--competition_ids", type=str, default=None)
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
    parser.add_argument("--finland_playoff_start_date", type=str, default=None)
    parser.add_argument("--slovakia_schedule_url", action="append", default=None)
    parser.add_argument("--slovakia_regular_season_end", type=str, default=None)
    parser.add_argument("--slovakia_regular_season_games_per_team", type=int, default=None)
    parser.add_argument("--latvia_calendar_url", action="append", default=None)
    parser.add_argument("--latvia_season_start_year", type=int, default=None)
    parser.add_argument("--playoff_teams_count", type=int, default=8)
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
    sweden_competition_ids = None
    if args.competition_ids:
        sweden_competition_ids = []
        if isinstance(args.competition_ids, list):
            sweden_competition_ids = [int(v) for v in args.competition_ids]
        else:
            for part in str(args.competition_ids).split(","):
                part = part.strip()
                if part.isdigit():
                    sweden_competition_ids.append(int(part))
    run_pipeline(
        league_id=args.league_id,
        season=args.season,
        phase=args.phase,
        backend=args.backend,
        competition_id=args.competition_id,
        competition_ids=sweden_competition_ids,
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
        finland_playoff_start_date=args.finland_playoff_start_date,
        slovakia_schedule_urls=args.slovakia_schedule_url,
        slovakia_regular_season_end=args.slovakia_regular_season_end,
        slovakia_regular_season_games_per_team=args.slovakia_regular_season_games_per_team,
        latvia_calendar_urls=args.latvia_calendar_url,
        latvia_season_start_year=args.latvia_season_start_year,
        playoff_teams_count=args.playoff_teams_count,
        data_dir=args.data_dir,
        content_dir=args.content_dir,
        skip_scrape=args.skip_scrape,
    )


if __name__ == "__main__":
    main()
