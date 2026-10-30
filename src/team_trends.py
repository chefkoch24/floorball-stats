"""Streaks, records, goal timing, comebacks and crowds of one season phase.

Input is the season's played games in date order, each with its goals in play
order (minute on the game clock, scoring side, scorer and assist). All counts
follow the definitions on the "How our stats work" page:

- Win streak: wins in a row, overtime and penalty-shot wins included. Losing
  streak: losses in a row, after overtime included. Unbeaten: no loss.
- Point streak (players): the team's games in a row in which the player had a
  goal or an assist. A game the player missed ends the streak, because the
  sources do not tell us who played.
- Goal timing: goals for and against in 5-minute blocks of regulation, plus
  overtime.
- Comeback win: won after being behind at some point. Blown lead: lost after
  being ahead at some point. "After two periods" is the score at 40:00.
- Crowd: average attendance of a team's home games with a published number.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from src.player_insights import PlayerRef

BLOCK_MINUTES = 5
REGULATION = 60.0


@dataclass(frozen=True)
class Goal:
    minute: float
    side: str
    scorer: PlayerRef | None = None
    assist: PlayerRef | None = None


@dataclass(frozen=True)
class Game:
    game_id: str
    url: str
    day: date
    home: str
    away: str
    home_goals: int
    away_goals: int
    extra_time: bool
    goals: tuple[Goal, ...] = ()
    attendance: int | None = None
    home_points: int | None = None
    away_points: int | None = None

    def side_of(self, team: str) -> str:
        return "home" if team == self.home else "away"

    def opponent(self, team: str) -> str:
        return self.away if team == self.home else self.home

    def score_for(self, team: str) -> tuple[int, int]:
        return (self.home_goals, self.away_goals) if team == self.home else (self.away_goals, self.home_goals)


def letter(game: Game, team: str) -> str:
    own, other = game.score_for(team)
    if own == other:
        return "D"
    if own > other:
        return "OTW" if game.extra_time else "W"
    return "OTL" if game.extra_time else "L"


def _run(letters: list[str], members: set[str]) -> int:
    count = 0
    for value in reversed(letters):
        if value not in members:
            break
        count += 1
    return count


def _longest(letters: list[str], members: set[str]) -> int:
    best = current = 0
    for value in letters:
        current = current + 1 if value in members else 0
        best = max(best, current)
    return best


WINS = {"W", "OTW"}
LOSSES = {"L", "OTL"}
UNBEATEN = {"W", "OTW", "D"}


@dataclass
class TeamStreaks:
    wins: int = 0
    losses: int = 0
    unbeaten: int = 0
    home_unbeaten: int = 0
    away_unbeaten: int = 0
    longest_wins: int = 0
    form: list[str] = field(default_factory=list)


def team_streaks(games: list[Game], team: str) -> TeamStreaks:
    own = [game for game in games if team in (game.home, game.away)]
    letters = [letter(game, team) for game in own]
    home = [letter(game, team) for game in own if game.home == team]
    away = [letter(game, team) for game in own if game.away == team]
    return TeamStreaks(
        wins=_run(letters, WINS),
        losses=_run(letters, LOSSES),
        unbeaten=_run(letters, UNBEATEN),
        home_unbeaten=_run(home, UNBEATEN),
        away_unbeaten=_run(away, UNBEATEN),
        longest_wins=_longest(letters, WINS),
        form=letters,
    )


def point_streaks(games: list[Game], team: str) -> dict[str, tuple[PlayerRef, int, int]]:
    """Player key -> (player, current point streak, current goal streak) in the team's games."""
    own = [game for game in games if team in (game.home, game.away)]
    seen: dict[str, PlayerRef] = {}
    per_game: list[tuple[set[str], set[str]]] = []
    for game in own:
        side = game.side_of(team)
        pointed: set[str] = set()
        scored: set[str] = set()
        for goal in game.goals:
            if goal.side != side:
                continue
            for player in (goal.scorer, goal.assist):
                if player:
                    seen.setdefault(player.key, player)
                    pointed.add(player.key)
            if goal.scorer:
                scored.add(goal.scorer.key)
        per_game.append((pointed, scored))
    result = {}
    for key, player in seen.items():
        points = goals = 0
        for pointed, _ in reversed(per_game):
            if key not in pointed:
                break
            points += 1
        for _, scored in reversed(per_game):
            if key not in scored:
                break
            goals += 1
        result[key] = (player, points, goals)
    return result


@dataclass
class Record:
    key: str
    label: str
    value: str
    detail: str
    url: str = ""


def _clock(minute: float) -> str:
    if minute > REGULATION:
        rest = minute - REGULATION
        return f"OT {int(rest):02d}:{round((rest % 1) * 60):02d}"
    seconds = round(minute * 60)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def season_records(games: list[Game]) -> list[Record]:
    """The season's standout single-game moments."""
    records: list[Record] = []
    with_goals = [game for game in games if game.goals]
    if with_goals:
        game, goal = min(((game, game.goals[0]) for game in with_goals), key=lambda item: (item[1].minute, item[0].day))
        team = game.home if goal.side == "home" else game.away
        who = f"{goal.scorer.name}, {team}" if goal.scorer else team
        records.append(Record("fastest-goal", "Fastest goal", _clock(goal.minute), f"{who} vs {game.opponent(team)}", game.url))

        def fastest_pair(game: Game):
            best = None
            for side in ("home", "away"):
                minutes = [goal.minute for goal in game.goals if goal.side == side and goal.minute <= REGULATION]
                for first, second in zip(minutes, minutes[1:]):
                    gap = second - first
                    if best is None or gap < best[0]:
                        best = (gap, side, second)
            return best

        pairs = [(fastest_pair(game), game) for game in with_goals]
        pairs = [(pair, game) for pair, game in pairs if pair]
        if pairs:
            (gap, side, minute), game = min(pairs, key=lambda item: (item[0][0], item[1].day))
            team = game.home if side == "home" else game.away
            records.append(Record("fastest-pair", "Two goals fastest", f"{round(gap * 60)} s", f"{team} vs {game.opponent(team)}, at {_clock(minute)}", game.url))

        def longest_run(game: Game):
            best = (0, "")
            current, side = 0, ""
            for goal in game.goals:
                current = current + 1 if goal.side == side else 1
                side = goal.side
                best = max(best, (current, side))
            return best

        (run, side), game = max(((longest_run(game), game) for game in with_goals), key=lambda item: (item[0][0], -item[1].day.toordinal()))
        team = game.home if side == "home" else game.away
        records.append(Record("longest-run", "Longest run", f"{run} goals", f"{team} in a row vs {game.opponent(team)}", game.url))

        tallies = []
        for game in with_goals:
            counts: dict[str, list] = {}
            for goal in game.goals:
                if goal.scorer:
                    team = game.home if goal.side == "home" else game.away
                    counts.setdefault(goal.scorer.key, [goal.scorer, team, 0])[2] += 1
            for player, team, count in counts.values():
                tallies.append((count, game, player, team))
        if tallies:
            count, game, player, team = max(tallies, key=lambda item: (item[0], -item[1].day.toordinal()))
            records.append(Record("most-goals-player", "Most goals by a player", f"{count} goals", f"{player.name}, {team} vs {game.opponent(team)}", game.url))

        comebacks = []
        for game in with_goals:
            if game.home_goals == game.away_goals:
                continue
            winner = "home" if game.home_goals > game.away_goals else "away"
            home = away = deficit = 0
            for goal in game.goals:
                home += goal.side == "home"
                away += goal.side == "away"
                deficit = max(deficit, (away - home) if winner == "home" else (home - away))
            comebacks.append((deficit, game, winner))
        if comebacks:
            deficit, game, winner = max(comebacks, key=lambda item: (item[0], -item[1].day.toordinal()))
            if deficit >= 2:
                team = game.home if winner == "home" else game.away
                records.append(Record("biggest-comeback", "Biggest comeback", f"{deficit} goals", f"{team} won from {deficit} down vs {game.opponent(team)}", game.url))
    if games:
        game = max(games, key=lambda game: (abs(game.home_goals - game.away_goals), -game.day.toordinal()))
        records.append(Record("biggest-win", "Biggest win", f"{game.home_goals}:{game.away_goals}", f"{game.home} vs {game.away}", game.url))
        game = max(games, key=lambda game: (game.home_goals + game.away_goals, -game.day.toordinal()))
        records.append(Record("most-goals", "Most goals in a game", str(game.home_goals + game.away_goals), f"{game.home} {game.home_goals}:{game.away_goals} {game.away}", game.url))
    crowds = [game for game in games if game.attendance]
    if crowds:
        game = max(crowds, key=lambda game: (game.attendance, -game.day.toordinal()))
        records.append(Record("biggest-crowd", "Biggest crowd", f"{game.attendance:,}", f"{game.home} vs {game.away}", game.url))
    return records


@dataclass
class Timing:
    blocks: list[tuple[int, int]] = field(default_factory=list)  # (for, against) per 5 minutes of regulation
    overtime: tuple[int, int] = (0, 0)
    periods: list[tuple[int, int]] = field(default_factory=list)


def goal_timing(games: list[Game], team: str) -> Timing:
    blocks = [[0, 0] for _ in range(int(REGULATION // BLOCK_MINUTES))]
    periods = [[0, 0] for _ in range(3)]
    overtime = [0, 0]
    for game in games:
        if team not in (game.home, game.away):
            continue
        side = game.side_of(team)
        for goal in game.goals:
            slot = 0 if goal.side == side else 1
            if goal.minute > REGULATION:
                overtime[slot] += 1
                continue
            index = min(int(goal.minute // BLOCK_MINUTES), len(blocks) - 1)
            blocks[index][slot] += 1
            periods[min(int(goal.minute // 20), 2)][slot] += 1
    return Timing(blocks=[tuple(block) for block in blocks], overtime=tuple(overtime), periods=[tuple(period) for period in periods])


@dataclass
class LeadRecord:
    games: int = 0
    trailed: int = 0
    trailed_points: int = 0
    comeback_wins: int = 0
    led: int = 0
    blown_leads: int = 0
    led_after_two: int = 0
    won_after_leading_two: int = 0
    trailed_after_two: int = 0
    won_after_trailing_two: int = 0


def lead_record(games: list[Game], team: str) -> LeadRecord:
    record = LeadRecord()
    for game in games:
        if team not in (game.home, game.away) or not game.goals:
            continue
        side = game.side_of(team)
        own = other = 0
        trailed = led = False
        at_two = None
        for goal in game.goals:
            if at_two is None and goal.minute > 40:
                at_two = own - other
            if goal.side == side:
                own += 1
            else:
                other += 1
            trailed = trailed or own < other
            led = led or own > other
        if at_two is None:
            at_two = own - other
        final_own, final_other = game.score_for(team)
        won, lost = final_own > final_other, final_own < final_other
        points = game.home_points if side == "home" else game.away_points
        record.games += 1
        if trailed:
            record.trailed += 1
            record.trailed_points += points or 0
            record.comeback_wins += won
        if led:
            record.led += 1
            record.blown_leads += lost
        if at_two > 0:
            record.led_after_two += 1
            record.won_after_leading_two += won
        elif at_two < 0:
            record.trailed_after_two += 1
            record.won_after_trailing_two += won
    return record


def crowds(games: list[Game]) -> dict[str, tuple[float, int]]:
    """Home team -> (average attendance, home games with a number)."""
    totals: dict[str, list[int]] = defaultdict(list)
    for game in games:
        if game.attendance:
            totals[game.home].append(game.attendance)
    return {team: (sum(values) / len(values), len(values)) for team, values in totals.items()}


def team_goals(games: list[Game]) -> dict[str, int]:
    """Goals per team from the goal events (no shootout goals); the final score for games without events."""
    totals: dict[str, int] = defaultdict(int)
    for game in games:
        if game.goals:
            for goal in game.goals:
                totals[game.home if goal.side == "home" else game.away] += 1
        else:
            totals[game.home] += game.home_goals
            totals[game.away] += game.away_goals
    return dict(totals)
