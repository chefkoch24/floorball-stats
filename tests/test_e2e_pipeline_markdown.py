from pathlib import Path
import time
import base64
import json

import pandas as pd

from src.generate_markdown import generate_markdown_files
from src.pipeline import run_pipeline
from src.run_stats_engine import run_stats_pipeline
from src.build_sqlite import sync_pipeline_outputs


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
                "attendance": 321,
                "scorer_name": "Alice Forward",
                "assist_name": None,
                "penalty_player_name": None,
            },
            {
                "game_id": 1,
                "game_date": "2025-09-13",
                "event_type": "penalty",
                "event_team": "Team B",
                "home_team_name": "Team A",
                "away_team_name": "Team B",
                "home_goals": 1,
                "guest_goals": 0,
                "period": 1,
                "sortkey": "1-12:00",
                "goal_type": None,
                "penalty_type": "penalty_2",
                "attendance": 321,
                "scorer_name": None,
                "assist_name": None,
                "penalty_player_name": "Pat Defender",
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
                "attendance": 321,
                "scorer_name": "Bob Sniper",
                "assist_name": "Chris Setup",
                "penalty_player_name": None,
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
                "attendance": 321,
                "scorer_name": "Dana Clutch",
                "assist_name": None,
                "penalty_player_name": None,
            },
        ]
    )


def _sample_events_with_upcoming() -> pd.DataFrame:
    rows = _sample_events().to_dict(orient="records")
    rows.append(
        {
            "game_id": 2,
            "game_date": "2025-09-20",
            "game_start_time": "18:30",
            "event_type": "scheduled",
            "event_team": None,
            "home_team_name": "Team A",
            "away_team_name": "Team C",
            "home_goals": None,
            "guest_goals": None,
            "period": 0,
            "sortkey": "0-00:00",
            "goal_type": None,
            "penalty_type": None,
            "attendance": None,
            "result_string": None,
            "game_status": "Scheduled",
            "ingame_status": None,
            "scorer_name": None,
            "assist_name": None,
            "penalty_player_name": None,
        }
    )
    return pd.DataFrame(rows)


def test_run_stats_and_generate_markdown_end_to_end(tmp_path: Path):
    data_dir = tmp_path / "data"
    content_dir = tmp_path / "content"
    data_dir.mkdir(parents=True, exist_ok=True)

    events_csv = data_dir / "events.csv"
    _sample_events().to_csv(events_csv, index=False)

    run_stats_pipeline(input_csv_path=str(events_csv), output_dir=str(data_dir))
    assert (data_dir / "home_away_split_table.json").exists()
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
    assert "attendance: 321" in game_content
    assert "timeline_minutes_csv:" in game_content
    assert "timeline_diffs_csv:" in game_content
    assert "game_events_b64:" in game_content

    game_stats = json.loads((data_dir / "game_stats.json").read_text(encoding="utf-8"))
    event_payload = base64.b64decode(game_stats[0]["game_events_b64"]).decode("utf-8")
    decoded_events = json.loads(event_payload)
    assert game_stats[0]["attendance"] == 321
    assert decoded_events[0]["event_kind"] == "goal"
    assert decoded_events[0]["title"] == "Alice Forward"
    assert any(event["event_kind"] == "penalty" and event["title"] == "2 min penalty" and event["assist"] == "Pat Defender" for event in decoded_events)
    assert any(event["event_kind"] == "break" and event["title"] == "End 1st period" for event in decoded_events)
    assert any(event["event_kind"] == "goal" and event["assist"] == "Chris Setup" for event in decoded_events)

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
    assert (data_dir / "home_away_split_table.json").exists()
    assert (content_dir / f"{season}-{phase}" / "games").exists()
    assert (content_dir / f"{season}-{phase}" / "teams").exists()


def test_generate_markdown_does_not_touch_unchanged_files(tmp_path: Path):
    data_dir = tmp_path / "data"
    content_dir = tmp_path / "content"
    data_dir.mkdir(parents=True, exist_ok=True)

    events_csv = data_dir / "events.csv"
    _sample_events().to_csv(events_csv, index=False)

    run_stats_pipeline(input_csv_path=str(events_csv), output_dir=str(data_dir))
    initial_counts = generate_markdown_files(
        game_stats_path=str(data_dir / "game_stats.json"),
        team_stats_path=str(data_dir / "team_stats_enhanced.json"),
        league_stats_path=str(data_dir / "league_averages.json"),
        output_games_dir=str(content_dir / "25-26-regular-season" / "games"),
        output_teams_dir=str(content_dir / "25-26-regular-season" / "teams"),
        output_liga_dir=str(content_dir / "25-26-regular-season" / "liga"),
        season="25-26",
        phase="regular-season",
    )
    assert initial_counts == (1, 2, 1)

    game_file = next((content_dir / "25-26-regular-season" / "games").glob("*.md"))
    team_file = next((content_dir / "25-26-regular-season" / "teams").glob("*.md"))
    liga_file = next((content_dir / "25-26-regular-season" / "liga").glob("*.md"))

    before = (
        game_file.stat().st_mtime_ns,
        team_file.stat().st_mtime_ns,
        liga_file.stat().st_mtime_ns,
    )
    time.sleep(1.1)

    second_counts = generate_markdown_files(
        game_stats_path=str(data_dir / "game_stats.json"),
        team_stats_path=str(data_dir / "team_stats_enhanced.json"),
        league_stats_path=str(data_dir / "league_averages.json"),
        output_games_dir=str(content_dir / "25-26-regular-season" / "games"),
        output_teams_dir=str(content_dir / "25-26-regular-season" / "teams"),
        output_liga_dir=str(content_dir / "25-26-regular-season" / "liga"),
        season="25-26",
        phase="regular-season",
    )
    assert second_counts == (0, 0, 0)

    after = (
        game_file.stat().st_mtime_ns,
        team_file.stat().st_mtime_ns,
        liga_file.stat().st_mtime_ns,
    )
    assert after == before


def test_generate_markdown_removes_slug_alias_files(tmp_path: Path):
    data_dir = tmp_path / "data"
    content_dir = tmp_path / "content"
    data_dir.mkdir(parents=True, exist_ok=True)

    events_csv = data_dir / "events.csv"
    _sample_events().to_csv(events_csv, index=False)
    run_stats_pipeline(input_csv_path=str(events_csv), output_dir=str(data_dir))

    liga_dir = content_dir / "25-26-regular-season" / "liga"
    liga_dir.mkdir(parents=True, exist_ok=True)
    stale_alias = liga_dir / "top_4_teams-25-26-regular-season.md"
    stale_alias.write_text(
        "\n".join(
            [
                "Date: 2025-09-13",
                "Title: Top 4 Teams",
                "Category: 25-26-regular-season, liga",
                "Slug: top-4-teams-25-26-regular-season",
                "type: liga",
                "team: Top 4 Teams",
            ]
        ),
        encoding="utf-8",
    )

    _, _, league_written = generate_markdown_files(
        game_stats_path=str(data_dir / "game_stats.json"),
        team_stats_path=str(data_dir / "team_stats_enhanced.json"),
        league_stats_path=str(data_dir / "league_averages.json"),
        playoff_averages_path=str(data_dir / "playoff_averages.json"),
        top4_averages_path=str(data_dir / "top4_averages.json"),
        output_games_dir=str(content_dir / "25-26-regular-season" / "games"),
        output_teams_dir=str(content_dir / "25-26-regular-season" / "teams"),
        output_liga_dir=str(liga_dir),
        season="25-26",
        phase="regular-season",
    )

    assert league_written == 3
    assert not stale_alias.exists()
    assert (liga_dir / "top-4-teams-25-26-regular-season.md").exists()


def test_run_stats_includes_upcoming_games_without_counting_them_in_team_stats(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    events_csv = data_dir / "events.csv"
    _sample_events_with_upcoming().to_csv(events_csv, index=False)

    result = run_stats_pipeline(input_csv_path=str(events_csv), output_dir=str(data_dir))

    game_stats = json.loads((data_dir / "game_stats.json").read_text(encoding="utf-8"))
    assert len(game_stats) == 2

    upcoming = next(game for game in game_stats if game["game_id"] == 2)
    assert upcoming["game_state"] == "scheduled"
    assert upcoming["start_time"] == "18:30"
    assert upcoming["game_events_count"] == 0
    assert upcoming["home_stats"]["games"] == 0
    assert upcoming["away_stats"]["games"] == 0

    team_stats = result["team_stats_enhanced"]
    assert team_stats["Team A"]["games"] == 1


def test_generate_markdown_accepts_playoff_team_stats_list(tmp_path: Path):
    data_dir = tmp_path / "data"
    content_dir = tmp_path / "content"
    data_dir.mkdir(parents=True, exist_ok=True)

    game_stats = [
        {
            "game_id": 1,
            "date": "2026-03-10",
            "home_team": "Team A",
            "away_team": "Team B",
            "home_stats": {"goals": 2},
            "away_stats": {"goals": 1},
        }
    ]
    team_stats_list = [
        {"team": "Team A", "stats": {"points": 3, "rank": 1}},
        {"team": "Team B", "stats": {"points": 0, "rank": 2}},
    ]
    league_stats = {"points_per_game": 1.5}

    (data_dir / "game_stats.json").write_text(json.dumps(game_stats), encoding="utf-8")
    (data_dir / "playoff_stats.json").write_text(json.dumps(team_stats_list), encoding="utf-8")
    (data_dir / "league_averages.json").write_text(json.dumps(league_stats), encoding="utf-8")

    _, teams_written, _ = generate_markdown_files(
        game_stats_path=str(data_dir / "game_stats.json"),
        team_stats_path=str(data_dir / "playoff_stats.json"),
        league_stats_path=str(data_dir / "league_averages.json"),
        output_games_dir=str(content_dir / "25-26-playoffs" / "games"),
        output_teams_dir=str(content_dir / "25-26-playoffs" / "teams"),
        output_liga_dir=str(content_dir / "25-26-playoffs" / "liga"),
        season="25-26",
        phase="playoffs",
    )

    assert teams_written == 2
    team_files = list((content_dir / "25-26-playoffs" / "teams").glob("*.md"))
    assert len(team_files) == 2


def test_generate_markdown_prefers_sqlite_and_keeps_json_as_fallback(tmp_path: Path):
    data_dir = tmp_path / "data"
    content_dir = tmp_path / "content"
    data_dir.mkdir(parents=True, exist_ok=True)

    raw_csv = data_dir / "data_25-26_regular_season.csv"
    _sample_events().to_csv(raw_csv, index=False)

    stats_payload = run_stats_pipeline(
        input_csv_path=str(raw_csv),
        output_dir=str(data_dir),
        season="25-26",
        phase="regular-season",
    )
    sync_pipeline_outputs(
        db_path=str(data_dir / "stats.db"),
        input_csv_path=str(raw_csv),
        season="25-26",
        phase="regular-season",
        stats_payload=stats_payload,
    )

    # Corrupt JSON after SQLite sync; markdown generation should still succeed from SQLite.
    (data_dir / "game_stats.json").write_text("[]", encoding="utf-8")
    (data_dir / "team_stats_enhanced.json").write_text("{}", encoding="utf-8")
    (data_dir / "league_averages.json").write_text("{}", encoding="utf-8")

    games_written, teams_written, league_written = generate_markdown_files(
        game_stats_path=str(data_dir / "game_stats.json"),
        team_stats_path=str(data_dir / "team_stats_enhanced.json"),
        league_stats_path=str(data_dir / "league_averages.json"),
        sqlite_path=str(data_dir / "stats.db"),
        output_games_dir=str(content_dir / "25-26-regular-season" / "games"),
        output_teams_dir=str(content_dir / "25-26-regular-season" / "teams"),
        output_liga_dir=str(content_dir / "25-26-regular-season" / "liga"),
        season="25-26",
        phase="regular-season",
    )

    assert games_written == 1
    assert teams_written == 2
    assert league_written == 3

    game_files = list((content_dir / "25-26-regular-season" / "games").glob("*.md"))
    assert len(game_files) == 1
    assert "home_team: Team A" in game_files[0].read_text(encoding="utf-8")
