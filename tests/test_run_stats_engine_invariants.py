import json
from pathlib import Path

import pandas as pd

from src.run_stats_engine import run_stats_pipeline


def _event(
    game_id: int,
    game_date: str,
    event_type: str,
    event_team: str,
    home: str,
    away: str,
    home_goals: int,
    guest_goals: int,
    period: int,
    sortkey: str,
    result_string: str,
    penalty_type: str | None = None,
):
    return {
        "game_id": game_id,
        "game_date": game_date,
        "game_start_time": "18:30:00",
        "event_type": event_type,
        "event_team": event_team,
        "home_team_name": home,
        "away_team_name": away,
        "home_goals": home_goals,
        "guest_goals": guest_goals,
        "period": period,
        "sortkey": sortkey,
        "goal_type": "goal",
        "penalty_type": penalty_type,
        "result_string": result_string,
        "ingame_status": None,
    }


def _sample_events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _event(1, "2026-03-10", "goal", "Team A", "Team A", "Team B", 1, 0, 1, "1-01:00", "2-1"),
            _event(1, "2026-03-10", "penalty", "Team B", "Team A", "Team B", 1, 0, 1, "1-02:00", "2-1", "penalty_2"),
            _event(1, "2026-03-10", "goal", "Team A", "Team A", "Team B", 2, 0, 1, "1-02:30", "2-1"),
            _event(1, "2026-03-10", "goal", "Team B", "Team A", "Team B", 2, 1, 3, "3-19:00", "2-1"),
            _event(2, "2026-03-11", "goal", "Team A", "Team B", "Team A", 0, 1, 2, "2-05:00", "1-2"),
            _event(2, "2026-03-11", "goal", "Team B", "Team B", "Team A", 1, 1, 3, "3-10:00", "1-2"),
            _event(2, "2026-03-11", "penalty", "Team B", "Team B", "Team A", 1, 1, 3, "3-11:00", "1-2", "penalty_2"),
            _event(2, "2026-03-11", "goal", "Team A", "Team B", "Team A", 1, 2, 3, "3-15:00", "1-2"),
        ]
    )


def _parse_result_string(value: str) -> tuple[int, int]:
    left, right = value.replace(":", "-").split("-")
    return int(left.strip()), int(right.strip())


def test_efficiency_and_stat_invariants_are_bounded(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    events_csv = data_dir / "events.csv"
    _sample_events().to_csv(events_csv, index=False)

    result = run_stats_pipeline(input_csv_path=str(events_csv), output_dir=str(data_dir))
    team_stats = result["team_stats_enhanced"]

    percent_fields = [
        "powerplay_efficiency",
        "boxplay_efficiency",
        "percent_goals_first_period",
        "percent_goals_second_period",
        "percent_goals_third_period",
        "percent_goals_overtime",
        "percent_goals_first_period_against",
        "percent_goals_second_period_against",
        "percent_goals_third_period_against",
        "percent_goals_overtime_against",
    ]

    non_negative_fields = [
        "goals",
        "goals_against",
        "powerplay",
        "boxplay",
        "penalty_2",
        "penalty_2and2",
        "penalty_10",
        "penalty_ms",
        "wins",
        "over_time_wins",
        "penalty_shootout_wins",
        "draws",
        "losses",
        "over_time_losses",
        "penalty_shootout_losses",
    ]

    for stats in team_stats.values():
        assert 0 <= stats["points_per_game"] <= 3

        for key in percent_fields:
            value = stats[key]
            if value == "n.a.":
                continue
            assert 0 <= value <= 100, f"{key} out of range: {value}"

        for key in non_negative_fields:
            assert stats[key] >= 0, f"{key} should be >= 0"

        assert stats["goals"] == stats["goals_home"] + stats["goals_away"]
        assert stats["goals_against"] == stats["goals_against_home"] + stats["goals_against_away"]


def test_game_score_and_timeline_consistency(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    events_csv = data_dir / "events.csv"
    _sample_events().to_csv(events_csv, index=False)

    run_stats_pipeline(input_csv_path=str(events_csv), output_dir=str(data_dir))

    game_stats = json.loads((data_dir / "game_stats.json").read_text(encoding="utf-8"))

    for game in game_stats:
        if game.get("result_string"):
            home_final, away_final = _parse_result_string(str(game["result_string"]))
            assert game["home_stats"]["goals"] == home_final
            assert game["away_stats"]["goals"] == away_final

        home_timeline = [int(v) for v in str(game.get("timeline_home_goals_csv", "")).split(",") if v]
        away_timeline = [int(v) for v in str(game.get("timeline_away_goals_csv", "")).split(",") if v]

        assert home_timeline == sorted(home_timeline)
        assert away_timeline == sorted(away_timeline)


def test_playoff_split_uses_regular_season_top8_eligibility(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    regular_csv = data_dir / "regular.csv"
    playoffs_csv = data_dir / "playoffs.csv"

    regular_events = pd.DataFrame(
        [
            _event(1, "2026-02-01", "goal", "Team 1", "Team 1", "Team 9", 5, 0, 3, "3-19:00", "5-0"),
            _event(2, "2026-02-02", "goal", "Team 2", "Team 2", "Team 10", 5, 0, 3, "3-19:00", "5-0"),
            _event(3, "2026-02-03", "goal", "Team 3", "Team 3", "Team 4", 2, 1, 3, "3-19:00", "2-1"),
            _event(4, "2026-02-04", "goal", "Team 5", "Team 5", "Team 6", 2, 1, 3, "3-19:00", "2-1"),
            _event(5, "2026-02-05", "goal", "Team 7", "Team 7", "Team 8", 2, 1, 3, "3-19:00", "2-1"),
        ]
    )
    regular_events.to_csv(regular_csv, index=False)

    # Team 9 and Team 10 should be in playdowns only, even if they play in this dataset.
    playoff_events = pd.DataFrame(
        [
            _event(101, "2026-03-10", "goal", "Team 9", "Team 9", "Team 10", 3, 0, 3, "3-19:00", "3-0"),
        ]
    )
    playoff_events.to_csv(playoffs_csv, index=False)

    result = run_stats_pipeline(
        input_csv_path=str(playoffs_csv),
        output_dir=str(data_dir),
        phase="playoffs",
        pregame_history_csv_paths=[str(regular_csv)],
    )

    assert [team["team"] for team in result["playoff_stats"]] == []
    assert [team["team"] for team in result["playdown_stats"]] == ["Team 9", "Team 10"]
