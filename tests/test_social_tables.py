import json
from pathlib import Path

from src.social_media.tables import build_home_away_split_table, write_home_away_split_table


def test_build_home_away_split_table_derives_expected_fields_and_sorting():
    team_stats = {
        "Team B": {
            "rank": 2,
            "points": 4,
            "goal_difference": 0,
            "goals": 5,
            "home_points": 3,
            "away_points": 1,
            "goals_home": 4,
            "goals_against_home": 2,
            "goals_away": 1,
            "goals_against_away": 3,
        },
        "Team A": {
            "rank": 1,
            "points": 6,
            "goal_difference": 4,
            "goals": 7,
            "home_points": 2,
            "away_points": 4,
            "goals_home": 3,
            "goals_against_home": 2,
            "goals_away": 4,
            "goals_against_away": 1,
        },
    }
    game_stats = [
        {"home_team": "Team A", "away_team": "Team B"},
        {"home_team": "Team B", "away_team": "Team A"},
    ]

    table = build_home_away_split_table(team_stats, game_stats, season="25-26", phase="regular-season")

    assert table["table_type"] == "home_away_split"
    assert table["season"] == "25-26"
    assert table["phase"] == "regular-season"
    assert [row["team"] for row in table["rows"]] == ["Team A", "Team B"]

    first_row = table["rows"][0]
    assert first_row["home_diff"] == 1
    assert first_row["away_diff"] == 3
    assert first_row["split_points"] == -2
    assert first_row["split_diff"] == -2
    assert first_row["home_games"] == 1
    assert first_row["away_games"] == 1
    assert first_row["home_points_per_game"] == 2.0
    assert first_row["away_points_per_game"] == 4.0
    assert first_row["home_record_label"] == "3:2"
    assert first_row["away_record_label"] == "4:1"


def test_write_home_away_split_table_persists_json(tmp_path: Path):
    output_file = tmp_path / "home_away_split_table.json"
    team_stats = {
        "Team A": {
            "rank": 1,
            "points": 3,
            "goal_difference": 1,
            "goals": 2,
            "home_points": 3,
            "away_points": 0,
            "goals_home": 2,
            "goals_against_home": 1,
            "goals_away": 0,
            "goals_against_away": 0,
        }
    }
    game_stats = [{"home_team": "Team A", "away_team": "Team B"}]

    write_home_away_split_table(team_stats, output_file, game_stats, season="25-26", phase="regular-season")

    persisted = json.loads(output_file.read_text(encoding="utf-8"))
    assert persisted["rows"][0]["team"] == "Team A"
    assert persisted["rows"][0]["split_points"] == 3
    assert persisted["rows"][0]["home_games"] == 1
