from datetime import datetime
import pandas as pd
import numpy as np
import argparse
import os
from matplotlib import pyplot as plt


def str2bool(val):
    if isinstance(val, bool):
        return val
    if val.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif val.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Expected boolean value.')

def create_path_if_not_exists(directory_path):
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

def dict_to_markdown(dictionary):
    markdown = ""
    # add meta data
    date = datetime.now().strftime('%Y-%m-%d')
    typ = 'liga' if dictionary['team'] not in teams else 'teams'
    markdown += "Date: " + date + "\n"
    markdown += f"Title: {stats['team'].replace('_', '-')}\n"
    markdown += f"Category: {args.year}-{time_of_year}, {typ}\n"
    markdown += f"Slug: {generate_slug(dictionary['team'])}\n"
    if typ == 'teams':
        markdown += "Platzierungsverlauf:" + f"{args.year}-{time_of_year}/teams/" + f"{generate_slug(dictionary['team'])}_platzierungsverlauf.png\n"
    for key, value in dictionary.items():
        if key != 'points_against':
            markdown += f"{key}: {value}\n"
        else:
            markdown += f"Tags:"
            for k, v in value.items():
                markdown += f"  {k}: {v},"
            markdown += "\n"
    return markdown


def generate_slug(name: str):
    filename = name.replace(' ', '-').lower()
    filename = filename.replace('ö', 'oe')
    filename = filename.replace('ä', 'ae')
    filename = filename.replace('ü', 'ue')
    filename = filename.replace('ß', 'ss')
    return filename + f'-{args.year}-{time_of_year}'

def initalize_stats(team, teams):
    return{'team': team,
        'goals': 0,
        'goals_in_first_period': 0,
        'goals_in_second_period': 0,
        'goals_in_third_period': 0,
        'goals_in_overtime': 0,
        'goals_in_boxplay': 0,
        'goals_in_powerplay': 0,
        'leading_goals': 0,
        'equalizer_goals': 0,
        'first_goal_of_match': 0,
        'goals_against': 0,
        'leading_goals_against': 0,
        'equalizer_goals_against': 0,
        'first_goal_of_match_against': 0,
        'goals_in_first_period_against': 0,
        'goals_in_second_period_against': 0,
        'goals_in_third_period_against': 0,
        'goals_in_overtime_against': 0,
        'goals_against_in_boxplay': 0,
        'goals_against_in_powerplay': 0,
        'goals_not_in_boxplay': 0,
        'boxplay': 0,
        'powerplay': 0,
        'boxplay_first_period': 0,
        'boxplay_second_period': 0,
        'boxplay_third_period': 0,
        'boxplay_overtime': 0,
        'powerplay_first_period': 0,
        'powerplay_second_period': 0,
        'powerplay_third_period': 0,
        'powerplay_overtime': 0,
        'games': 0,
        'goals_home': 0,
        'goals_away': 0,
        'goals_against_home': 0,
        'goals_against_away': 0,
        'points': 0,
        'home_points': 0,
        'away_points': 0,
        'wins': 0,
        'over_time_wins': 0,
        'losses': 0,
        'over_time_losses': 0,
        'draws': 0,
        'points_against': {t: 0 for t in teams if t != team},
        'points_after_first_period': 0,
        'points_after_second_period': 0,
        'points_after_third_period': 0,
        'points_after_55_min': 0,
        'points_after_58_min': 0,
        'points_after_59_min': 0,
        'win_1':0,
        'loss_1':0,
        'points_max_difference_3': 0,
        'points_more_3_difference': 0,
        'close_game_win': 0,
        'close_game_loss': 0,
        'close_game_overtime': 0,
        'penalty_shot_goals': 0,
        'penalty_shot_goals_against': 0,
        'penalty_2': 0,
        'penalty_2and2': 0,
        'penalty_10': 0,
        'penalty_ms': 0,
    }


def transform_in_seconds(data):
    times = []
    for d in data['sortkey']:
        period, time = d.split('-')
        min, sec = time.split(':')
        time_in_s = (int(period)-1) * 20 * 60 + int(min) * 60 + int(sec)
        times.append(time_in_s)
    data['time_in_s'] = times
    return data

def is_boxplay(time):
    if len(penalties_for) > len(penalties_against):
        if time - penalties_for[0] <= 120:
            return True
        else:
            return False
    else:
        return False

def is_powerplay(time):
    if len(penalties_for) < len(penalties_against):
        if time - penalties_against[0] <= 120:
            return True
        else:
            return False
    else:
        return False

def add_penalties(penalty_type, penalties, time):
    if penalty_type == 'penalty_2' or penalty_type == 'penalty_10':
        penalties.append(time)
    elif penalty_type == 'penalty_2and2' or penalty_type == 'penalty_ms_full' or penalty_type == 'penalty_ms_tech':
        penalties.append(time)
        penalties.append(time)
    return penalties

def calculate_rank_after_gamedays(all_logs_after_game):
    teams = {x['team']:[] for x in all_logs_after_game}
    gamedays = max([x['game'] for x in all_logs_after_game])
    for gameday in range(1, gamedays+1):
        gameday_stats = [x for x in all_logs_after_game if x['game'] == gameday]
        ranking = sorted(gameday_stats, key=lambda x: (-x['points'], -x['goal_difference'], -x['goals']))
        for i, team in enumerate(ranking):
            teams[team['team']].append(i+1)
    return teams

def create_visualization_rankings(data, path):
    for team in data.keys():
        plt.figure(figsize=(8, 6))  # Set a custom figure size
        plt.scatter(x=range(len(data[team])), y=data[team], label=team)
        plt.plot(range(len(data[team])), data[team])
        plt.title(f"Platzierungsverlauf {team}")
        # Customize the x-axis and y-axis scale and labels
        plt.xticks(range(len(data[team])), [f"{i + 1}" for i in range(len(data[team]))])
        plt.yticks(range(13))  # Reverse the y-axis scale

        # Add gridlines
        plt.grid(True, linestyle='--', alpha=0.7)

        # Set margins
        plt.margins(0.5)  # Adjust the margin as needed

        plt.xlim(-0.1, len(data[team]) - 0.9)  # Set custom limits for x-axis
        plt.ylim(0.5, 12.5)  # Set custom limits for y-axis
        plt.xlabel('Spieltag')
        plt.ylabel('Platzierung')
        plt.gca().invert_yaxis()
        plt.tight_layout()  # Ensure the labels are not cut off
        plt.savefig(os.path.join(path, f'{generate_slug(team)}_platzierungsverlauf.png'))

def add_points(team, event):
    if team == event['home_team_name']:
        team_final = 'home_goals'
        opponent_final = 'guest_goals'
    else:
        team_final = 'guest_goals'
        opponent_final = 'home_goals'
    if event[team_final] > event[opponent_final]:
        if event['period'] == 4:
            return 2, 'over_time_wins', event[team_final] - event[opponent_final]
        else:
            return 3, 'wins', event[team_final] - event[opponent_final]
    elif event[team_final] == event[opponent_final]:
        return 1, 'draws', event[team_final] - event[opponent_final]
    elif event[team_final] < event[opponent_final]:
        if event['period'] == 4:
            return 1, 'over_time_losses', event[team_final] - event[opponent_final]
        else:
            return 0, 'losses',  event[team_final] - event[opponent_final]
    else:
        return 0, 'losses',  event[team_final]- event[opponent_final]

def read_data(path):
    return pd.read_csv(path)

def safe_div(numerator, denominator,  rounding=2, in_percent= False, default: float | str = 0.0):
    """Divide and return default if denominator is 0 or None."""
    if denominator:
        val = round(numerator / denominator, rounding)
        if in_percent:
            return val * 100
        else:
            return val
    else:
        return default




arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("--input_path", type=str, default="data/data_regular_season.csv")
arg_parser.add_argument("--output_path", type=str, default="data/enriched_data_regular_season.csv")
arg_parser.add_argument("--year", type=str, default='22-23')
arg_parser.add_argument("--is_playoffs", type=str2bool, nargs='?', const=True, default=False)
args, _ = arg_parser.parse_known_args()

data = read_data(args.input_path)
teams = list(data['home_team_name'].unique()) + list(data['away_team_name'].unique())
teams = np.unique(teams)
time_of_year = 'playoffs' if args.is_playoffs else 'regular-season'
EVENT_GOAL = 'goal'
EVENT_PENALTY = 'penalty'
OUTPUT_FOLDER = f'content/{args.year}-{time_of_year}/teams/'
OUTPUT_FOLDER_LIGA = f'content/{args.year}-{time_of_year}/liga/'
create_path_if_not_exists(OUTPUT_FOLDER)
create_path_if_not_exists(OUTPUT_FOLDER_LIGA)

playoff_stats = []
playdown_stats = []
average_stats = []
top4_team_stats = []
goal_differences_in_game = []



all = []
all_logs_after_game = []
for _ , team in enumerate(teams):
    stats = initalize_stats(team, teams)
    events_from_team = data[(data['home_team_name'] == team) | (data['away_team_name'] == team)]
    events_from_team = transform_in_seconds(events_from_team)
    enriched_events = []
    all_stats = []
    prev_period = 100
    last_goal_event = None
    for game in events_from_team['game_id'].unique():
        logs_after_game = {}
        game_events = events_from_team[events_from_team['game_id'] == game]
        penalties_for = []
        penalties_against = []
        stats['games'] += 1
        calculated_55_min = False
        calculated_58_min = False
        calculated_59_min = False
        index = 0
        for i, event in game_events.iterrows():
                index += 1
                # reset variables for new game
                if prev_period != event['period']:
                    if event['period'] == 2:
                        stats['points_after_first_period'] += add_points(team,last_goal_event)[0]
                    elif event['period'] == 3:
                        stats['points_after_second_period'] += add_points(team, last_goal_event)[0]

                if (event['time_in_s'] >= 55 * 60 and event['time_in_s'] < 60 * 60) and not calculated_55_min:
                    if last_goal_event['period'] != 4:
                        stats['points_after_55_min'] += add_points(team, last_goal_event)[0]
                    else:
                        stats['points_after_55_min'] += 1
                    calculated_55_min = True
                if (event['time_in_s'] >= 58 * 60 and event['time_in_s'] < 60 * 60) and not calculated_58_min:
                    if last_goal_event['period'] != 4:
                        stats['points_after_58_min'] += add_points(team, last_goal_event)[0]
                    else:
                        stats['points_after_58_min'] += 1
                    calculated_58_min = True
                if (event['time_in_s'] >= 59 * 60 and event['time_in_s'] < 60 * 60)  and not calculated_59_min:
                    if last_goal_event['period'] != 4:
                        stats['points_after_59_min'] += add_points(team, last_goal_event)[0]
                    else:
                        stats['points_after_59_min'] += 1
                    calculated_59_min = True

                # check if penalties are over
                if len(penalties_for) > 0:
                    if event['time_in_s'] - penalties_for[0] >= 120:
                        penalties_for.pop(0)
                if len(penalties_against) > 0:
                    if event['time_in_s'] - penalties_against[0] >= 120:
                        penalties_against.pop(0)
                # our goals
                if event['event_type'] == EVENT_GOAL and event['event_team'] == team:
                    stats['goals'] += 1
                    if event['goal_type'] == 'penalty_shot':
                        stats['penalty_shot_goals'] += 1
                    if event['period'] == 1:
                        stats['goals_in_first_period'] += 1
                    elif event['period'] == 2:
                        stats['goals_in_second_period'] += 1
                    elif event['period'] == 3:
                        stats['goals_in_third_period'] += 1
                    elif event['period'] == 4:
                        stats['goals_in_overtime'] += 1
                    if is_boxplay(event['time_in_s']):
                        stats['goals_in_boxplay'] += 1
                        event['goal_in_boxplay'] = 1
                    if is_powerplay(event['time_in_s']):
                        if event['time_in_s'] - penalties_against[0] <= 120:
                            stats['goals_in_powerplay'] += 1
                            penalties_against.pop(0) # remove penalty
                            event['is_powerplay_goal'] = 1

                    if event['home_goals'] - event['guest_goals'] == 1:
                        stats['leading_goals'] += 1

                    if event['home_goals'] - event['guest_goals'] == 0:
                        stats['equalizer_goals'] += 1

                    if (event['home_goals'] == 1 and event['guest_goals'] == 0) or (event['home_goals'] == 0 and event['guest_goals'] == 1):
                        stats['first_goal_of_match'] +=1

                    if event['event_team'] == event['home_team_name']:
                        stats['goals_home'] += 1
                    else:
                        stats['goals_away'] += 1

                # goals against
                if event['event_type'] == EVENT_GOAL and event['event_team'] != team:
                    stats['goals_against'] += 1
                    if event['goal_type'] == 'penalty_shot':
                        stats['penalty_shot_goals_against'] += 1
                    if event['period'] == 1:
                        stats['goals_in_first_period_against'] += 1
                    elif event['period'] == 2:
                        stats['goals_in_second_period_against'] += 1
                    elif event['period'] == 3:
                        stats['goals_in_third_period_against'] += 1
                    elif event['period'] == 4:
                        stats['goals_in_overtime_against'] += 1
                    if is_powerplay(event['time_in_s']):
                        stats['goals_against_in_powerplay']+=1
                        event['goal_against_powerplay'] = 1
                    if is_boxplay(event['time_in_s']):
                        if event['time_in_s'] - penalties_for[0] <= 120:
                            stats['goals_against_in_boxplay'] += 1
                            penalties_for.pop(0) # remove penalty
                            event['is_boxplay_goal_against'] = 1
                    else:
                        stats['goals_not_in_boxplay'] += 1

                    if event['home_goals'] - event['guest_goals'] == 1:
                        stats['leading_goals_against'] += 1

                    if event['home_goals'] - event['guest_goals'] == 0:
                        stats['equalizer_goals_against'] += 1

                    if (event['home_goals'] == 1 and event['guest_goals'] == 0) or (event['home_goals'] == 0 and event['guest_goals'] == 1):
                        stats['first_goal_of_match_against'] +=1

                    if event['event_team'] != event['home_team_name']:
                        stats['goals_against_home'] += 1
                    else:
                        stats['goals_against_away'] += 1

                # boxplay
                if event['event_type'] == EVENT_PENALTY and event['event_team'] == team:
                    penalty_type = event['penalty_type']
                    if penalty_type == 'penalty_2':
                        stats['penalty_2'] += 1
                    elif penalty_type == 'penalty_2and2':
                        stats['penalty_2and2'] += 1
                    elif penalty_type == 'penalty_10':
                        stats['penalty_10'] += 1
                    elif penalty_type == 'penalty_ms_full' or penalty_type == 'penalty_ms_tech':
                        stats['penalty_ms'] += 1
                    penalties_for = add_penalties(event['penalty_type'], penalties_for, event['time_in_s'])
                    stats['boxplay'] += 1
                    if event['period'] == 1:
                        stats['boxplay_first_period'] += 1
                    elif event['period'] == 2:
                        stats['boxplay_second_period'] += 1
                    elif event['period'] == 3:
                        stats['boxplay_third_period'] += 1
                    elif event['period'] == 4:
                        stats['boxplay_overtime'] += 1
                # powerplay
                if event['event_type'] == EVENT_PENALTY and event['event_team'] != team:
                    penalties_against = add_penalties(event['penalty_type'], penalties_against, event['time_in_s'])
                    stats['powerplay'] += 1
                    if event['period'] == 1:
                        stats['powerplay_first_period'] += 1
                    elif event['period'] == 2:
                        stats['powerplay_second_period'] += 1
                    elif event['period'] == 3:
                        stats['powerplay_third_period'] += 1
                    elif event['period'] == 4:
                        stats['powerplay_overtime'] += 1
                prev_period = event['period']
                if event['event_type'] == EVENT_GOAL:
                    last_goal_event = event
                    goal_differences_in_game.append(abs(event['home_goals'] - event['guest_goals']))
                enriched_events.append(event)
        # Point calculations
        point_event = game_events[game_events['event_type'] == EVENT_GOAL].iloc[-1]
        points, result, diff = add_points(team, point_event)
        stats['points'] += points
        stats[result] += 1
        opponent = point_event['away_team_name'] if point_event['home_team_name'] == team else point_event['home_team_name']
        stats['points_against'][opponent] += points
        if point_event['home_team_name'] == team:
            stats['home_points'] += points
        else:
            stats['away_points'] += points

        if diff == 1:
            stats['win_1'] += 1
        elif diff == -1:
            stats['loss_1'] += 1
        if max(goal_differences_in_game) < 3:
            points = add_points(team, point_event)[0]
            stats['points_max_difference_3'] += points
            if points == 3:
                stats['close_game_win'] += 1
            elif points == 0:
                stats['close_game_loss'] += 1
            else:
                stats['close_game_overtime'] += 1
        else:
            stats['points_more_3_difference'] += add_points(team, point_event)[0]
            goal_differences_in_game = []
        logs_after_game['game'] = stats['games']
        logs_after_game['team'] = team
        logs_after_game['points'] = stats['points']
        logs_after_game['goal_difference'] = stats['goals'] - stats['goals_against']
        logs_after_game['goals'] = stats['goals']
        all_logs_after_game.append(logs_after_game)

    # calculated stats
    stats['goals_per_game'] = safe_div(stats['goals'], stats['games'],2)
    stats['goals_against_per_game'] = safe_div(stats['goals_against'] ,stats['games'], 2)
    stats['boxplay_per_game'] = safe_div(stats['boxplay'], stats['games'],2)
    stats['powerplay_per_game'] = safe_div(stats['powerplay'],stats['games'],2)

    stats['powerplay_efficiency'] = safe_div(stats['goals_in_powerplay'],stats['powerplay'], 4, True, "n.a.")
    stats['boxplay_efficiency'] =safe_div(stats['goals_against_in_boxplay'],stats['boxplay'], 4, True, "n.a.")
    if type(stats['boxplay_efficiency']) != str:
        stats['boxplay_efficiency'] = 100 - stats['boxplay_efficiency']
    stats['percent_goals_first_period'] = safe_div(stats['goals_in_first_period'], stats['goals'], 4, True, "n.a.")
    stats['percent_goals_second_period'] = safe_div(stats['goals_in_second_period'], stats['goals'], 4, True, "n.a.")
    stats['percent_goals_third_period'] = safe_div(stats['goals_in_third_period'], stats['goals'], 4, True, "n.a.")
    stats['percent_goals_overtime'] = safe_div(stats['goals_in_overtime'], stats['goals'], 4, True, "n.a.")
    stats['percent_goals_first_period_against'] = safe_div(stats['goals_in_first_period_against'], stats['goals_against'], 4, True, "n.a.")
    stats['percent_goals_second_period_against'] = safe_div(stats['goals_in_second_period_against'], stats['goals_against'], 4, True, "n.a.")
    stats['percent_goals_third_period_against'] = safe_div(stats['goals_in_third_period_against'], stats['goals_against'], 4, True, "n.a.")
    stats['percent_goals_overtime_against'] = safe_div(stats['goals_in_overtime_against'], stats['goals_against'], 4, True, "n.a.")
    stats['points_per_game'] = safe_div(stats['points'], stats['games'])
    stats['goal_difference'] = stats['goals'] - stats['goals_against']
    stats['goal_difference_per_game'] = safe_div(stats['goal_difference'], stats['games'])

    stats['scoring_ratio'] = safe_div(stats['goals'], stats['goals_against'])

    pd.DataFrame(enriched_events).to_csv(args.output_path)
    all.append(stats)

rankings_gameday = calculate_rank_after_gamedays(all_logs_after_game)
create_visualization_rankings(rankings_gameday, OUTPUT_FOLDER)

all = sorted(all, key=lambda x: (-x['points'], -x['goal_difference']))

for index, stats in enumerate(all):
    stats['rank'] = index + 1
    if stats['rank'] <= 8:
        stats['is_playoffs'] = True
        playoff_stats.append(stats)
        if stats['rank'] <= 4:
            top4_team_stats.append(stats)
    elif stats['rank'] > 8:
        playdown_stats.append(stats)
        stats['is_playoffs'] = False
    average_stats.append(stats)
    md = dict_to_markdown(stats)
    filename = generate_slug(stats['team'])

    with open(OUTPUT_FOLDER + filename + '.md', 'w') as f:
        f.write(md)


pd.DataFrame(average_stats).to_csv('data/processed_stats.csv')

for filename, aggregated_stats in [('playoffs', playoff_stats), ('playdowns', playdown_stats), ('ligaschnitt',average_stats), ('top_4_teams', top4_team_stats)]:
    # calculate average stats over all items in the list for each respective key
    if args.is_playoffs and filename in ['playdowns', 'top_4_teams']:
        break
    stats = {}
    for key in aggregated_stats[0].keys():
        if key in ['team', 'points_against']:
            continue
        else:
            s = 0
            for agg in aggregated_stats:
                if type(agg[key]) != str:
                    s += float(agg[key])
            stats[key] = round(s / len(aggregated_stats), 2)

    stats['team'] = filename.capitalize()
    md = dict_to_markdown(stats)

    with open(OUTPUT_FOLDER_LIGA + filename + '.md', 'w') as f:
        f.write(md)