import pandas as pd

from src.run_stats_engine import (
    _build_gameflow_timeline,
    stat_away_points,
    stat_boxplay,
    stat_losses,
    stat_over_time_losses,
    stat_over_time_wins,
    stat_penalty_first_period,
    stat_penalty_overtime,
    stat_penalty_second_period,
    stat_penalty_third_period,
    stat_first_goal_of_match,
    stat_first_goal_of_match_against,
    stat_take_the_lead_goals,
    stat_take_the_lead_goals_against,
    stat_equalizer_goals,
    stat_equalizer_goals_against,
    stat_points,
    stat_points_after_55_minutes,
    stat_points_after_58_minutes,
    stat_points_after_59_minutes,
    stat_points_against,
    stat_points_max_difference,
    stat_points_more_2_difference,
    stat_powerplay,
    stat_wins,
)


def _goal_event(
    game_id: int,
    sortkey: str,
    period: int,
    home: str,
    away: str,
    home_goals: int,
    guest_goals: int,
    event_team: str,
):
    return {
        "game_id": game_id,
        "event_type": "goal",
        "event_team": event_team,
        "home_team_name": home,
        "away_team_name": away,
        "home_goals": home_goals,
        "guest_goals": guest_goals,
        "period": period,
        "sortkey": sortkey,
        "time_in_s": (period - 1) * 20 * 60 + int(sortkey.split("-")[1].split(":")[0]) * 60 + int(sortkey.split("-")[1].split(":")[1]),
        "goal_type": "normal",
        "penalty_type": None,
    }


def _event(
    game_id: int,
    sortkey: str,
    period: int,
    home: str,
    away: str,
    event_type: str,
    event_team: str,
    home_goals: int = 0,
    guest_goals: int = 0,
    penalty_type: str | None = None,
):
    return {
        "game_id": game_id,
        "event_type": event_type,
        "event_team": event_team,
        "home_team_name": home,
        "away_team_name": away,
        "home_goals": home_goals,
        "guest_goals": guest_goals,
        "period": period,
        "sortkey": sortkey,
        "time_in_s": (period - 1) * 20 * 60 + int(sortkey.split("-")[1].split(":")[0]) * 60 + int(sortkey.split("-")[1].split(":")[1]),
        "goal_type": "normal",
        "penalty_type": penalty_type,
    }


def test_stat_points_regular_and_overtime():
    regular = pd.DataFrame(
        [
            _goal_event(1, "1-01:00", 1, "A", "B", 1, 0, "A"),
            _goal_event(1, "3-19:00", 3, "A", "B", 4, 2, "A"),
        ]
    )
    overtime = pd.DataFrame(
        [
            _goal_event(2, "3-19:59", 3, "A", "B", 2, 2, "B"),
            _goal_event(2, "4-02:00", 4, "A", "B", 2, 3, "B"),
        ]
    )
    shootout = pd.DataFrame(
        [
            _goal_event(3, "3-19:59", 3, "A", "B", 4, 4, "B"),
            _goal_event(3, "5-10:00", 5, "A", "B", 5, 4, "A"),
        ]
    )

    assert stat_points(regular, "A") == 3
    assert stat_points(regular, "B") == 0
    assert stat_points(overtime, "A") == 1
    assert stat_points(overtime, "B") == 2
    assert stat_points(shootout, "A") == 2
    assert stat_points(shootout, "B") == 1


def test_shootout_results_are_not_counted_as_regular_or_overtime_wins_losses():
    shootout = pd.DataFrame(
        [
            _goal_event(3, "3-19:59", 3, "A", "B", 4, 4, "B"),
            _goal_event(3, "5-10:00", 5, "A", "B", 5, 4, "A"),
        ]
    )

    assert stat_wins(shootout, "A") == 0
    assert stat_losses(shootout, "A") == 0
    assert stat_over_time_wins(shootout, "A") == 0
    assert stat_over_time_losses(shootout, "A") == 0


def test_stat_points_after_minutes_uses_last_event_before_threshold():
    events = pd.DataFrame(
        [
            _goal_event(1, "3-14:30", 3, "A", "B", 4, 3, "A"),  # 54:30
            _goal_event(1, "3-17:10", 3, "A", "B", 4, 4, "B"),  # 57:10
            _goal_event(1, "3-18:20", 3, "A", "B", 5, 4, "A"),  # 58:20
            _goal_event(1, "3-19:10", 3, "A", "B", 5, 5, "B"),  # 59:10
            _goal_event(1, "4-01:00", 4, "A", "B", 6, 5, "A"),  # overtime winner
        ]
    )

    assert stat_points_after_55_minutes(events, "A") == 3
    assert stat_points_after_58_minutes(events, "A") == 1
    assert stat_points_after_59_minutes(events, "A") == 3


def test_stat_away_points_counts_only_games_where_team_is_away():
    events = pd.DataFrame(
        [
            # Team A away, wins in OT -> 2 points
            _goal_event(1, "4-01:00", 4, "B", "A", 2, 3, "A"),
            # Team A home, should not count toward away points
            _goal_event(2, "3-19:00", 3, "A", "C", 4, 1, "A"),
        ]
    )

    assert stat_away_points(events, "A") == 2


def test_stat_points_against_tracks_points_for_latest_opponent():
    events = pd.DataFrame(
        [
            _goal_event(1, "3-19:00", 3, "A", "B", 4, 2, "A"),
        ]
    )

    points_against = stat_points_against(events, "A")
    assert points_against["B"] == 3


def test_powerplay_counts_opportunities_not_events_during_advantage():
    events = pd.DataFrame(
        [
            _event(1, "1-10:00", 1, "A", "B", "penalty", "B", penalty_type="penalty_2"),
            _event(1, "1-10:30", 1, "A", "B", "timeout", "A"),
            _event(1, "1-11:00", 1, "A", "B", "timeout", "B"),
        ]
    )
    assert stat_powerplay(events, "A") == 1
    assert stat_boxplay(events, "B") == 1


def test_powerplay_does_not_count_coincidental_penalties_at_same_time():
    events = pd.DataFrame(
        [
            _event(1, "2-05:00", 2, "A", "B", "penalty", "B", penalty_type="penalty_2"),
            _event(1, "2-05:00", 2, "A", "B", "penalty", "A", penalty_type="penalty_2"),
        ]
    )
    assert stat_powerplay(events, "A") == 0
    assert stat_boxplay(events, "A") == 0


def test_penalties_are_counted_per_period():
    events = pd.DataFrame(
        [
            _event(1, "1-02:00", 1, "A", "B", "penalty", "A", penalty_type="penalty_2"),
            _event(1, "2-03:00", 2, "A", "B", "penalty", "A", penalty_type="penalty_2"),
            _event(1, "3-04:00", 3, "A", "B", "penalty", "A", penalty_type="penalty_10"),
            _event(1, "4-01:00", 4, "A", "B", "penalty", "A", penalty_type="penalty_2"),
        ]
    )
    assert stat_penalty_first_period(events, "A") == 1
    assert stat_penalty_second_period(events, "A") == 1
    assert stat_penalty_third_period(events, "A") == 1
    assert stat_penalty_overtime(events, "A") == 1


def test_game_flow_metrics_ignore_duplicate_goal_rows():
    events = pd.DataFrame(
        [
            _goal_event(1, "1-01:00", 1, "A", "B", 1, 0, "A"),
            _goal_event(1, "1-01:00", 1, "A", "B", 1, 0, "A"),  # duplicate
            _goal_event(1, "2-05:00", 2, "A", "B", 1, 1, "B"),
            _goal_event(1, "2-05:00", 2, "A", "B", 1, 1, "B"),  # duplicate
            _goal_event(1, "3-10:00", 3, "A", "B", 2, 1, "A"),
        ]
    )

    assert stat_first_goal_of_match(events, "A") == 1
    assert stat_first_goal_of_match_against(events, "A") == 0
    assert stat_take_the_lead_goals(events, "A") == 2
    assert stat_take_the_lead_goals_against(events, "A") == 0
    assert stat_equalizer_goals(events, "A") == 0
    assert stat_equalizer_goals_against(events, "A") == 1


def test_game_flow_metrics_exclude_penalty_shootout_goals():
    events = pd.DataFrame(
        [
            _goal_event(1, "3-19:00", 3, "A", "B", 1, 0, "A"),
            _goal_event(1, "3-19:30", 3, "A", "B", 1, 1, "B"),
            _goal_event(1, "5-01:00", 5, "A", "B", 2, 1, "A"),  # shootout
            _goal_event(1, "5-01:30", 5, "A", "B", 2, 2, "B"),  # shootout
        ]
    )

    assert stat_take_the_lead_goals(events, "A") == 1
    assert stat_equalizer_goals(events, "A") == 0
    assert stat_take_the_lead_goals_against(events, "A") == 0
    assert stat_equalizer_goals_against(events, "A") == 1


def test_points_max_difference_2_counts_games_with_diff_of_two():
    events = pd.DataFrame(
        [
            _goal_event(1, "3-19:00", 3, "A", "B", 5, 3, "A"),
        ]
    )

    assert stat_points_max_difference(events, "A") == 3
    assert stat_points_max_difference(events, "B") == 0


def test_points_more_2_difference_counts_only_games_above_two():
    close_game = pd.DataFrame(
        [
            _goal_event(1, "3-19:00", 3, "A", "B", 5, 3, "A"),
        ]
    )
    big_margin = pd.DataFrame(
        [
            _goal_event(2, "3-19:00", 3, "A", "B", 6, 3, "A"),
        ]
    )

    assert stat_points_more_2_difference(close_game, "A") == 0
    assert stat_points_more_2_difference(big_margin, "A") == 3


def test_gameflow_handles_czech_absolute_clock_sortkeys():
    events = pd.DataFrame(
        [
            _goal_event(1, "1-05:08", 1, "Home", "Away", 0, 1, "Away"),
            _goal_event(1, "1-06:47", 1, "Home", "Away", 1, 1, "Home"),
            _goal_event(1, "2-27:20", 2, "Home", "Away", 2, 1, "Home"),
            _goal_event(1, "3-53:05", 3, "Home", "Away", 3, 1, "Home"),
        ]
    )

    flow = _build_gameflow_timeline(events, "Home", "Away")
    minutes = [float(v) for v in flow["timeline_minutes_csv"].split(",") if v]
    assert minutes == [0.0, 5.13, 6.78, 27.33, 53.08]
    assert flow["timeline_max_minute"] == 60.0


def test_gameflow_uses_70_minutes_for_extra_time_games():
    events = pd.DataFrame(
        [
            _goal_event(1, "3-19:30", 3, "Home", "Away", 2, 2, "Away"),
            _goal_event(1, "4-01:00", 4, "Home", "Away", 3, 2, "Home"),
        ]
    )

    flow = _build_gameflow_timeline(events, "Home", "Away")
    assert flow["timeline_max_minute"] == 70.0
