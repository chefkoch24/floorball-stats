import numpy as np
import pandas as pd
import json

from src.stats_engine import StatsEngine
from src.team_stats import TeamStats
from src.utils import add_points, add_penalties, is_powerplay, is_boxplay, safe_div

EVENT_PENALTY = 'penalty'
EVENT_GOAL = 'goal'

def stat_goals(events: pd.DataFrame, team: str):
    return int((events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team)]).shape[0])

def stat_goals_against(events: pd.DataFrame, team: str):
    return int((events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team)]).shape[0])

def stat_games(events: pd.DataFrame, team: str):
    return int(events['game_id'].nunique())

def stat_points(events: pd.DataFrame, team: str):
    points = 0
    last_goal = events[events['event_type'] == EVENT_GOAL].iloc[-1] if not events[events['event_type'] == EVENT_GOAL].empty else None
    if last_goal is not None:
        if team == last_goal['home_team_name']:
            team_goals = last_goal['home_goals']
            opp_goals = last_goal['guest_goals']
            period = last_goal['period']
        else:
            team_goals = last_goal['guest_goals']
            opp_goals = last_goal['home_goals']
            period = last_goal['period']
        if team_goals > opp_goals:
            points += 2 if period == 4 else 3
        elif team_goals == opp_goals:
            points += 1
        elif team_goals < opp_goals:
            points += 1 if period == 4 else 0
    return points

def stat_goal_difference(events: pd.DataFrame, team: str):
    return stat_goals(events, team) - stat_goals_against(events, team)

def stat_points_max_difference(events: pd.DataFrame, team: str, num_goals: int = 2):
    points = 0
    last_goal = events[events['event_type'] == EVENT_GOAL].iloc[-1] if not events[events['event_type'] == EVENT_GOAL].empty else None
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
        if diff <= num_goals:
            if team_goals > opp_goals:
                points += 2 if period == 4 else 3
            elif team_goals == opp_goals:
                points += 1
            elif team_goals < opp_goals:
                points += 1 if period == 4 else 0
    return points

def stat_goals_in_first_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['period'] == 1)].shape[0])

def stat_goals_in_second_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['period'] == 2)].shape[0])

def stat_goals_in_third_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['period'] == 3)].shape[0])

def stat_goals_in_overtime(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['period'] == 4)].shape[0])

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

        if is_powerplay(event['time_in_s'], penalties_for, penalties_against):
            powerplays += 1
            if event['event_type'] == EVENT_GOAL and event['event_team'] == team:
                penalties_against.pop(0)
    return powerplays


def stat_boxplay(events: pd.DataFrame, team: str):
    penalties_against = []
    penalties_for = []
    boxplays = 0
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


            if is_boxplay(event['time_in_s'], penalties_for, penalties_against):
                boxplays += 1
                if event['event_type'] == EVENT_GOAL and event['event_team'] != team:
                    penalties_for.pop(0)

    return boxplays

def _stat_points_after_period(events: pd.DataFrame, team: str, period: int):
    points = 0
    period_events = events[((events['event_type'] == EVENT_GOAL) | (events['event_type'] == EVENT_PENALTY)) & (events['period'] <= period)]
    if not period_events.empty:
        last_goal = period_events.iloc[-1]
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
        last_goal = period_events.iloc[-1]
        if team == last_goal['home_team_name']:
            team_goals = last_goal['home_goals']
            opp_goals = last_goal['guest_goals']
            period = last_goal['period']
        else:
            team_goals = last_goal['guest_goals']
            opp_goals = last_goal['home_goals']
            period = last_goal['period']
        if team_goals > opp_goals:
            points += 2 if period == 4 else 3
        elif team_goals == opp_goals:
            points += 1
        elif team_goals < opp_goals:
            points += 1 if period == 4 else 0
    return points

def stat_win_1(events: pd.DataFrame, team: str):
    win_1 = 0
    last_goal = events[events['event_type'] == EVENT_GOAL].iloc[-1] if not events[events['event_type'] == EVENT_GOAL].empty else None
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
    last_goal = events[events['event_type'] == EVENT_GOAL].iloc[-1] if not events[events['event_type'] == EVENT_GOAL].empty else None
    if last_goal is not None:
        if team == last_goal['home_team_name']:
            diff = last_goal['home_goals'] - last_goal['guest_goals']
        else:
            diff = last_goal['guest_goals'] - last_goal['home_goals']
        if diff == -1:
            loss_1 += 1
    return loss_1

def stat_points_max_difference_3(events: pd.DataFrame, team: str):
    points = 0
    last_goal = events[events['event_type'] == EVENT_GOAL].iloc[-1] if not events[events['event_type'] == EVENT_GOAL].empty else None
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
        if diff < 3:
            if team_goals > opp_goals:
                points += 2 if period == 4 else 3
            elif team_goals == opp_goals:
                points += 1
            elif team_goals < opp_goals:
                points += 1 if period == 4 else 0
    return points

def stat_points_more_3_difference(events: pd.DataFrame, team: str):
    points = 0
    last_goal = events[events['event_type'] == EVENT_GOAL].iloc[-1] if not events[events['event_type'] == EVENT_GOAL].empty else None
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
        if diff >= 3:
            if team_goals > opp_goals:
                points += 2 if period == 4 else 3
            elif team_goals == opp_goals:
                points += 1
            elif team_goals < opp_goals:
                points += 1 if period == 4 else 0
    return points

def stat_close_game_win(events: pd.DataFrame, team: str):
    close_game_win = 0
    last_goal = events[events['event_type'] == EVENT_GOAL].iloc[-1] if not events[events['event_type'] == EVENT_GOAL].empty else None
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
    last_goal = events[events['event_type'] == EVENT_GOAL].iloc[-1] if not events[events['event_type'] == EVENT_GOAL].empty else None
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
    last_goal = events[events['event_type'] == EVENT_GOAL].iloc[-1] if not events[events['event_type'] == EVENT_GOAL].empty else None
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
        if diff < 3 and team_goals != opp_goals and period == 4:
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

def stat_leading_goals(events: pd.DataFrame, team: str):
    count = 0
    for _, event in events.iterrows():
        if event['event_type'] == EVENT_GOAL and event['event_team'] == team:
            if event['home_goals'] - event['guest_goals'] == 1:
                count += 1
    return count

def stat_equalizer_goals(events: pd.DataFrame, team: str):
    count = 0
    for _, event in events.iterrows():
        if event['event_type'] == EVENT_GOAL and event['event_team'] == team:
            if event['home_goals'] - event['guest_goals'] == 0:
                count += 1
    return count

def stat_first_goal_of_match(events: pd.DataFrame, team: str):
    count = 0
    for _, event in events.iterrows():
        if event['event_type'] == EVENT_GOAL and event['event_team'] == team:
            if (event['home_goals'] == 1 and event['guest_goals'] == 0) or (event['home_goals'] == 0 and event['guest_goals'] == 1):
                count += 1
    return count

def stat_leading_goals_against(events: pd.DataFrame, team: str):
    count = 0
    for _, event in events.iterrows():
        if event['event_type'] == EVENT_GOAL and event['event_team'] != team:
            if event['home_goals'] - event['guest_goals'] == 1:
                count += 1
    return count

def stat_equalizer_goals_against(events: pd.DataFrame, team: str):
    count = 0
    for _, event in events.iterrows():
        if event['event_type'] == EVENT_GOAL and event['event_team'] != team:
            if event['home_goals'] - event['guest_goals'] == 0:
                count += 1
    return count

def stat_first_goal_of_match_against(events: pd.DataFrame, team: str):
    count = 0
    for _, event in events.iterrows():
        if event['event_type'] == EVENT_GOAL and event['event_team'] != team:
            if (event['home_goals'] == 1 and event['guest_goals'] == 0) or (event['home_goals'] == 0 and event['guest_goals'] == 1):
                count += 1
    return count

def stat_goals_in_first_period_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['period'] == 1)].shape[0])

def stat_goals_in_second_period_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['period'] == 2)].shape[0])

def stat_goals_in_third_period_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['period'] == 3)].shape[0])

def stat_goals_in_overtime_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['period'] == 4)].shape[0])

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
    last_goal = events[events['event_type'] == EVENT_GOAL].iloc[-1] if not events[events['event_type'] == EVENT_GOAL].empty else None
    if last_goal is not None and last_goal['home_team_name'] == team:
        if team == last_goal['home_team_name']:
            team_goals = last_goal['home_goals']
            opp_goals = last_goal['guest_goals']
            period = last_goal['period']
        else:
            team_goals = last_goal['guest_goals']
            opp_goals = last_goal['home_goals']
            period = last_goal['period']
        if team_goals > opp_goals:
            points += 2 if period == 4 else 3
        elif team_goals == opp_goals:
            points += 1
        elif team_goals < opp_goals:
            points += 1 if period == 4 else 0
    return points

def stat_away_points(events: pd.DataFrame, team: str):
    points = 0
    for game_id, game_df in events.groupby('game_id'):
        last_goal = game_df[game_df['event_type'] == EVENT_GOAL].iloc[-1] if not game_df[game_df['event_type'] == EVENT_GOAL].empty else None
        if last_goal is not None and last_goal['away_team_name'] == team:
            if team == last_goal['home_team_name']:
                team_goals = last_goal['home_goals']
                opp_goals = last_goal['guest_goals']
                period = last_goal['period']
            else:
                team_goals = last_goal['guest_goals']
                opp_goals = last_goal['home_goals']
                period = last_goal['period']
            if team_goals > opp_goals:
                points += 2 if period == 4 else 3
            elif team_goals == opp_goals:
                points += 1
            elif team_goals < opp_goals:
                points += 1 if period == 4 else 0
    return points



def stat_points_against(events: pd.DataFrame, team: str):
    teams = list(events['home_team_name'].unique()) + list(events['away_team_name'].unique())
    teams = np.unique(teams)
    points_against = {str(t): 0 for t in teams if t != team}
    last_goal = events[events['event_type'] == EVENT_GOAL].iloc[-1] if not events[events['event_type'] == EVENT_GOAL].empty else None
    if last_goal is not None:
        opponent = last_goal['away_team_name'] if last_goal['home_team_name'] == team else last_goal['home_team_name']
        points = add_points(team, last_goal)[0]
        points_against[str(opponent)] += points
    return points_against

if __name__ == "__main__":
    df = pd.read_csv("../data/data_regular_season.csv")
    teams = list(df['home_team_name'].unique()) + list(df['away_team_name'].unique())
    teams = np.unique(teams)

    engine = StatsEngine()
    engine.register_stat('points', stat_points)
    engine.register_stat('goals', stat_goals)
    engine.register_stat('goals_against', stat_goals_against)
    engine.register_stat('games', stat_games)
    engine.register_stat('goal_difference', stat_goal_difference)
    engine.register_stat('points_max_difference_2', stat_points_max_difference)
    engine.register_stat('goals_in_first_period', stat_goals_in_first_period)
    engine.register_stat('goals_in_second_period', stat_goals_in_second_period)
    engine.register_stat('goals_in_third_period', stat_goals_in_third_period)
    engine.register_stat('goals_in_overtime', stat_goals_in_overtime)
    engine.register_stat('goals_in_powerplay', stat_goals_in_powerplay)
    engine.register_stat('goals_in_boxplay', stat_goals_in_boxplay)
    engine.register_stat('goals_against_in_powerplay', stat_goals_against_in_powerplay)
    engine.register_stat('goals_against_in_boxplay', stat_goals_against_in_boxplay)
    engine.register_stat('powerplay', stat_powerplay)
    engine.register_stat('boxplay', stat_boxplay)
    engine.register_stat('points_after_first_period', stat_points_after_first_period)
    engine.register_stat('points_after_second_period', stat_points_after_second_period)
    engine.register_stat('points_after_third_period', stat_points_after_third_period)
    engine.register_stat('points_after_55_min', stat_points_after_55_minutes)
    engine.register_stat('points_after_58_min', stat_points_after_58_minutes)
    engine.register_stat('points_after_59_min', stat_points_after_59_minutes)
    engine.register_stat('win_1', stat_win_1)
    engine.register_stat('loss_1', stat_loss_1)
    engine.register_stat('points_max_difference_3', stat_points_max_difference_3)
    engine.register_stat('points_more_3_difference', stat_points_more_3_difference)
    engine.register_stat('close_game_win', stat_close_game_win)
    engine.register_stat('close_game_loss', stat_close_game_loss)
    engine.register_stat('close_game_overtime', stat_close_game_overtime)
    engine.register_stat('penalty_shot_goals', stat_penalty_shot_goals)
    engine.register_stat('penalty_shot_goals_against', stat_penalty_shot_goals_against)
    engine.register_stat('penalty_2', stat_penalty_2)
    engine.register_stat('penalty_2and2', stat_penalty_2and2)
    engine.register_stat('penalty_10', stat_penalty_10)
    engine.register_stat('penalty_ms', stat_penalty_ms)
    engine.register_stat('leading_goals', stat_leading_goals)
    engine.register_stat('equalizer_goals', stat_equalizer_goals)
    engine.register_stat('first_goal_of_match', stat_first_goal_of_match)
    engine.register_stat('goals_in_first_period_against', stat_goals_in_first_period_against)
    engine.register_stat('goals_in_second_period_against', stat_goals_in_second_period_against)
    engine.register_stat('goals_in_third_period_against', stat_goals_in_third_period_against)
    engine.register_stat('goals_in_overtime_against', stat_goals_in_overtime_against)
    engine.register_stat('goals_against_in_boxplay', stat_goals_against_in_boxplay)
    engine.register_stat('goals_home', stat_goals_home)
    engine.register_stat('home_points', stat_home_points)
    engine.register_stat('away_points', stat_away_points)
    engine.register_stat('points_against', stat_points_against)
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


        game_stat = {
            'game_id': game_id,
            'home_team': home_team,
            'home_stats': home_stats,
            'away_team': away_team,
            'away_stats': away_stats
        }
        game_stats.append(game_stat)

    # aggregate per game


    # save to json
    with open('../data/game_stats.json', 'w') as f:
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
                if key not in ['points_against', 'powerplay_efficiency', 'boxplay_efficiency']:
                    if key not in team_stats[team]:
                        team_stats[team][key] = value
                    else:
                        try:
                            team_stats[team][key] += value
                        except Exception as e:
                            print(f"Error adding {key} for team {team}: {e}")


    with open('../data/team_stats.json', 'w') as f:
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


    print(team_stats)
    with open('../data/team_stats_enhanced.json', 'w') as f:
        json.dump(team_stats, f, indent=4)


    # convert to a list of dicts
    all_stats = [TeamStats(team, stats) for team, stats in team_stats.items()]





    playoff_stats, playdown_stats, top4_stats = engine.split_by_rank(all_stats)
    league_stats = engine.aggregate_stats(all_stats)
    print('Playoff Stats:', [t.stats for t in playoff_stats])
    print('Playdown Stats:', [t.stats for t in playdown_stats])
    print('Top4 Stats:', [t.stats for t in top4_stats])
    print('Ligaschnitt:', league_stats)

    with open('../data/playoff_stats.json', 'w') as f:
        json.dump([team.to_dict() for team in playoff_stats], f, indent=4)

    with open('../data/playdown_stats.json', 'w') as f:
        json.dump([team.to_dict() for team in playdown_stats], f, indent=4)

    with open('../data/top4_stats.json', 'w') as f:
        json.dump([team.to_dict() for team in top4_stats], f, indent=4)

    with open('../data/league_averages.json', 'w') as f:
        json.dump(league_stats, f, indent=4)








