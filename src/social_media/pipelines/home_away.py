from pathlib import Path

from src.social_media.render_home_away import load_table, render_home_away_post


def run_home_away_export(
    *,
    output_path: str,
    league: str,
    season_label: str,
    table_path: str | None = None,
    team_stats_path: str | None = None,
    season: str | None = None,
    phase: str = "regular-season",
    rows_limit: int | None = None,
) -> Path:
    table = load_table(
        table_path=table_path,
        team_stats_path=team_stats_path,
        season=season or season_label,
        phase=phase,
    )
    return render_home_away_post(
        table,
        output_path,
        league=league,
        season_label=season_label,
        rows_limit=rows_limit,
    )
