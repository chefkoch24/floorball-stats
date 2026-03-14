"""
Modulares Framework zur flexiblen Berechnung und Aggregation von Floorball-Statistiken.
Vergleichbar mit der Logik aus generate_content.py.
"""
import numpy as np
import pandas as pd
from typing import Callable, Dict, List, Any

from src.utils import read_data


class TeamStats:
    def __init__(self, team_name: str, teams: List[str]):
        self.team_name = team_name
        self.stats: Dict[str, Any] = self.initalize_stats(teams)

    def initalize_stats(self, teams):
        return {
            'team': self.team_name,
            'goals': 0,
            'goals_against': 0,
            'games': 0,
            'points': 0,
            'wins': 0,
            'over_time_wins': 0,
            'losses': 0,
            'over_time_losses': 0,
            'draws': 0,
            'points_against': {t: 0 for t in teams if t != self.team_name},
            # weitere Stats nach Bedarf...
        }

class FloorballStatsEngine:
    def __init__(self):
        self.stat_functions: Dict[str, Callable[[pd.DataFrame, TeamStats], Any]] = {}

    def register_stat(self, name: str, func: Callable[[pd.DataFrame, TeamStats], Any]):
        self.stat_functions[name] = func

    def calculate_team_stats(self, events: pd.DataFrame, team: str, teams: List[str]) -> TeamStats:
        team_stats = TeamStats(team, teams)
        # Filter Events für das Team
        team_events = events[(events['home_team_name'] == team) | (events['away_team_name'] == team)]
        team_stats.stats['games'] = team_events['game_id'].nunique()
        # Basis-Stats mit DataFrame-Operationen
        team_stats.stats['goals'] = team_events[(team_events['event_type'] == EVENT_GOAL) & (team_events['event_team'] == team)].shape[0]
        team_stats.stats['goals_against'] = team_events[(team_events['event_type'] == 'goal') & (team_events['event_team'] != team)].shape[0]
        # Berechne alle registrierten Statistiken
        for stat_name, func in self.stat_functions.items():
            team_stats.stats[stat_name] = func(team_events, team_stats)
        return team_stats

    def aggregate_stats(self, team_stats_list: List[TeamStats]) -> Dict[str, Any]:
        if not team_stats_list:
            return {}
        result = {}
        stat_keys = set()
        for ts in team_stats_list:
            stat_keys.update(ts.stats.keys())
        for key in stat_keys:
            values = [ts.stats[key] for ts in team_stats_list if key in ts.stats and isinstance(ts.stats[key], (int, float))]
            if values:
                result[key] = round(sum(values) / len(values), 2)
        return result

    def split_by_rank(self, all_stats: List[TeamStats], playoff_cut: int = 8, top4_cut: int = 4):
        # Sortiere analog zu generate_content.py
        sorted_stats = sorted(all_stats, key=lambda x: (-x.stats['points'], -x.stats.get('goal_difference', 0)))
        playoff_stats = sorted_stats[:playoff_cut]
        playdown_stats = sorted_stats[playoff_cut:]
        top4_stats = sorted_stats[:top4_cut]
        return playoff_stats, playdown_stats, top4_stats

# Beispiel für Stat-Funktionen

def stat_goals_per_game(team_events: pd.DataFrame, team_stats: TeamStats):
    games = team_stats.stats.get('games', 1)
    return round(team_stats.stats.get('goals', 0) / games, 2) if games else 0

def stat_goals_against_per_game(team_events: pd.DataFrame, team_stats: TeamStats):
    games = team_stats.stats.get('games', 1)
    return round(team_stats.stats.get('goals_against', 0) / games, 2) if games else 0




# Beispiel für die Nutzung
if __name__ == "__main__":
    df = read_data("../data/data_regular_season.csv")
    teams = list(df['home_team_name'].unique()) + list(df['away_team_name'].unique())
    teams = np.unique(teams)
    engine = FloorballStatsEngine()
    engine.register_stat('goals_per_game', stat_goals_per_game)
    engine.register_stat('goals_against_per_game', stat_goals_against_per_game)
    all_stats = [engine.calculate_team_stats(df, team, teams) for team in teams]
    playoff_stats, playdown_stats, top4_stats = engine.split_by_rank(all_stats)
    print('Playoff Stats:', [t.stats for t in playoff_stats])
    print('Playdown Stats:', [t.stats for t in playdown_stats])
    print('Top4 Stats:', [t.stats for t in top4_stats])
print('League Average:', engine.aggregate_stats(all_stats))
