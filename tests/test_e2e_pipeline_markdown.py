from pathlib import Path

import pandas as pd

from src.generate_markdown import generate_markdown_files
from src.pipeline import run_pipeline
from src.run_stats_engine import run_stats_pipeline


def _sample_events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "game_id": 1,
                "game_date": "2025-09-13",
                "event_type": "goal",
                "event_team": "Team A",
                "home_team_name": "Team A",
                "away_team_name": "Team B",
                "home_goals": 1,
                "guest_goals": 0,
                "period": 1,
                "sortkey": "1-03:00",
                "goal_type": "normal",
                "penalty_type": None,
            },
            {
                "game_id": 1,
                "game_date": "2025-09-13",
                "event_type": "goal",
                "event_team": "Team B",
                "home_team_name": "Team A",
                "away_team_name": "Team B",
                "home_goals": 1,
                "guest_goals": 1,
                "period": 2,
                "sortkey": "2-10:00",
                "goal_type": "normal",
                "penalty_type": None,
            },
            {
                "game_id": 1,
                "game_date": "2025-09-13",
                "event_type": "goal",
                "event_team": "Team A",
                "home_team_name": "Team A",
                "away_team_name": "Team B",
                "home_goals": 2,
                "guest_goals": 1,
                "period": 3,
                "sortkey": "3-19:00",
                "goal_type": "normal",
                "penalty_type": None,
            },
        ]
    )


def test_run_stats_and_generate_markdown_end_to_end(tmp_path: Path):
    data_dir = tmp_path / "data"
    content_dir = tmp_path / "content"
    data_dir.mkdir(parents=True, exist_ok=True)

    events_csv = data_dir / "events.csv"
    _sample_events().to_csv(events_csv, index=False)

    run_stats_pipeline(input_csv_path=str(events_csv), output_dir=str(data_dir))
    games_written, teams_written, league_written = generate_markdown_files(
        game_stats_path=str(data_dir / "game_stats.json"),
        team_stats_path=str(data_dir / "team_stats_enhanced.json"),
        league_stats_path=str(data_dir / "league_averages.json"),
        output_games_dir=str(content_dir / "25-26-regular-season" / "games"),
        output_teams_dir=str(content_dir / "25-26-regular-season" / "teams"),
        output_liga_dir=str(content_dir / "25-26-regular-season" / "liga"),
        season="25-26",
        phase="regular-season",
    )

    assert games_written == 1
    assert teams_written == 2
    assert league_written == 1

    game_files = list((content_dir / "25-26-regular-season" / "games").glob("*.md"))
    team_files = list((content_dir / "25-26-regular-season" / "teams").glob("*.md"))
    liga_files = list((content_dir / "25-26-regular-season" / "liga").glob("*.md"))
    assert len(game_files) == 1
    assert len(team_files) == 2
    assert len(liga_files) == 1

    game_content = game_files[0].read_text(encoding="utf-8")
    assert "type: game" in game_content
    assert "Date: 2025-09-13" in game_content
    assert "home_team: Team A" in game_content
    assert "away_team: Team B" in game_content
    assert "Category: 25-26-regular-season, game" in game_content

    team_content = team_files[0].read_text(encoding="utf-8")
    assert "type: team" in team_content
    assert "Category: 25-26-regular-season, teams" in team_content


def test_pipeline_writes_markdown_into_content_tree(tmp_path: Path):
    season = "25-26"
    phase = "regular-season"
    data_dir = tmp_path / "data"
    content_dir = tmp_path / "content"
    data_dir.mkdir(parents=True, exist_ok=True)

    raw_csv = data_dir / f"data_{season}_{phase.replace('-', '_')}.csv"
    _sample_events().to_csv(raw_csv, index=False)

    result = run_pipeline(
        league_id=1890,
        season=season,
        phase=phase,
        data_dir=str(data_dir),
        content_dir=str(content_dir),
        skip_scrape=True,
    )

    assert result["games_written"] == 1
    assert result["teams_written"] == 2
    assert (content_dir / f"{season}-{phase}" / "games").exists()
    assert (content_dir / f"{season}-{phase}" / "teams").exists()
