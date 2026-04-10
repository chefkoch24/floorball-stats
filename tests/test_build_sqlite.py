import sqlite3

import pandas as pd

from src.build_sqlite import sync_pipeline_outputs, sync_player_stats_csv


def test_sync_pipeline_outputs_writes_current_run_tables(tmp_path):
    input_csv = tmp_path / "data_25-26_regular_season.csv"
    pd.DataFrame(
        [
            {
                "game_id": 1,
                "home_team_name": "Home",
                "away_team_name": "Away",
                "event_type": "goal",
            }
        ]
    ).to_csv(input_csv, index=False)

    db_path = tmp_path / "stats.db"
    counts = sync_pipeline_outputs(
        db_path=str(db_path),
        input_csv_path=str(input_csv),
        season="25-26",
        phase="regular-season",
        stats_payload={
            "game_stats": [
                {
                    "game_id": 1,
                    "home_team": "Home",
                    "away_team": "Away",
                    "date": "2026-04-10",
                }
            ],
            "team_stats_enhanced": {
                "Home": {"points": 3, "rank": 1},
                "Away": {"points": 0, "rank": 2},
            },
            "league_averages": {"points": 1.5},
            "top4_averages": {"points": 1.5},
        },
    )

    assert counts == {
        "events": 1,
        "game_stats": 1,
        "team_stats": 2,
        "playoff_team_stats": 0,
        "playdown_team_stats": 0,
        "top4_team_stats": 0,
        "league_stats": 2,
    }

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM game_stats").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM team_stats").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM league_stats").fetchone()[0] == 2
        row = conn.execute(
            "SELECT source_key, season, phase, game_id, home_team FROM game_stats"
        ).fetchone()
        assert row == ("data_25-26_regular_season", "25-26", "regular-season", 1, "Home")


def test_sync_player_stats_csv_replaces_existing_snapshot(tmp_path):
    csv_path = tmp_path / "player_stats.csv"
    pd.DataFrame(
        [
            {
                "player_uid": "p1",
                "player": "Player One",
                "season": "25-26",
                "phase": "regular-season",
                "points": 5,
            }
        ]
    ).to_csv(csv_path, index=False)

    db_path = tmp_path / "stats.db"
    assert sync_player_stats_csv(db_path=str(db_path), csv_path=str(csv_path)) == 1

    pd.DataFrame(
        [
            {
                "player_uid": "p2",
                "player": "Player Two",
                "season": "25-26",
                "phase": "playoffs",
                "points": 7,
            }
        ]
    ).to_csv(csv_path, index=False)

    assert sync_player_stats_csv(db_path=str(db_path), csv_path=str(csv_path)) == 1

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT player_uid, player, phase FROM player_stats ORDER BY player_uid"
        ).fetchall()
        assert rows == [("p2", "Player Two", "playoffs")]
