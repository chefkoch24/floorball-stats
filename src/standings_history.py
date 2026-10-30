"""Table position of every team after each round of a regular season.

The sources publish no round numbers, so a round is a block of game days: a new
round starts when a game day is more than ``ROUND_GAP_DAYS`` after the first day
of the current round (Friday to Sunday stays one round, Wednesday and Saturday
are two). After every round the table is rebuilt from the results with points,
goal difference and goals scored, then the team name. Leagues that rank ties by
head-to-head results can differ from the official table on such ties during the
season; the last round always takes the official ranks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Sequence

ROUND_GAP_DAYS = 2


@dataclass(frozen=True)
class PlayedGame:
    day: date
    home: str
    away: str
    home_goals: int
    away_goals: int
    home_points: int
    away_points: int


@dataclass
class Round:
    number: int
    first_day: date
    last_day: date


@dataclass
class StandingsHistory:
    rounds: list[Round] = field(default_factory=list)
    # team -> table position after each round (1 = top)
    positions: dict[str, list[int]] = field(default_factory=dict)

    def best(self, team: str) -> int | None:
        return min(self.positions[team]) if self.positions.get(team) else None

    def worst(self, team: str) -> int | None:
        return max(self.positions[team]) if self.positions.get(team) else None


def group_rounds(days: Iterable[date]) -> list[Round]:
    rounds: list[Round] = []
    for day in sorted(set(days)):
        if rounds and (day - rounds[-1].first_day).days <= ROUND_GAP_DAYS:
            rounds[-1].last_day = day
        else:
            rounds.append(Round(number=len(rounds) + 1, first_day=day, last_day=day))
    return rounds


def standings_history(
    games: Sequence[PlayedGame],
    teams: Iterable[str],
    official_ranks: dict[str, int] | None = None,
) -> StandingsHistory:
    team_list = sorted(set(teams) | {game.home for game in games} | {game.away for game in games})
    rounds = group_rounds(game.day for game in games)
    history = StandingsHistory(rounds=rounds, positions={team: [] for team in team_list})
    if not rounds:
        return history

    table = {team: [0, 0, 0] for team in team_list}  # points, goal difference, goals
    ordered = sorted(games, key=lambda game: game.day)
    cursor = 0
    for round_ in rounds:
        while cursor < len(ordered) and ordered[cursor].day <= round_.last_day:
            game = ordered[cursor]
            for team, points, scored, conceded in (
                (game.home, game.home_points, game.home_goals, game.away_goals),
                (game.away, game.away_points, game.away_goals, game.home_goals),
            ):
                row = table[team]
                row[0] += points
                row[1] += scored - conceded
                row[2] += scored
            cursor += 1
        ranking = sorted(team_list, key=lambda team: (-table[team][0], -table[team][1], -table[team][2], team))
        if round_ is rounds[-1] and official_ranks and set(official_ranks) >= set(team_list):
            ranking = sorted(team_list, key=lambda team: (official_ranks[team], team))
        for position, team in enumerate(ranking, start=1):
            history.positions[team].append(position)
    return history
