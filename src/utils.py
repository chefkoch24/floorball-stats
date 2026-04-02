from datetime import datetime
import re

import pandas as pd
import numpy as np
from unidecode import unidecode


from typing import Union, Optional

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
    period = int(event.get('period', 0))
    is_extra_time = period >= 4
    if event[team_final] > event[opponent_final]:
        if is_extra_time:
            return 2, 'over_time_wins', event[team_final] - event[opponent_final]
        else:
            return 3, 'wins', event[team_final] - event[opponent_final]
    elif event[team_final] == event[opponent_final]:
        return 1, 'draws', event[team_final] - event[opponent_final]
    elif event[team_final] < event[opponent_final]:
        if is_extra_time:
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

def safe_div(numerator, denominator,  rounding=2, in_percent= False, default: Union[float, str] = 0.0):
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
    filename = normalize_slug_fragment(name)
    return filename + f'-{year}-{time_of_year}'


def normalize_slug_fragment(value: str) -> str:
    value = unidecode(value).lower()
    value = value.replace('&', ' and ')
    value = re.sub(r'[^a-z0-9]+', '-', value)
    value = re.sub(r'-+', '-', value).strip('-')
    return value


def flatten_team_stats(stats_dict, prefix):
    """Flacht die Team-Stats mit dem gegebenen Präfix"""
    def _normalize_key(key: str) -> str:
        key = unidecode(key)
        key = key.replace(' ', '_').lower()
        key = re.sub(r'[^a-z0-9_]', '_', key)
        key = re.sub(r'_+', '_', key).strip('_')
        return key

    flattened = {}
    for key, value in stats_dict.items():
        if isinstance(value, dict):
            # Für verschachtelte Dicts wie 'points_against'
            for nested_key, nested_value in value.items():
                flattened[f"{prefix}_{key}_{_normalize_key(nested_key)}"] = nested_value
        else:
            flattened[f"{prefix}_{key}"] = value
    return flattened


def _iter_stable_items(mapping: dict):
    for key in sorted(mapping):
        yield key, mapping[key]


def dict_to_markdown_game_stats(game_data: dict, title: str, season: str, phase: str, metadata_date: Optional[str] = None):
    """Generiert Markdown mit geflatteten Team-Stats"""
    result = []
    category = "game"
    result.append(f"Date: {game_data.get('date') or metadata_date or datetime.now().strftime('%Y-%m-%d')}")
    title = title.replace('_', ' ')
    result.append(f"Title: {title}")
    result.append(f"Category: {season}-{phase}, {category}")
    result.append(f"Slug: {normalize_slug_fragment(f'{title}-{season}-{phase}')}")
    result.append(f"type: game")
    result.append(f"game_id: {game_data['game_id']}")

    # Team Namen
    result.append(f"home_team: {game_data['home_team']}")
    result.append(f"away_team: {game_data['away_team']}")

    excluded_keys = {"game_id", "date", "home_team", "away_team", "home_stats", "away_stats", "title", "slug", "category", "type"}
    for key, value in _iter_stable_items(game_data):
        if key in excluded_keys:
            continue
        if isinstance(value, (str, int, float)) or value is None:
            result.append(f"{key}: {value}")

    # Flat Home Stats
    home_stats = flatten_team_stats(game_data["home_stats"], "home")
    for key, value in _iter_stable_items(home_stats):
        result.append(f"{key}: {value}")

    # Flat Home Pregame Stats
    if "home_pregame_stats" in game_data:
        home_pre_stats = flatten_team_stats(game_data["home_pregame_stats"], "home_pregame")
        for key, value in _iter_stable_items(home_pre_stats):
            result.append(f"{key}: {value}")

    # Flat Away Stats
    away_stats = flatten_team_stats(game_data["away_stats"], "away")
    for key, value in _iter_stable_items(away_stats):
        result.append(f"{key}: {value}")

    # Flat Away Pregame Stats
    if "away_pregame_stats" in game_data:
        away_pre_stats = flatten_team_stats(game_data["away_pregame_stats"], "away_pregame")
        for key, value in _iter_stable_items(away_pre_stats):
            result.append(f"{key}: {value}")

    return "\n".join(result)



def dict_to_markdown_team_stats(
    stats: dict,
    team: str,
    season: str,
    phase: str,
    metadata_date: Optional[str] = None,
):
    """Generiert Markdown mit geflatteten Team-Stats"""
    result = []
    category = "teams"
    result.append(f"Date: {metadata_date or datetime.now().strftime('%Y-%m-%d')}")
    result.append(f"Title: {team}")
    result.append(f"Category: {season}-{phase}, {category}")
    slug = generate_slug(team, season, phase)
    result.append(f"Slug: {slug.lower().replace(' ', '_')}-{season}-{phase}")
    result.append(f"type: team")
    result.append(f"team:{team}")
    result.append("platzierungsverlauf:" + f"{season}-{phase}/teams/" + f"{slug}_platzierungsverlauf.png")

    for key, value in _iter_stable_items(stats):
        if key != 'points_against':
            result.append(f"{key}: {value}")
        else:
            markdown = f"Tags:"
            for k, v in _iter_stable_items(value):
                markdown += f"  {k}: {v},"
            result.append(markdown)
    return '\n'.join(result)


def dict_to_markdown_league_stats(
    stats: dict,
    title: str,
    season: str,
    phase: str,
    metadata_date: Optional[str] = None,
):
    result = []
    category = "liga"
    result.append(f"Date: {metadata_date or datetime.now().strftime('%Y-%m-%d')}")
    result.append(f"Title: {title}")
    result.append(f"Category: {season}-{phase}, {category}")
    slug = normalize_slug_fragment(f"{title}-{season}-{phase}")
    result.append(f"Slug: {slug}")
    result.append(f"type: liga")
    result.append(f"team: {title}")

    for key, value in _iter_stable_items(stats):
        result.append(f"{key}: {value}")
    return '\n'.join(result)
