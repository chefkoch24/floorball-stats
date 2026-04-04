import json
from pathlib import Path
from typing import Any


def load_league_config(path: str | Path) -> dict[str, Any]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"League config not found: {cfg_path}")
    with cfg_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("League config must be a JSON object")
    return data


def apply_league_config(args: Any, config: dict[str, Any]) -> None:
    if not config:
        return
    args.backend = config.get("backend", args.backend)
    args.league_id = config.get("league_id", args.league_id)
    args.competition_id = config.get("competition_id", args.competition_id)
    args.competition_ids = config.get("competition_ids", getattr(args, "competition_ids", None))
    args.season = config.get("season", args.season)
    args.phase = config.get("phase", args.phase)
    args.playoff_teams_count = config.get("playoff_teams_count", getattr(args, "playoff_teams_count", 8))
    args.data_dir = config.get("data_dir", args.data_dir)
    args.content_dir = config.get("content_dir", args.content_dir)
    args.skip_scrape = bool(config.get("skip_scrape", args.skip_scrape))

    swiss = config.get("swiss", {}) or {}
    args.swiss_game_ids = swiss.get("game_ids", args.swiss_game_ids)
    args.swiss_schedule_url = swiss.get("schedule_urls", args.swiss_schedule_url)
    args.swiss_league = swiss.get("league", args.swiss_league)
    args.swiss_season = swiss.get("season", args.swiss_season)
    args.swiss_game_class = swiss.get("game_class", args.swiss_game_class)
    args.swiss_mode = swiss.get("mode", args.swiss_mode)
    args.swiss_group = swiss.get("group", args.swiss_group)
    args.swiss_start_round = swiss.get("start_round", args.swiss_start_round)

    czech = config.get("czech", {}) or {}
    args.czech_schedule_url = czech.get("schedule_urls", args.czech_schedule_url)
    args.czech_season_start_year = czech.get("season_start_year", args.czech_season_start_year)

    finland = config.get("finland", {}) or {}
    args.finland_schedule_url = finland.get("schedule_urls", args.finland_schedule_url)
    args.finland_playoff_start_date = finland.get("playoff_start_date", args.finland_playoff_start_date)

    slovakia = config.get("slovakia", {}) or {}
    args.slovakia_schedule_url = slovakia.get("schedule_urls", args.slovakia_schedule_url)
    args.slovakia_regular_season_end = slovakia.get("regular_season_end_date", args.slovakia_regular_season_end)
    args.slovakia_regular_season_games_per_team = slovakia.get(
        "regular_season_games_per_team", args.slovakia_regular_season_games_per_team
    )

    latvia = config.get("latvia", {}) or {}
    args.latvia_calendar_url = latvia.get("calendar_urls", args.latvia_calendar_url)
    args.latvia_season_start_year = latvia.get("season_start_year", args.latvia_season_start_year)
