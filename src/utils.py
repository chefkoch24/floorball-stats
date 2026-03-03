from datetime import datetime

import pandas as pd
import numpy as np


def read_data(path):
    return pd.read_csv(path)

def transform_in_seconds(data):
    times = []
    for d in data['sortkey']:
        period, time = d.split('-')
        min, sec = time.split(':')
        time_in_s = (int(period)-1) * 20 * 60 + int(min) * 60 + int(sec)
        times.append(time_in_s)
    data = data.copy()  # Kopie erstellen, um Warnung zu vermeiden
    data.loc[:, 'time_in_s'] = times
    return data

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

def is_boxplay(time: int, penalties_for: list, penalties_against: list):
    if len(penalties_for) > len(penalties_against):
        if time - penalties_for[0] <= 120:
            return True
        else:
            return False
    else:
        return False

def is_powerplay(time, penalties_for: list, penalties_against: list):
    if len(penalties_for) < len(penalties_against):
        if time - penalties_against[0] <= 120:
            return True
        else:
            return False
    else:
        return False

def add_penalties(penalty_type: str, penalties: list, time: int):
    if penalty_type == 'penalty_2' or penalty_type == 'penalty_10':
        penalties.append(time)
    elif penalty_type == 'penalty_2and2' or penalty_type == 'penalty_ms_full' or penalty_type == 'penalty_ms_tech':
        penalties.append(time)
        penalties.append(time)
    return penalties

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

def generate_slug(name: str, year:str, time_of_year: str) -> str:
    filename = name.replace(' ', '-').lower()
    filename = filename.replace('ö', 'oe')
    filename = filename.replace('ä', 'ae')
    filename = filename.replace('ü', 'ue')
    filename = filename.replace('ß', 'ss')
    return filename + f'-{year}-{time_of_year}'


def flatten_team_stats(stats_dict, prefix):
    """Flacht die Team-Stats mit dem gegebenen Präfix"""
    flattened = {}
    for key, value in stats_dict.items():
        if isinstance(value, dict):
            # Für verschachtelte Dicts wie 'points_against'
            for nested_key, nested_value in value.items():
                flattened[f"{prefix}_{key}_{nested_key.replace(' ', '_').lower()}"] = nested_value
        else:
            flattened[f"{prefix}_{key}"] = value
    return flattened


def dict_to_markdown_game_stats(game_data: dict, title: str, season: str, phase: str):
    """Generiert Markdown mit geflatteten Team-Stats"""
    result = []
    category = "game"
    result.append(f"Date: {game_data.get('date',datetime.now().strftime('%Y-%m-%d'))}")
    title = title.replace('_', ' ')
    result.append(f"Title: {title}")
    result.append(f"Category: {season}-{phase}, {category}")
    result.append(f"Slug: {title.lower().replace(' ', '-')}")
    result.append(f"type: game")
    result.append(f"game_id: {game_data['game_id']}")

    # Team Namen
    result.append(f"home_team: {game_data['home_team']}")
    result.append(f"away_team: {game_data['away_team']}")

    # Flat Home Stats
    home_stats = flatten_team_stats(game_data['home_stats'], 'home')
    for key, value in home_stats.items():
        result.append(f"{key}: {value}")

    # Flat Away Stats
    away_stats = flatten_team_stats(game_data['away_stats'], 'away')
    for key, value in away_stats.items():
        result.append(f"{key}: {value}")

    return '\n'.join(result)



def dict_to_markdown_team_stats(stats: dict, team: str, season: str, phase: str):
    """Generiert Markdown mit geflatteten Team-Stats"""
    result = []
    category = "teams"
    result.append(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    result.append(f"Title: {team}")
    result.append(f"Category: {season}-{phase}, {category}")
    slug = generate_slug(team, season, phase)
    result.append(f"Slug: {slug.lower().replace(' ', '_')}-{season}-{phase}")
    result.append(f"type: team")
    result.append(f"team:{team}")
    result.append("Platzierungsverlauf:" + f"{season}-{phase}/teams/" + f"{slug}_platzierungsverlauf.png\n")

    for key, value in stats.items():
        if key != 'points_against':
            result.append(f"{key}: {value}")
        else:
            markdown = f"Tags:"
            for k, v in value.items():
                markdown += f"  {k}: {v},"
            result.append(markdown)
    return '\n'.join(result)