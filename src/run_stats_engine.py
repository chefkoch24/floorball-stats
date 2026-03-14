import argparse
import numpy as np
import pandas as pd
import json
from pathlib import Path

from src.stats_engine import StatsEngine
from src.team_stats import TeamStats
from src.utils import add_points, add_penalties, is_powerplay, is_boxplay, safe_div

EVENT_PENALTY = 'penalty'
EVENT_GOAL = 'goal'


def _parse_result_string_score(result_string: object) -> tuple[int, int] | None:
    if result_string is None:
        return None
    match = pd.Series([result_string]).astype(str).str.extract(r"(\d+)\s*:\s*(\d+)").iloc[0]
    if match.isna().any():
        return None
    return int(match[0]), int(match[1])

def _parse_sortkey_to_minute(sortkey: str) -> float:
    try:
        period_str, clock = str(sortkey).split("-", 1)
        minute_str, second_str = clock.split(":", 1)
        period = int(period_str)
        minute = int(minute_str)
        second = int(second_str)
    except (ValueError, AttributeError):
        return 0.0
    # Most providers use period-relative clock (00:00..19:59), but some
    # (notably Czech) provide absolute game clock in sortkey (e.g. 53:05 in P3).
    if period > 1 and minute >= 20:
        return round(minute + second / 60.0, 2)
    return round((period - 1) * 20 + minute + second / 60.0, 2)


def _build_gameflow_timeline(game_df: pd.DataFrame, home_team: str, away_team: str) -> dict:
    periods = pd.to_numeric(game_df.get("period"), errors="coerce").fillna(0).astype(int)
    has_extra_time = bool((periods >= 4).any())

    goals = game_df[game_df["event_type"] == EVENT_GOAL].copy()
    if {"home_goals", "guest_goals"}.issubset(goals.columns):
        goals = goals[~(goals["home_goals"].isna() & goals["guest_goals"].isna())]
    goals = goals[goals["period"].astype(int) <= 4]
    goals = goals.sort_values(by=["period", "sortkey"])

    timeline_minutes = [0.0]
    timeline_diffs = [0]
    timeline_home_goals = [0]
    timeline_away_goals = [0]
    home_goal_minutes = []
    home_goal_diffs = []
    away_goal_minutes = []
    away_goal_diffs = []
    home_penalty_minutes = []
    home_penalty_goals = []
    home_penalty_ends = []
    away_penalty_minutes = []
    away_penalty_goals = []
    away_penalty_ends = []
    home_major_penalty_minutes = []
    away_major_penalty_minutes = []

    def _to_int(value: object) -> int:
        if pd.isna(value):
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    running_home_goals = 0
    running_away_goals = 0
    goal_times: list[tuple[float, str]] = []

    for _, event in goals.iterrows():
        minute = _parse_sortkey_to_minute(event.get("sortkey", ""))
        scoring_team = str(event.get("event_team", ""))
        if scoring_team == home_team:
            running_home_goals += 1
        elif scoring_team == away_team:
            running_away_goals += 1
        else:
            # Unknown scoring team cannot be placed on a home/away timeline.
            continue

        home_goals = running_home_goals
        away_goals = running_away_goals
        diff = running_home_goals - running_away_goals
        timeline_minutes.append(minute)
        timeline_diffs.append(diff)
        timeline_home_goals.append(home_goals)
        timeline_away_goals.append(away_goals)
        goal_times.append((minute, scoring_team))

        if scoring_team == home_team:
            home_goal_minutes.append(minute)
            home_goal_diffs.append(diff)
        elif scoring_team == away_team:
            away_goal_minutes.append(minute)
            away_goal_diffs.append(diff)

    penalties = game_df[game_df["event_type"] == EVENT_PENALTY].copy()
    penalties = penalties[penalties["period"].astype(int) <= 4]
    penalties = penalties.sort_values(by=["period", "sortkey"])
    goal_events = game_df[game_df["event_type"] == EVENT_GOAL].copy()
    goal_events = goal_events[goal_events["period"].astype(int) <= 4]
    goal_events = goal_events.sort_values(by=["period", "sortkey"])

    timeline_events = list(zip(timeline_minutes, timeline_home_goals, timeline_away_goals))
    if not goal_times:
        goal_times = [
            (_parse_sortkey_to_minute(event.get("sortkey", "")), str(event.get("event_team", "")))
            for _, event in goal_events.iterrows()
        ]

    def _score_at(minute: float) -> tuple[int, int]:
        home = 0
        away = 0
        for m, h, a in timeline_events:
            if m <= minute:
                home = h
                away = a
            else:
                break
        return home, away

    for _, event in penalties.iterrows():
        minute = _parse_sortkey_to_minute(event.get("sortkey", ""))
        home_score, away_score = _score_at(minute)
        penalized_team = str(event.get("event_team", ""))
        penalty_type = str(event.get("penalty_type") or "")
        if penalty_type in {"penalty_10", "penalty_ms_full", "penalty_ms_tech"}:
            if penalized_team == home_team:
                home_major_penalty_minutes.append(minute)
            elif penalized_team == away_team:
                away_major_penalty_minutes.append(minute)
            continue
        if penalty_type not in {"penalty_2", "penalty_2and2"}:
            continue
        duration = 2
        if penalty_type == "penalty_2and2":
            duration = 4
        natural_end = round(minute + duration, 2)
        end_minute = natural_end
        # Minor penalties end early when the non-penalized team scores.
        if penalty_type in {"penalty_2", "penalty_2and2"}:
            for goal_minute, goal_team in goal_times:
                if goal_minute < minute or goal_minute > natural_end:
                    continue
                if goal_team and goal_team != penalized_team:
                    end_minute = goal_minute
                    break

        if penalized_team == home_team:
            home_penalty_minutes.append(minute)
            home_penalty_goals.append(home_score)
            home_penalty_ends.append(end_minute)
        elif penalized_team == away_team:
            away_penalty_minutes.append(minute)
            away_penalty_goals.append(away_score)
            away_penalty_ends.append(end_minute)

    timeline_max_minute = 70.0 if has_extra_time else 60.0

    def _csv(values: list[float | int]) -> str:
        return ",".join(str(v) for v in values)

    return {
        "timeline_minutes_csv": _csv(timeline_minutes),
        "timeline_diffs_csv": _csv(timeline_diffs),
        "timeline_home_goals_csv": _csv(timeline_home_goals),
        "timeline_away_goals_csv": _csv(timeline_away_goals),
        "home_goal_minutes_csv": _csv(home_goal_minutes),
        "home_goal_diffs_csv": _csv(home_goal_diffs),
        "away_goal_minutes_csv": _csv(away_goal_minutes),
        "away_goal_diffs_csv": _csv(away_goal_diffs),
        "home_penalty_minutes_csv": _csv(home_penalty_minutes),
        "home_penalty_goals_csv": _csv(home_penalty_goals),
        "home_penalty_ends_csv": _csv(home_penalty_ends),
        "away_penalty_minutes_csv": _csv(away_penalty_minutes),
        "away_penalty_goals_csv": _csv(away_penalty_goals),
        "away_penalty_ends_csv": _csv(away_penalty_ends),
        "home_major_penalty_minutes_csv": _csv(home_major_penalty_minutes),
        "away_major_penalty_minutes_csv": _csv(away_major_penalty_minutes),
        "timeline_max_minute": round(timeline_max_minute, 2),
    }


def _is_extra_time_period(period: int, ingame_status: str | None = None) -> bool:
    try:
        if int(period) >= 4:
            return True
    except (TypeError, ValueError):
        pass
    status = str(ingame_status or "").strip().lower()
    return status in {"extratime", "penalty_shots"}


def _points_from_final_score(team_goals: int, opp_goals: int, period: int, ingame_status: str | None = None) -> int:
    if team_goals > opp_goals:
        return 2 if _is_extra_time_period(period, ingame_status) else 3
    if team_goals == opp_goals:
        return 1
    return 1 if _is_extra_time_period(period, ingame_status) else 0


def stat_goals(events: pd.DataFrame, team: str):
    return int((events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team)]).shape[0])

def stat_goals_against(events: pd.DataFrame, team: str):
    return int((events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team)]).shape[0])

def stat_games(events: pd.DataFrame, team: str):
    return int(events['game_id'].nunique())


def _final_score_for_team(last_goal: pd.Series, team: str):
    is_home = team == last_goal['home_team_name']
    if is_home:
        team_goals = last_goal['home_goals']
        opp_goals = last_goal['guest_goals']
    else:
        team_goals = last_goal['guest_goals']
        opp_goals = last_goal['home_goals']

    period = last_goal['period']
    ingame_status = last_goal.get('ingame_status')
    if team_goals == opp_goals and _is_extra_time_period(period, ingame_status):
        parsed = _parse_result_string_score(last_goal.get('result_string'))
        if parsed is not None:
            home_final, away_final = parsed
            if is_home:
                team_goals, opp_goals = home_final, away_final
            else:
                team_goals, opp_goals = away_final, home_final
    return team_goals, opp_goals, period


def _sort_events_chronologically(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events
    ordered = events.copy()
    if "sortkey" in ordered.columns:
        ordered["_minute_sort"] = ordered["sortkey"].apply(_parse_sortkey_to_minute)
    else:
        ordered["_minute_sort"] = 0.0
    if "time_in_s" in ordered.columns:
        time_values = pd.to_numeric(ordered["time_in_s"], errors="coerce")
        ordered["_time_sort"] = time_values.where(time_values.notna(), ordered["_minute_sort"] * 60.0)
    else:
        ordered["_time_sort"] = ordered["_minute_sort"] * 60.0
    if "period" in ordered.columns:
        ordered["_period_sort"] = pd.to_numeric(ordered["period"], errors="coerce").fillna(0).astype(int)
    else:
        ordered["_period_sort"] = 0
    ordered = ordered.sort_values(by=["_time_sort", "_period_sort", "sortkey"] if "sortkey" in ordered.columns else ["_time_sort", "_period_sort"])
    return ordered.drop(columns=["_minute_sort", "_time_sort", "_period_sort"], errors="ignore")


def _last_goal_event(events: pd.DataFrame) -> pd.Series | None:
    goals = events[events['event_type'] == EVENT_GOAL]
    if goals.empty:
        return None
    goals = _sort_events_chronologically(goals)
    return goals.iloc[-1]


def _last_goals_per_game(events: pd.DataFrame):
    for _, game_df in events.groupby('game_id'):
        last_goal = _last_goal_event(game_df)
        if last_goal is not None:
            yield last_goal


def stat_wins(events: pd.DataFrame, team: str):
    wins = 0
    for last_goal in _last_goals_per_game(events):
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        if team_goals > opp_goals and int(period) <= 3:
            wins += 1
    return wins


def stat_over_time_wins(events: pd.DataFrame, team: str):
    wins = 0
    for last_goal in _last_goals_per_game(events):
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        if team_goals > opp_goals and int(period) == 4:
            wins += 1
    return wins


def stat_draws(events: pd.DataFrame, team: str):
    draws = 0
    for last_goal in _last_goals_per_game(events):
        team_goals, opp_goals, _ = _final_score_for_team(last_goal, team)
        if team_goals == opp_goals:
            draws += 1
    return draws


def stat_losses(events: pd.DataFrame, team: str):
    losses = 0
    for last_goal in _last_goals_per_game(events):
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        if team_goals < opp_goals and int(period) <= 3:
            losses += 1
    return losses


def stat_over_time_losses(events: pd.DataFrame, team: str):
    losses = 0
    for last_goal in _last_goals_per_game(events):
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        if team_goals < opp_goals and int(period) == 4:
            losses += 1
    return losses


def stat_penalty_shootout_wins(events: pd.DataFrame, team: str):
    wins = 0
    for last_goal in _last_goals_per_game(events):
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        if team_goals > opp_goals and int(period) == 5:
            wins += 1
    return wins


def stat_penalty_shootout_losses(events: pd.DataFrame, team: str):
    losses = 0
    for last_goal in _last_goals_per_game(events):
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        if team_goals < opp_goals and int(period) == 5:
            losses += 1
    return losses

def stat_points(events: pd.DataFrame, team: str):
    points = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        points += _points_from_final_score(team_goals, opp_goals, period, last_goal.get('ingame_status'))
    return points

def stat_goal_difference(events: pd.DataFrame, team: str):
    return stat_goals(events, team) - stat_goals_against(events, team)

def stat_points_max_difference(events: pd.DataFrame, team: str, num_goals: int = 2):
    points = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        diff = abs(team_goals - opp_goals)
        if diff <= num_goals:
            points += _points_from_final_score(team_goals, opp_goals, period, last_goal.get('ingame_status'))
    return points

def stat_goals_in_first_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['period'] == 1)].shape[0])

def stat_goals_in_second_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['period'] == 2)].shape[0])

def stat_goals_in_third_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['period'] == 3)].shape[0])

def stat_goals_in_overtime(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['period'] == 4)].shape[0])


def stat_goals_in_penalty_shootout(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['period'] == 5)].shape[0])

def stat_goals_in_powerplay(events: pd.DataFrame, team: str):
    penalties_against = []
    penalties_for = []
    goals_in_powerplay = 0
    for _, event in events.iterrows():
        if len(penalties_for) > 0:
            if event['time_in_s'] - penalties_for[0] >= 120:
                penalties_for.pop(0)
        if len(penalties_against) > 0:
            if event['time_in_s'] - penalties_against[0] >= 120:
                penalties_against.pop(0)

        if event['event_type'] == EVENT_PENALTY and event['event_team'] != team:
            penalties_against = add_penalties(event['penalty_type'], penalties_against, event['time_in_s'])
        if event['event_type'] == EVENT_PENALTY and event['event_team'] == team:
            penalties_for = add_penalties(event['penalty_type'], penalties_for, event['time_in_s'])

        if event['event_type'] == EVENT_GOAL and event['event_team'] == team:
            if is_powerplay(event['time_in_s'], penalties_for, penalties_against):
                goals_in_powerplay += 1
                penalties_against.pop(0)

    return goals_in_powerplay

def stat_goals_in_boxplay(events: pd.DataFrame, team: str):
    penalties_against = []
    penalties_for = []
    goals_in_boxplay = 0
    for _, event in events.iterrows():
        if len(penalties_for) > 0:
            if event['time_in_s'] - penalties_for[0] >= 120:
                penalties_for.pop(0)
        if len(penalties_against) > 0:
            if event['time_in_s'] - penalties_against[0] >= 120:
                penalties_against.pop(0)

        if event['event_type'] == EVENT_PENALTY and event['event_team'] != team:
            penalties_against = add_penalties(event['penalty_type'], penalties_against, event['time_in_s'])
        if event['event_type'] == EVENT_PENALTY and event['event_team'] == team:
            penalties_for = add_penalties(event['penalty_type'], penalties_for, event['time_in_s'])

        if event['event_type'] == EVENT_GOAL and event['event_team'] == team:
            if is_boxplay(event['time_in_s'], penalties_for, penalties_against):
                goals_in_boxplay += 1

    return goals_in_boxplay

def stat_goals_against_in_boxplay(events: pd.DataFrame, team: str):
    penalties_against = []
    penalties_for = []
    goals_against_in_boxplay = 0
    for _, event in events.iterrows():
        if len(penalties_for) > 0:
            if event['time_in_s'] - penalties_for[0] >= 120:
                penalties_for.pop(0)
        if len(penalties_against) > 0:
            if event['time_in_s'] - penalties_against[0] >= 120:
                penalties_against.pop(0)

        if event['event_type'] == EVENT_PENALTY and event['event_team'] != team:
            penalties_against = add_penalties(event['penalty_type'], penalties_against, event['time_in_s'])
        if event['event_type'] == EVENT_PENALTY and event['event_team'] == team:
            penalties_for = add_penalties(event['penalty_type'], penalties_for, event['time_in_s'])

        if event['event_type'] == EVENT_GOAL and event['event_team'] != team:
            if is_boxplay(event['time_in_s'], penalties_for, penalties_against):
                goals_against_in_boxplay += 1
                penalties_for.pop(0)

    return goals_against_in_boxplay

def stat_goals_against_in_powerplay(events: pd.DataFrame, team: str):
    penalties_against = []
    penalties_for = []
    goals_against_in_powerplay = 0
    for _, event in events.iterrows():
        if len(penalties_for) > 0:
            if event['time_in_s'] - penalties_for[0] >= 120:
                penalties_for.pop(0)
        if len(penalties_against) > 0:
            if event['time_in_s'] - penalties_against[0] >= 120:
                penalties_against.pop(0)

        if event['event_type'] == EVENT_PENALTY and event['event_team'] != team:
            penalties_against = add_penalties(event['penalty_type'], penalties_against, event['time_in_s'])
        if event['event_type'] == EVENT_PENALTY and event['event_team'] == team:
            penalties_for = add_penalties(event['penalty_type'], penalties_for, event['time_in_s'])

        if event['event_type'] == EVENT_GOAL and event['event_team'] != team:
            if is_powerplay(event['time_in_s'], penalties_for, penalties_against):
                goals_against_in_powerplay += 1

    return goals_against_in_powerplay

def stat_penalties_for_opponent(events: pd.DataFrame, team: str):
    # number of penalities for the opponent
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] != team)].shape[0])

def stat_penalties_for_team(events: pd.DataFrame, team: str):
    # number of penalities for the team
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team)].shape[0])

def stat_powerplay(events: pd.DataFrame, team: str):
    penalties_against = []
    penalties_for = []
    powerplays = 0

    def _expire_penalties(current_time: int):
        while penalties_for and current_time - penalties_for[0] >= 120:
            penalties_for.pop(0)
        while penalties_against and current_time - penalties_against[0] >= 120:
            penalties_against.pop(0)

    events_sorted = events.sort_values(by='time_in_s')
    for current_time, bucket in events_sorted.groupby('time_in_s', sort=True):
        _expire_penalties(current_time)
        prev_adv = max(0, len(penalties_against) - len(penalties_for))

        penalties = bucket[bucket['event_type'] == EVENT_PENALTY]
        for _, event in penalties.iterrows():
            if event['event_team'] != team:
                penalties_against = add_penalties(event['penalty_type'], penalties_against, event['time_in_s'])
            else:
                penalties_for = add_penalties(event['penalty_type'], penalties_for, event['time_in_s'])

        goals = bucket[bucket['event_type'] == EVENT_GOAL]
        for _, event in goals.iterrows():
            if event['event_team'] == team and is_powerplay(current_time, penalties_for, penalties_against):
                penalties_against.pop(0)

        new_adv = max(0, len(penalties_against) - len(penalties_for))
        if new_adv > prev_adv:
            powerplays += new_adv - prev_adv

    return int(powerplays)

def _events_for_period(events: pd.DataFrame, period: int) -> pd.DataFrame:
    return events[events['period'] == period]

def stat_powerplay_first_period(events: pd.DataFrame, team: str):
    return stat_powerplay(_events_for_period(events, 1), team)

def stat_powerplay_second_period(events: pd.DataFrame, team: str):
    return stat_powerplay(_events_for_period(events, 2), team)

def stat_powerplay_third_period(events: pd.DataFrame, team: str):
    return stat_powerplay(_events_for_period(events, 3), team)

def stat_powerplay_overtime(events: pd.DataFrame, team: str):
    return stat_powerplay(_events_for_period(events, 4), team)


def stat_boxplay(events: pd.DataFrame, team: str):
    penalties_against = []
    penalties_for = []
    boxplays = 0

    def _expire_penalties(current_time: int):
        while penalties_for and current_time - penalties_for[0] >= 120:
            penalties_for.pop(0)
        while penalties_against and current_time - penalties_against[0] >= 120:
            penalties_against.pop(0)

    events_sorted = events.sort_values(by='time_in_s')
    for current_time, bucket in events_sorted.groupby('time_in_s', sort=True):
        _expire_penalties(current_time)
        prev_adv = max(0, len(penalties_for) - len(penalties_against))

        penalties = bucket[bucket['event_type'] == EVENT_PENALTY]
        for _, event in penalties.iterrows():
            if event['event_team'] != team:
                penalties_against = add_penalties(event['penalty_type'], penalties_against, event['time_in_s'])
            else:
                penalties_for = add_penalties(event['penalty_type'], penalties_for, event['time_in_s'])

        goals = bucket[bucket['event_type'] == EVENT_GOAL]
        for _, event in goals.iterrows():
            if event['event_team'] != team and is_boxplay(current_time, penalties_for, penalties_against):
                penalties_for.pop(0)

        new_adv = max(0, len(penalties_for) - len(penalties_against))
        if new_adv > prev_adv:
            boxplays += new_adv - prev_adv

    return int(boxplays)

def stat_boxplay_first_period(events: pd.DataFrame, team: str):
    return stat_boxplay(_events_for_period(events, 1), team)

def stat_boxplay_second_period(events: pd.DataFrame, team: str):
    return stat_boxplay(_events_for_period(events, 2), team)

def stat_boxplay_third_period(events: pd.DataFrame, team: str):
    return stat_boxplay(_events_for_period(events, 3), team)

def stat_boxplay_overtime(events: pd.DataFrame, team: str):
    return stat_boxplay(_events_for_period(events, 4), team)

def _stat_points_after_period(events: pd.DataFrame, team: str, period: int):
    points = 0
    period_events = events[((events['event_type'] == EVENT_GOAL) | (events['event_type'] == EVENT_PENALTY)) & (events['period'] <= period)]
    if not period_events.empty:
        last_goal = _sort_events_chronologically(period_events).iloc[-1]
        if team == last_goal['home_team_name']:
            team_goals = last_goal['home_goals']
            opp_goals = last_goal['guest_goals']
        else:
            team_goals = last_goal['guest_goals']
            opp_goals = last_goal['home_goals']
        if team_goals > opp_goals:
            points += 3
        elif team_goals == opp_goals:
            points += 1
    return points


def stat_points_after_first_period(events: pd.DataFrame, team: str):
    return _stat_points_after_period(events, team, period=1)



def stat_points_after_second_period(events: pd.DataFrame, team: str):
    return _stat_points_after_period(events, team, period=2)

def stat_points_after_third_period(events: pd.DataFrame, team: str):
    return _stat_points_after_period(events, team, period=3)

def stat_points_after_55_minutes(events: pd.DataFrame, team: str):
    return _stat_points_after_minute(events, team, minute=55)

def stat_points_after_58_minutes(events: pd.DataFrame, team: str):
    return _stat_points_after_minute(events, team, minute=58)

def stat_points_after_59_minutes(events: pd.DataFrame, team: str):
    return _stat_points_after_minute(events, team, minute=59)

def _stat_points_after_minute(events: pd.DataFrame, team: str, minute: int):
    points = 0
    period_events = events[((events['event_type'] == EVENT_GOAL) | (events['event_type'] == EVENT_PENALTY))  &  (events.get('time_in_s', 0) <= minute * 60)]
    if not period_events.empty:
        last_goal = _sort_events_chronologically(period_events).iloc[-1]
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        points += _points_from_final_score(team_goals, opp_goals, period, last_goal.get('ingame_status'))
    return points

def stat_win_1(events: pd.DataFrame, team: str):
    win_1 = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        if team == last_goal['home_team_name']:
            diff = last_goal['home_goals'] - last_goal['guest_goals']
        else:
            diff = last_goal['guest_goals'] - last_goal['home_goals']
        if diff == 1:
            win_1 += 1
    return win_1

def stat_loss_1(events: pd.DataFrame, team: str):
    loss_1 = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        if team == last_goal['home_team_name']:
            diff = last_goal['home_goals'] - last_goal['guest_goals']
        else:
            diff = last_goal['guest_goals'] - last_goal['home_goals']
        if diff == -1:
            loss_1 += 1
    return loss_1

def stat_points_more_2_difference(events: pd.DataFrame, team: str):
    points = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        diff = abs(team_goals - opp_goals)
        if diff > 2:
            points += _points_from_final_score(team_goals, opp_goals, period, last_goal.get('ingame_status'))
    return points

def stat_close_game_win(events: pd.DataFrame, team: str):
    close_game_win = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        if team == last_goal['home_team_name']:
            diff = abs(last_goal['home_goals'] - last_goal['guest_goals'])
            team_goals = last_goal['home_goals']
            opp_goals = last_goal['guest_goals']
        else:
            diff = abs(last_goal['guest_goals'] - last_goal['home_goals'])
            team_goals = last_goal['guest_goals']
            opp_goals = last_goal['home_goals']
        if diff < 3 and team_goals > opp_goals:
            close_game_win += 1
    return close_game_win

def stat_close_game_loss(events: pd.DataFrame, team: str):
    close_game_loss = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        if team == last_goal['home_team_name']:
            diff = abs(last_goal['home_goals'] - last_goal['guest_goals'])
            team_goals = last_goal['home_goals']
            opp_goals = last_goal['guest_goals']
        else:
            diff = abs(last_goal['guest_goals'] - last_goal['home_goals'])
            team_goals = last_goal['guest_goals']
            opp_goals = last_goal['home_goals']
        if diff < 3 and team_goals < opp_goals:
            close_game_loss += 1
    return close_game_loss

def stat_close_game_overtime(events: pd.DataFrame, team: str):
    close_game_ot = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        if team == last_goal['home_team_name']:
            diff = abs(last_goal['home_goals'] - last_goal['guest_goals'])
            team_goals = last_goal['home_goals']
            opp_goals = last_goal['guest_goals']
            period = last_goal['period']
        else:
            diff = abs(last_goal['guest_goals'] - last_goal['home_goals'])
            team_goals = last_goal['guest_goals']
            opp_goals = last_goal['home_goals']
            period = last_goal['period']
        if diff < 3 and team_goals != opp_goals and _is_extra_time_period(period):
            close_game_ot += 1
    return close_game_ot

def stat_penalty_shot_goals(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['goal_type'] == 'penalty_shot')].shape[0])

def stat_penalty_shot_goals_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['goal_type'] == 'penalty_shot')].shape[0])

def stat_penalty_2(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & (events['penalty_type'] == 'penalty_2')].shape[0])

def stat_penalty_2and2(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & (events['penalty_type'] == 'penalty_2and2')].shape[0])

def stat_penalty_10(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & (events['penalty_type'] == 'penalty_10')].shape[0])

def stat_penalty_ms(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & ((events['penalty_type'] == 'penalty_ms_full') | (events['penalty_type'] == 'penalty_ms_tech'))].shape[0])

def stat_penalty_first_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & (events['period'] == 1)].shape[0])

def stat_penalty_second_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & (events['period'] == 2)].shape[0])

def stat_penalty_third_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & (events['period'] == 3)].shape[0])

def stat_penalty_overtime(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & (events['period'] == 4)].shape[0])

def _team_score_state(event: pd.Series, team: str):
    if event.get('home_team_name') == team:
        return event['home_goals'], event['guest_goals']
    if event.get('away_team_name') == team:
        return event['guest_goals'], event['home_goals']
    return None, None

def _goal_progression(events: pd.DataFrame) -> pd.DataFrame:
    """Return deduplicated in-game goals (periods 1-4) in chronological order."""
    goals = events[(events['event_type'] == EVENT_GOAL) & (events['period'] <= 4)].copy()
    if goals.empty:
        return goals
    goals = goals.sort_values(by=['time_in_s', 'sortkey'])
    goals['score_key'] = goals['home_goals'].astype(str) + ":" + goals['guest_goals'].astype(str)
    goals = goals[goals['score_key'].ne(goals['score_key'].shift())].copy()
    return goals.drop(columns=['score_key'])

def stat_take_the_lead_goals(events: pd.DataFrame, team: str):
    count = 0
    for _, event in _goal_progression(events).iterrows():
        if event['event_team'] == team:
            team_goals, opp_goals = _team_score_state(event, team)
            if team_goals is None:
                continue
            # Leading goal: a goal that turns a tie into a lead.
            if team_goals == opp_goals + 1:
                count += 1
    return count

def stat_equalizer_goals(events: pd.DataFrame, team: str):
    count = 0
    for _, event in _goal_progression(events).iterrows():
        if event['event_team'] == team:
            if event['home_goals'] - event['guest_goals'] == 0:
                count += 1
    return count

def stat_first_goal_of_match(events: pd.DataFrame, team: str):
    goals = _goal_progression(events)
    if goals.empty:
        return 0
    first = goals.iloc[0]
    return int(first['event_team'] == team)

def stat_take_the_lead_goals_against(events: pd.DataFrame, team: str):
    count = 0
    for _, event in _goal_progression(events).iterrows():
        if event['event_team'] != team:
            team_goals, opp_goals = _team_score_state(event, team)
            if team_goals is None:
                continue
            # Against: opponent scores to take the lead from a tie.
            if opp_goals == team_goals + 1:
                count += 1
    return count

def stat_equalizer_goals_against(events: pd.DataFrame, team: str):
    count = 0
    for _, event in _goal_progression(events).iterrows():
        if event['event_team'] != team:
            if event['home_goals'] - event['guest_goals'] == 0:
                count += 1
    return count

def stat_first_goal_of_match_against(events: pd.DataFrame, team: str):
    goals = _goal_progression(events)
    if goals.empty:
        return 0
    first = goals.iloc[0]
    return int(first['event_team'] != team)

def stat_goals_in_first_period_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['period'] == 1)].shape[0])

def stat_goals_in_second_period_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['period'] == 2)].shape[0])

def stat_goals_in_third_period_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['period'] == 3)].shape[0])

def stat_goals_in_overtime_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['period'] == 4)].shape[0])


def stat_goals_in_penalty_shootout_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['period'] == 5)].shape[0])

def stat_goals_not_in_boxplay(events: pd.DataFrame, team: str):
    total_goals_against = stat_goals_against(events, team)
    boxplay_goals_against = stat_goals_against_in_boxplay(events, team)
    return total_goals_against - boxplay_goals_against


def stat_goals_home(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['home_team_name'] == team)].shape[0])

def stat_goals_away(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['away_team_name'] == team)].shape[0])

def stat_goals_against_home(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['home_team_name'] == team)].shape[0])

def stat_goals_against_away(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['away_team_name'] == team)].shape[0])

def stat_home_points(events: pd.DataFrame, team: str):
    points = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None and last_goal['home_team_name'] == team:
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        points += _points_from_final_score(team_goals, opp_goals, period, last_goal.get('ingame_status'))
    return points

def stat_away_points(events: pd.DataFrame, team: str):
    points = 0
    for game_id, game_df in events.groupby('game_id'):
        last_goal = _last_goal_event(game_df)
        if last_goal is not None and last_goal['away_team_name'] == team:
            team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
            points += _points_from_final_score(team_goals, opp_goals, period, last_goal.get('ingame_status'))
    return points



def stat_points_against(events: pd.DataFrame, team: str):
    teams = list(events['home_team_name'].unique()) + list(events['away_team_name'].unique())
    teams = np.unique(teams)
    points_against = {str(t): 0 for t in teams if t != team}
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        opponent = last_goal['away_team_name'] if last_goal['home_team_name'] == team else last_goal['home_team_name']
        points = add_points(team, last_goal)[0]
        points_against[str(opponent)] += points
    return points_against

def build_engine() -> StatsEngine:
    engine = StatsEngine()
    engine.register_stat('points', stat_points)
    engine.register_stat('wins', stat_wins)
    engine.register_stat('over_time_wins', stat_over_time_wins)
    engine.register_stat('penalty_shootout_wins', stat_penalty_shootout_wins)
    engine.register_stat('draws', stat_draws)
    engine.register_stat('losses', stat_losses)
    engine.register_stat('over_time_losses', stat_over_time_losses)
    engine.register_stat('penalty_shootout_losses', stat_penalty_shootout_losses)
    engine.register_stat('goals', stat_goals)
    engine.register_stat('goals_against', stat_goals_against)
    engine.register_stat('games', stat_games)
    engine.register_stat('goal_difference', stat_goal_difference)
    engine.register_stat('points_max_difference_2', stat_points_max_difference)
    engine.register_stat('goals_in_first_period', stat_goals_in_first_period)
    engine.register_stat('goals_in_second_period', stat_goals_in_second_period)
    engine.register_stat('goals_in_third_period', stat_goals_in_third_period)
    engine.register_stat('goals_in_overtime', stat_goals_in_overtime)
    engine.register_stat('goals_in_penalty_shootout', stat_goals_in_penalty_shootout)
    engine.register_stat('goals_in_powerplay', stat_goals_in_powerplay)
    engine.register_stat('goals_in_boxplay', stat_goals_in_boxplay)
    engine.register_stat('goals_against_in_powerplay', stat_goals_against_in_powerplay)
    engine.register_stat('goals_against_in_boxplay', stat_goals_against_in_boxplay)
    engine.register_stat('powerplay', stat_powerplay)
    engine.register_stat('boxplay', stat_boxplay)
    engine.register_stat('powerplay_first_period', stat_powerplay_first_period)
    engine.register_stat('powerplay_second_period', stat_powerplay_second_period)
    engine.register_stat('powerplay_third_period', stat_powerplay_third_period)
    engine.register_stat('powerplay_overtime', stat_powerplay_overtime)
    engine.register_stat('boxplay_first_period', stat_boxplay_first_period)
    engine.register_stat('boxplay_second_period', stat_boxplay_second_period)
    engine.register_stat('boxplay_third_period', stat_boxplay_third_period)
    engine.register_stat('boxplay_overtime', stat_boxplay_overtime)
    engine.register_stat('points_after_first_period', stat_points_after_first_period)
    engine.register_stat('points_after_second_period', stat_points_after_second_period)
    engine.register_stat('points_after_third_period', stat_points_after_third_period)
    engine.register_stat('points_after_55_min', stat_points_after_55_minutes)
    engine.register_stat('points_after_58_min', stat_points_after_58_minutes)
    engine.register_stat('points_after_59_min', stat_points_after_59_minutes)
    engine.register_stat('win_1', stat_win_1)
    engine.register_stat('loss_1', stat_loss_1)
    engine.register_stat('points_more_2_difference', stat_points_more_2_difference)
    engine.register_stat('close_game_win', stat_close_game_win)
    engine.register_stat('close_game_loss', stat_close_game_loss)
    engine.register_stat('close_game_overtime', stat_close_game_overtime)
    engine.register_stat('penalty_shot_goals', stat_penalty_shot_goals)
    engine.register_stat('penalty_shot_goals_against', stat_penalty_shot_goals_against)
    engine.register_stat('penalty_2', stat_penalty_2)
    engine.register_stat('penalty_2and2', stat_penalty_2and2)
    engine.register_stat('penalty_10', stat_penalty_10)
    engine.register_stat('penalty_ms', stat_penalty_ms)
    engine.register_stat('penalty_first_period', stat_penalty_first_period)
    engine.register_stat('penalty_second_period', stat_penalty_second_period)
    engine.register_stat('penalty_third_period', stat_penalty_third_period)
    engine.register_stat('penalty_overtime', stat_penalty_overtime)
    engine.register_stat('take_the_lead_goals', stat_take_the_lead_goals)
    engine.register_stat('equalizer_goals', stat_equalizer_goals)
    engine.register_stat('first_goal_of_match', stat_first_goal_of_match)
    engine.register_stat('goals_in_first_period_against', stat_goals_in_first_period_against)
    engine.register_stat('goals_in_second_period_against', stat_goals_in_second_period_against)
    engine.register_stat('goals_in_third_period_against', stat_goals_in_third_period_against)
    engine.register_stat('goals_in_overtime_against', stat_goals_in_overtime_against)
    engine.register_stat('goals_in_penalty_shootout_against', stat_goals_in_penalty_shootout_against)
    engine.register_stat('goals_against_in_boxplay', stat_goals_against_in_boxplay)
    engine.register_stat('goals_home', stat_goals_home)
    engine.register_stat('goals_away', stat_goals_away)
    engine.register_stat('goals_against_home', stat_goals_against_home)
    engine.register_stat('goals_against_away', stat_goals_against_away)
    engine.register_stat('home_points', stat_home_points)
    engine.register_stat('away_points', stat_away_points)
    engine.register_stat('take_the_lead_goals_against', stat_take_the_lead_goals_against)
    engine.register_stat('equalizer_goals_against', stat_equalizer_goals_against)
    engine.register_stat('first_goal_of_match_against', stat_first_goal_of_match_against)
    engine.register_stat('points_against', stat_points_against)
    return engine


def run_stats_pipeline(input_csv_path: str, output_dir: str) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_csv_path)
    if {"event_type", "home_goals", "guest_goals"}.issubset(df.columns):
        # Some sources include malformed goal rows (e.g. mixed timeline blocks)
        # without any score snapshot. Drop them before computing stats.
        invalid_goals = (
            (df["event_type"] == EVENT_GOAL)
            & df["home_goals"].isna()
            & df["guest_goals"].isna()
        )
        df = df.loc[~invalid_goals].copy()
    teams = list(df['home_team_name'].unique()) + list(df['away_team_name'].unique())
    teams = np.unique(teams)
    engine = build_engine()
    game_stats = []

    for game_id, game_df in df.groupby('game_id'):

        home_team = game_df['home_team_name'].iloc[0]
        away_team = game_df['away_team_name'].iloc[0]
        home_stats = engine.calculate_team_stats(game_df, home_team).stats.copy()

        away_stats = engine.calculate_team_stats(game_df, away_team).stats.copy()

        for stats in [home_stats, away_stats]:
            stats['powerplay_efficiency'] = safe_div(stats['goals_in_powerplay'], stats['powerplay'], 4, True, "n.a.")
            stats['boxplay_efficiency'] = safe_div(stats['goals_against_in_boxplay'], stats['boxplay'], 4, True, "n.a.")
            if type(stats['boxplay_efficiency']) != str:
                stats['boxplay_efficiency'] = 100 - stats['boxplay_efficiency']
            stats['penalties'] = stats['penalty_2'] + stats['penalty_2and2'] + stats['penalty_10'] + stats['penalty_ms']


        game_stat = {
            'game_id': game_id,
            'date': game_df['game_date'].iloc[0] if 'game_date' in game_df.columns else None,
            'start_time': game_df['game_start_time'].iloc[0] if 'game_start_time' in game_df.columns else None,
            'result_string': game_df['result_string'].iloc[0] if 'result_string' in game_df.columns else None,
            'ingame_status': game_df['ingame_status'].iloc[0] if 'ingame_status' in game_df.columns else None,
            'home_team': home_team,
            'home_stats': home_stats,
            'away_team': away_team,
            'away_stats': away_stats
        }
        game_stat.update(_build_gameflow_timeline(game_df, home_team, away_team))
        game_stats.append(game_stat)

    # aggregate per game


    # save to json
    with open(output_path / 'game_stats.json', 'w') as f:
        json.dump(game_stats, f, indent=4)

    # aggregate per team
    team_stats = {}

    for game in game_stats:
        for side in ['home', 'away']:
            team = game[f'{side}_team']
            stats = game[f'{side}_stats']
            if team not in team_stats:
                team_stats[team] = {}
            for key, value in stats.items():
                if key == 'points_against':
                    if key not in team_stats[team]:
                        team_stats[team][key] = {}
                    for opponent, pts in value.items():
                        team_stats[team][key][opponent] = team_stats[team][key].get(opponent, 0) + pts
                elif key not in ['powerplay_efficiency', 'boxplay_efficiency']:
                    if key not in team_stats[team]:
                        team_stats[team][key] = value
                    else:
                        try:
                            team_stats[team][key] += value
                        except Exception as e:
                            raise ValueError(f"Error adding {key} for team {team}: {e}") from e

    with open(output_path / 'team_stats.json', 'w') as f:
        json.dump(team_stats, f, indent=4)

    # add ratio features
    for team, stats in team_stats.items():
        stats['powerplay_efficiency'] = safe_div(stats['goals_in_powerplay'], stats['powerplay'], 4, True, "n.a.")
        stats['boxplay_efficiency'] = safe_div(stats['goals_against_in_boxplay'], stats['boxplay'], 4, True, "n.a.")
        if type(stats['boxplay_efficiency']) != str:
            stats['boxplay_efficiency'] = 100 - stats['boxplay_efficiency']
        stats['percent_goals_first_period'] = safe_div(stats['goals_in_first_period'], stats['goals'], 4, True, "n.a.")
        stats['percent_goals_second_period'] = safe_div(stats['goals_in_second_period'], stats['goals'], 4, True,
                                                        "n.a.")
        stats['percent_goals_third_period'] = safe_div(stats['goals_in_third_period'], stats['goals'], 4, True, "n.a.")
        stats['percent_goals_overtime'] = safe_div(stats['goals_in_overtime'], stats['goals'], 4, True, "n.a.")
        stats['percent_goals_first_period_against'] = safe_div(stats['goals_in_first_period_against'],
                                                               stats['goals_against'], 4, True, "n.a.")
        stats['percent_goals_second_period_against'] = safe_div(stats['goals_in_second_period_against'],
                                                                stats['goals_against'], 4, True, "n.a.")
        stats['percent_goals_third_period_against'] = safe_div(stats['goals_in_third_period_against'],
                                                               stats['goals_against'], 4, True, "n.a.")
        stats['percent_goals_overtime_against'] = safe_div(stats['goals_in_overtime_against'], stats['goals_against'],
                                                           4, True, "n.a.")
        stats['points_per_game'] = safe_div(stats['points'], stats['games'])
        stats['goal_difference'] = stats['goals'] - stats['goals_against']
        stats['goal_difference_per_game'] = safe_div(stats['goal_difference'], stats['games'])

        stats['scoring_ratio'] = safe_div(stats['goals'], stats['goals_against'], 2, False, "n.a.")
        stats['goals_per_game'] = safe_div(stats['goals'], stats['games'], 2)
        stats['goals_against_per_game'] = safe_div(stats['goals_against'], stats['games'], 2)
        stats['boxplay_per_game'] = safe_div(stats['boxplay'], stats['games'], 2)
        stats['powerplay_per_game'] = safe_div(stats['powerplay'], stats['games'], 2)

    # convert to a list of dicts
    all_stats = [TeamStats(team, stats) for team, stats in team_stats.items()]
    ranking = sorted(all_stats, key=lambda x: (-x.stats.get('points', 0), -x.stats.get('goal_difference', 0), -x.stats.get('goals', 0)))
    for i, entry in enumerate(ranking):
        team_stats[entry.team]['rank'] = i + 1

    with open(output_path / 'team_stats_enhanced.json', 'w') as f:
        json.dump(team_stats, f, indent=4)

    playoff_stats, playdown_stats, top4_stats = engine.split_by_rank(all_stats)
    league_stats = engine.aggregate_stats(all_stats)
    playoff_averages = engine.aggregate_stats(playoff_stats)
    playdown_averages = engine.aggregate_stats(playdown_stats)
    top4_averages = engine.aggregate_stats(top4_stats)
    with open(output_path / 'playoff_stats.json', 'w') as f:
        json.dump([team.to_dict() for team in playoff_stats], f, indent=4)

    with open(output_path / 'playdown_stats.json', 'w') as f:
        json.dump([team.to_dict() for team in playdown_stats], f, indent=4)

    with open(output_path / 'top4_stats.json', 'w') as f:
        json.dump([team.to_dict() for team in top4_stats], f, indent=4)

    with open(output_path / 'playoff_averages.json', 'w') as f:
        json.dump(playoff_averages, f, indent=4)

    with open(output_path / 'playdown_averages.json', 'w') as f:
        json.dump(playdown_averages, f, indent=4)

    with open(output_path / 'top4_averages.json', 'w') as f:
        json.dump(top4_averages, f, indent=4)

    with open(output_path / 'league_averages.json', 'w') as f:
        json.dump(league_stats, f, indent=4)
    return {
        "game_stats": game_stats,
        "team_stats_enhanced": team_stats,
        "playoff_stats": [team.to_dict() for team in playoff_stats],
        "playdown_stats": [team.to_dict() for team in playdown_stats],
        "top4_stats": [team.to_dict() for team in top4_stats],
        "playoff_averages": playoff_averages,
        "playdown_averages": playdown_averages,
        "top4_averages": top4_averages,
        "league_averages": league_stats,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_csv_path", default="data/data_regular_season.csv")
    parser.add_argument("--output_dir", default="data")
    return parser.parse_args()


def main():
    args = parse_args()
    run_stats_pipeline(input_csv_path=args.input_csv_path, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
