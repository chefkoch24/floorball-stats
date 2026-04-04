import pandas as pd
from typing import Callable, Dict, Any, List, Optional, Set

from src.utils import transform_in_seconds
from src.team_stats import TeamStats


class StatsEngine:
    def __init__(self):
        self.stat_functions: Dict[str, Callable[[pd.DataFrame, str], Any]] = {}

    def register_stat(self, name: str, func: Callable[[pd.DataFrame, str], Any]):
        self.stat_functions[name] = func

    def calculate_team_stats(self, df: pd.DataFrame, team: str) -> TeamStats:
        team_stats = TeamStats(team)
        team_events = transform_in_seconds(df)  # Zeit umwandeln
        for stat_name, func in self.stat_functions.items():
            team_stats.stats[stat_name] = func(team_events, team)
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

    def split_by_rank(
        self,
        all_stats: List[TeamStats],
        playoff_cut: int = 8,
        top4_cut: int = 4,
        playoff_eligible_teams: Optional[Set[str]] = None,
    ):
        sorted_stats = sorted(all_stats, key=lambda x: (-x.stats.get('points', 0), -x.stats.get('goal_difference', 0)))

        if playoff_eligible_teams:
            playoff_stats = [team for team in sorted_stats if team.team in playoff_eligible_teams]
            playdown_stats = [team for team in sorted_stats if team.team not in playoff_eligible_teams]
        else:
            playoff_stats = sorted_stats[:playoff_cut]
            playdown_stats = sorted_stats[playoff_cut:]

        top4_stats = playoff_stats[:top4_cut]
        return playoff_stats, playdown_stats, top4_stats
