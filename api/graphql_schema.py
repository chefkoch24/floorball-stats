from typing import Dict

import strawberry
from strawberry.types import Info

from api import crud


@strawberry.type
class League:
    league_id: strawberry.ID
    year: str
    league_name: str
    team: list['Team']

@strawberry.type
class Team:
    team_id: strawberry.ID
    team_name: str
    league: League

@strawberry.type
class Stats:
    stats_id: strawberry.ID
    goals: int
    goals_in_first_period: int
    goals_in_second_period: int
    goals_in_third_period: int
    goals_in_overtime: int
    goals_in_boxplay: int
    goals_in_powerplay: int
    leading_goals: int
    equalizer_goals: int
    first_goal_of_match: int
    goals_against: int
    leading_goals_against: int
    equalizer_goals_against: int
    first_goal_of_match_against: int
    goals_in_first_period_against: int
    goals_in_second_period_against: int
    goals_in_third_period_against: int
    goals_in_overtime_against: int
    goals_against_in_boxplay: int
    goals_against_in_powerplay: int
    goals_not_in_boxplay: int
    boxplay: int
    powerplay: int
    boxplay_first_period: int
    boxplay_second_period: int
    boxplay_third_period: int
    boxplay_overtime: int
    powerplay_first_period: int
    powerplay_second_period: int
    powerplay_third_period: int
    powerplay_overtime: int
    games: int
    games_home: int
    games_away: int
    goals_home: int
    goals_away: int
    goals_against_home: int
    goals_against_away: int
    points: int
    home_points: int
    away_points: int
    wins: int
    over_time_wins: int
    losses: int
    over_time_losses: int
    draws: int
    #points_against: Dict
    points_after_first_period: int
    points_after_second_period: int
    points_after_third_period: int
    points_after_55_min: int
    points_after_58_min: int
    points_after_59_min: int
    win_1: int
    loss_1: int
    points_max_difference_3: int
    points_more_3_difference: int
    close_game_win: int
    close_game_loss: int
    close_game_overtime: int
    penalty_shot_goals: int
    penalty_shot_goals_against: int
    penalty_2: int
    penalty_2and2: int
    penalty_10: int
    penalty_ms: int
    goals_per_game: float
    goals_against_per_game: float
    boxplay_per_game: float
    powerplay_per_game: float
    powerplay_efficiency: float
    boxplay_efficiency: float
    percent_goals_first_period: float
    percent_goals_second_period: float
    percent_goals_third_period: float
    percent_goals_overtime: float
    percent_goals_in_boxplay: float
    percent_goals_in_powerplay: float
    percent_goals_first_period_against: float
    percent_goals_second_period_against: float
    percent_goals_third_period_against: float
    percent_goals_overtime_against: float
    points_per_game: float
    goal_difference: float
    goal_difference_per_game: float
    scoring_ratio: float
    is_playoffs: bool
    rank: int
    team: Team



@strawberry.type
class Query:
    @strawberry.field
    def leagues(self, info: Info) -> list[League]:
        return crud.get_leagues(info.context['db'])

    @strawberry.field
    def league_by_id(self, info: Info, league_id: int, ) -> League:
        return crud.get_leagues_by_id(info.context['db'],league_id)

    @strawberry.field
    def stats(self, info: Info) -> list[Stats]:
        return crud.get_stats(info.context['db'])

    @strawberry.field
    def stats_by_id(self, info: Info, stats_id: int) -> Stats:
        return crud.get_stats_by_id(info.context['db'],stats_id)

    @strawberry.field
    def teams(self,info: Info) -> list[Team]:
        return crud.get_teams(info.context['db'])

    @strawberry.field
    def team_by_id(self, info: Info, team_id: int) -> Team:
        return crud.get_teams_by_id(info.context['db'],team_id)

