from datetime import datetime
import pandas as pd
import numpy as np


def dict_to_markdown(dictionary):
    markdown = ""
    # add meta data
    date = datetime.now().strftime('%Y-%m-%d')
    markdown += "Date: " + date + "\n"
    markdown += f"Title: {stats['team']}\n"
    markdown += f"Slug: {generate_slug(dictionary['team'])}\n"
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
    return filename

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
        'points_after_55_min': 0,
        'win_1':0,
        'loss_1':0,
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
    if len(penalties_for_us) > len(penalties_opponent):
        if time - penalties_for_us[0] <= 120:
            return True
        else:
            return False
    else:
        return False

def is_powerplay(time):
    if len(penalties_for_us) < len(penalties_opponent):
        if time - penalties_opponent[0] <= 120:
            return True
        else:
            return False
    else:
        return False

def add_penalties(penalty_type, penalties, time):
    if penalty_type == 'penalty_2' or penalty_type == 'penalty_10':
        penalties.append(time)
    elif penalty_type == 'penalty_2and2' or penalty_type == 'penalty_ms_full':
        penalties.append(time)
        penalties.append(time)
    return penalties

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
        return 1, 'draws' , event[team_final]- event[opponent_final]
    elif event[team_final] < event[opponent_final]:
        if event['period'] == 4:
            return 1, 'over_time_losses', event[team_final] - event[opponent_final]
        else:
            return 0, 'losses',  event[team_final] - event[opponent_final]
    else:
        return 0, 'losses',  event[team_final]- event[opponent_final]



data = pd.read_csv('data/goals_team.csv')
teams = ['MFBC Leipzig', 'DJK Holzbüttgen', 'UHC Sparkasse Weißenfels', 'ETV Piranhhas Hamburg', 'Berlin Rockets',  'TV Schriesheim', 'VfL Red Hocks Kaufering', 'Floor Fighters Chemnitz', 'SSF Dragons Bonn', 'Red Devils Wernigerode', 'Unihockey Igels Dresden', 'Blau-Weiß 96 Schenefeld']
playoff_teams = teams[:9]
playdown_teams = teams[9:]
teams = playoff_teams + playdown_teams
top4_teams = playoff_teams[:4]
print()
EVENT_GOAL = 'goal'
EVENT_PENALTY = 'penalty'
OUTPUT_FOLDER = 'content/teams/'
OUTPUT_FOLDER_LIGA = 'content/liga/'

playoff_stats = []
playdown_stats = []
average_stats = []
top4_team_stats = []

for rank, team in enumerate(teams):
    stats = initalize_stats(team, teams)
    stats['rank'] = rank+1

    events_from_team = data[(data['home_team_name'] == team) | (data['away_team_name'] == team)]
    events_from_team = transform_in_seconds(events_from_team)

    enriched_events = []

    all_stats = []
    prev_period = 100
    last_goal_event = None
    prev_game_id = None
    index = 0
    for i, event in events_from_team.iterrows():
            index += 1

            # reset for new game
            if prev_game_id != event['game_id'] or prev_game_id is None:
                penalties_for_us = []
                penalties_opponent = []
                stats['games'] += 1
                is_crunchtime = True

            # intermediate points after period
            if prev_period < event['period']:
                if event['period'] == 2:
                    stats['points_after_first_period'] += add_points(team, event)[0]
                elif event['period'] == 3:
                    stats['points_after_second_period'] += add_points(team, event)[0]

            if (event['time_in_s'] >= 55 * 60 or (prev_game_id != event['game_id'] and prev_game_id is not None)) and is_crunchtime:
                stats['points_after_55_min'] += add_points(team, last_goal_event)[0]
                is_crunchtime = False

            # check if penalties are over
            if len(penalties_for_us) > 0:
                if event['time_in_s'] - penalties_for_us[0] >= 120:
                    penalties_for_us.pop(0)
            if len(penalties_opponent) > 0:
                if event['time_in_s'] - penalties_opponent[0] >= 120:
                    penalties_opponent.pop(0)
            # our goals
            if event['event_type'] == EVENT_GOAL and event['event_team'] == team:
                stats['goals'] += 1
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
                    if event['time_in_s'] - penalties_opponent[0] <= 120:
                        stats['goals_in_powerplay'] += 1
                        penalties_opponent.pop(0) # remove penalty
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
                    if event['time_in_s'] - penalties_for_us[0] <= 120:
                        stats['goals_against_in_boxplay'] += 1
                        penalties_for_us.pop(0) # remove penalty
                        event['is_boxplay_goal_against'] = 1
                else:
                    stats['goals_not_in_boxplay'] += 1

                if event['home_goals'] - event['guest_goals'] == 1:
                    stats['leading_goals_against'] += 1

                if event['home_goals'] - event['guest_goals'] == 0:
                    stats['equalizer_goals_against'] += 1

                if (event['home_goals'] == 1 and event['guest_goals'] == 0) or (event['home_goals'] == 0 and event['guest_goals'] == 1):
                    stats['first_goal_of_match_against'] +=1

                if event['event_team'] == event['home_team_name']:
                    stats['goals_against_home'] += 1
                else:
                    stats['goals_against_away'] += 1

            # boxplay
            if event['event_type'] == EVENT_PENALTY and event['event_team'] == team:
                penalties_for_us = add_penalties(event['penalty_type'], penalties_for_us, event['time_in_s'])
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
                penalties_opponent = add_penalties(event['penalty_type'], penalties_opponent, event['time_in_s'])
                stats['powerplay'] += 1
                if event['period'] == 1:
                    stats['powerplay_first_period'] += 1
                elif event['period'] == 2:
                    stats['powerplay_second_period'] += 1
                elif event['period'] == 3:
                    stats['powerplay_third_period'] += 1
                elif event['period'] == 4:
                    stats['powerplay_overtime'] += 1

            # points
            if prev_game_id is not None:
                if event['game_id'] != prev_game_id or index == len(events_from_team):
                    points, result, diff = add_points(team, last_goal_event)
                    stats['points'] += points
                    stats[result] += 1
                    opponent = last_goal_event['away_team_name'] if last_goal_event['home_team_name'] == team else last_goal_event['home_team_name']
                    stats['points_against'][opponent] += points
                    if last_goal_event['home_team_name'] == team:
                        stats['home_points'] += points
                    else:
                        stats['away_points'] += points

                    if diff == 1:
                        stats['win_1'] += 1
                    elif diff == -1:
                        stats['loss_1'] += 1

            prev_game_id = event['game_id']
            prev_period = event['period']
            if event['event_type'] == EVENT_GOAL:
                last_goal_event = event
            enriched_events.append(event)

    # calculated stats
    stats['goals_per_game'] = round(stats['goals'] / stats['games'],2)
    stats['goals_against_per_game'] = round(stats['goals_against'] / stats['games'], 2)
    stats['boxplay_per_game'] = round(stats['boxplay'] / stats['games'],2)
    stats['powerplay_per_game'] = round(stats['powerplay'] / stats['games'],2)

    stats['powerplay_efficiency'] = round(stats['goals_in_powerplay'] / stats['powerplay'], 4)*100
    stats['boxplay_efficiency'] = round(1 - (stats['goals_against_in_boxplay'] / stats['boxplay']), 4)*100
    stats['percent_goals_first_period'] = round(stats['goals_in_first_period'] / stats['goals'], 4)*100
    stats['percent_goals_second_period'] = round(stats['goals_in_second_period'] / stats['goals'], 4)*100
    stats['percent_goals_third_period'] = round(stats['goals_in_third_period'] / stats['goals'], 4)*100
    stats['percent_goals_overtime'] = round(stats['goals_in_overtime'] / stats['goals'], 4)*100
    stats['percent_goals_first_period_against'] = round(stats['goals_in_first_period_against'] / stats['goals_against'], 4)*100
    stats['percent_goals_second_period_against'] = round(stats['goals_in_second_period_against'] / stats['goals_against'], 4)*100
    stats['percent_goals_third_period_against'] = round(stats['goals_in_third_period_against'] / stats['goals_against'], 4)*100
    stats['percent_goals_overtime_against'] = round(stats['goals_in_overtime_against'] / stats['goals_against'], 4)*100
    stats['points_per_game'] = round(stats['points'] / stats['games'], 2)


    #pd.DataFrame(enriched_events).to_csv('enriched_events.csv')
    md = dict_to_markdown(stats)
    filename = generate_slug(stats['team'])

    with open(OUTPUT_FOLDER + filename + '.md', 'w') as f:
        f.write(md)

    if team in playoff_teams:
        playoff_stats.append(stats)
        if team in top4_teams:
            top4_team_stats.append(stats)
    elif team in playdown_teams:
        playdown_stats.append(stats)
    average_stats.append(stats)

for filename, aggregated_stats in [('playoffs', playoff_stats), ('playdowns', playdown_stats), ('ligaschnitt',average_stats), ('top_4_teams', top4_team_stats)]:
    # calculate average stats over all items in the list for each respective key
    stats = {}
    for key in aggregated_stats[0].keys():
        if key in ['team', 'points_against']:
            continue
        else:
            s = 0
            for agg in aggregated_stats:
                s += float(agg[key])
            stats[key] = round(s / len(aggregated_stats), 2)

    stats['team'] = filename.capitalize()
    md = dict_to_markdown(stats)

    with open(OUTPUT_FOLDER_LIGA + filename + '.md', 'w') as f:
        f.write(md)