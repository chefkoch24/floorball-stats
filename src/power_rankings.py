"""Elo power ratings, win probabilities and Monte Carlo season projections.

Ratings run per league chain (one category prefix such as ``se-`` over all
published seasons, regular season and playoffs in date order):

- Every team starts at 1500; a team new to a league that already has a season
  of history starts at ``NEWCOMER_RATING`` (promoted teams tend to be weaker).
- Between seasons every rating moves a quarter of the way back to 1500.
- The home team gets ``HOME_ADVANTAGE`` rating points.
- A regulation win counts as a full win, a win after overtime or penalty shots
  as ``EXTRA_TIME_SCORE``, a draw as 0.5. The update scales with the goal margin
  (FiveThirtyEight's margin-of-victory multiplier).

The parameters were chosen by a grid search on the 25-26 and 26-27 games of all
league chains (October 2026, 1350 decided games after a burn-in): log loss of the
pre-game home-win probability 0.545 (a coin flip is 0.693), Brier score 0.184,
and predicted and observed home-win rates agree within a few points per decile.

``simulate_season`` plays the remaining regular-season games many times. Each
simulated season draws every team's strength around its current rating
(``RATING_UNCERTAINTY``, standing in for what a rating does not know yet), ranks
the teams by points (then current goal difference, then chance) and, when a
playoff format is given, plays the bracket: the best seed meets the worst
remaining one in every round.
"""

from __future__ import annotations

import math
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable, Sequence

import numpy as np

BASE_RATING = 1500.0
NEWCOMER_RATING = 1450.0
SEASON_REGRESSION = 0.25
HOME_ADVANTAGE = 45.0
K_FACTOR = 56.0
EXTRA_TIME_SCORE = 0.6
# Spread of the true strength around the current rating in each simulated season.
RATING_UNCERTAINTY = 50.0

REGULATION = "REG"
OVERTIME = "OT"
SHOOTOUT = "PS"

DEFAULT_POINTS = {"win": 3, "extra_win": 2, "extra_loss": 1, "loss": 0, "draw": 1}


@dataclass(frozen=True)
class GameResult:
    game_id: str
    season: str
    phase: str
    day: date
    order: str
    home: str
    away: str
    played: bool
    home_goals: int = 0
    away_goals: int = 0
    decision: str = REGULATION
    home_points: int | None = None
    away_points: int | None = None

    @property
    def sort_key(self) -> tuple:
        return (self.day, self.order, self.game_id)


def win_probability(home_rating, away_rating, home_advantage: float = HOME_ADVANTAGE):
    """Chance that the home team wins (after regulation, overtime or penalty shots)."""
    return 1.0 / (1.0 + 10 ** ((away_rating - home_rating - home_advantage) / 400.0))


def _actual_score(game: GameResult, extra_time_score: float = EXTRA_TIME_SCORE) -> float:
    if game.home_goals == game.away_goals:
        return 0.5
    full = 1.0 if game.decision == REGULATION else extra_time_score
    return full if game.home_goals > game.away_goals else 1.0 - full


def _margin_multiplier(goal_diff: int, winner_rating_diff: float) -> float:
    return math.log(abs(goal_diff) + 1) * (2.2 / (winner_rating_diff * 0.001 + 2.2))


def elo_example(home_rating: float = 1600.0, away_rating: float = 1500.0, home_goals: int = 5, away_goals: int = 3) -> dict:
    """One rating update with the live parameters, for the explanation page."""
    expected = win_probability(home_rating, away_rating)
    multiplier = _margin_multiplier(home_goals - away_goals, home_rating + HOME_ADVANTAGE - away_rating)
    change = K_FACTOR * multiplier * (1.0 - expected)
    return {
        "home_rating": round(home_rating),
        "away_rating": round(away_rating),
        "home_goals": home_goals,
        "away_goals": away_goals,
        "expected": expected,
        "multiplier": multiplier,
        "change": change,
        # The same favourite winning only after overtime, by one goal.
        "extra_time_change": K_FACTOR
        * _margin_multiplier(1, home_rating + HOME_ADVANTAGE - away_rating)
        * (EXTRA_TIME_SCORE - expected),
    }


def model_parameters() -> dict:
    return {
        "base": round(BASE_RATING),
        "newcomer": round(NEWCOMER_RATING),
        "regression": SEASON_REGRESSION,
        "home_advantage": round(HOME_ADVANTAGE),
        "k_factor": round(K_FACTOR),
        "extra_time_score": EXTRA_TIME_SCORE,
        "uncertainty": round(RATING_UNCERTAINTY),
        "neutral_100": win_probability(BASE_RATING + 100, BASE_RATING, 0.0),
        "example": elo_example(),
    }


@dataclass
class EloRun:
    ratings: dict[str, float] = field(default_factory=dict)
    # team -> [(day, rating after the game, game_id)]
    history: dict[str, list[tuple[date, float, str]]] = field(default_factory=lambda: defaultdict(list))
    # game_id -> (home rating, away rating, home win probability) before the game
    pregame: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    season_teams: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def rating_on(self, team: str, day: date) -> float | None:
        """Rating after the last game played before ``day``."""
        rating = None
        for game_day, value, _ in self.history.get(team, []):
            if game_day >= day:
                break
            rating = value
        return rating


def run_elo(
    games: Iterable[GameResult],
    k_factor: float = K_FACTOR,
    home_advantage: float = HOME_ADVANTAGE,
    season_regression: float = SEASON_REGRESSION,
    newcomer_rating: float = NEWCOMER_RATING,
    extra_time_score: float = EXTRA_TIME_SCORE,
) -> EloRun:
    """Ratings after all played games, plus the pre-game view of every game (played or scheduled)."""
    run = EloRun()
    ordered = sorted(games, key=lambda game: (_season_order(game.season), game.sort_key))
    current_season = None
    seen_seasons: list[str] = []
    for game in ordered:
        if game.season != current_season:
            if current_season is not None:
                for team, rating in run.ratings.items():
                    run.ratings[team] = BASE_RATING + (rating - BASE_RATING) * (1 - season_regression)
            current_season = game.season
            seen_seasons.append(game.season)
        start = newcomer_rating if len(seen_seasons) > 1 else BASE_RATING
        for team in (game.home, game.away):
            run.ratings.setdefault(team, start)
            run.season_teams[game.season].add(team)
        home_rating, away_rating = run.ratings[game.home], run.ratings[game.away]
        expected = win_probability(home_rating, away_rating, home_advantage)
        run.pregame[game.game_id] = (home_rating, away_rating, expected)
        if not game.played:
            continue
        actual = _actual_score(game, extra_time_score)
        goal_diff = game.home_goals - game.away_goals
        winner_diff = (home_rating + home_advantage - away_rating) * (1 if goal_diff >= 0 else -1)
        multiplier = _margin_multiplier(goal_diff, winner_diff) if goal_diff else 1.0
        change = k_factor * multiplier * (actual - expected)
        run.ratings[game.home] = home_rating + change
        run.ratings[game.away] = away_rating - change
        run.history[game.home].append((game.day, run.ratings[game.home], game.game_id))
        run.history[game.away].append((game.day, run.ratings[game.away], game.game_id))
    return run


def _season_order(season: str) -> tuple:
    digits = [int(part) for part in season.split("-") if part.isdigit()]
    return tuple(digits) or (0,)


@dataclass(frozen=True)
class LeagueModel:
    """How a league awards points and how often games go past regulation."""

    points: dict[str, int]
    extra_time_rate: float
    draw_rate: float


def league_model(games: Sequence[GameResult]) -> LeagueModel:
    played = [game for game in games if game.played and game.phase == "regular-season"]
    votes: dict[str, Counter] = defaultdict(Counter)
    extra = draws = 0
    for game in played:
        if game.home_goals == game.away_goals:
            draws += 1
            if game.home_points is not None:
                votes["draw"][game.home_points] += 1
            continue
        home_won = game.home_goals > game.away_goals
        winner_points = game.home_points if home_won else game.away_points
        loser_points = game.away_points if home_won else game.home_points
        if game.decision == REGULATION:
            win_key, loss_key = "win", "loss"
        else:
            extra += 1
            win_key, loss_key = "extra_win", "extra_loss"
        if winner_points is not None:
            votes[win_key][winner_points] += 1
        if loser_points is not None:
            votes[loss_key][loser_points] += 1
    points = {key: (votes[key].most_common(1)[0][0] if votes[key] else default) for key, default in DEFAULT_POINTS.items()}
    total = len(played)
    if total < 20:
        # Too few games for a rate of their own: use a typical top-league share.
        return LeagueModel(points=points, extra_time_rate=0.15, draw_rate=draws / total if total else 0.0)
    return LeagueModel(points=points, extra_time_rate=extra / total, draw_rate=draws / total)


@dataclass(frozen=True)
class PlayoffRound:
    name: str
    teams: int
    wins_to_advance: int


@dataclass
class TeamProjection:
    team: str
    rating: float
    points_now: int
    projected_points: float
    projected_rank: float
    first: float
    top4: float
    playoffs: float
    title: float | None = None


def _outcome_probabilities(p_home: np.ndarray, model: LeagueModel) -> np.ndarray:
    """Columns: home regulation win, home extra-time win, away extra-time win, away regulation win, draw."""
    draw = model.draw_rate
    extra = model.extra_time_rate
    decisive = max(1e-9, 1.0 - draw)
    # Share of the home team's decisive results; extra time is closer to a coin flip.
    p_win = np.clip((p_home - 0.5 * draw) / decisive, 0.0, 1.0)
    extra_home = 0.5 + (p_win - 0.5) * 0.5
    regulation_share = max(1e-9, decisive - extra)
    reg_home = np.clip((p_win * decisive - extra * extra_home) / regulation_share, 0.0, 1.0)
    return np.stack(
        [
            regulation_share * reg_home,
            extra * extra_home,
            extra * (1 - extra_home),
            regulation_share * (1 - reg_home),
            np.full_like(p_home, draw),
        ],
        axis=-1,
    )


def simulate_season(
    ratings: dict[str, float],
    points_now: dict[str, int],
    goal_diff_now: dict[str, int],
    remaining: Sequence[GameResult],
    model: LeagueModel,
    playoff_teams: int,
    rounds: Sequence[PlayoffRound] = (),
    simulations: int = 4000,
    seed: str = "",
    home_advantage: float = HOME_ADVANTAGE,
    rating_uncertainty: float = RATING_UNCERTAINTY,
) -> list[TeamProjection]:
    teams = sorted(points_now)
    index = {team: position for position, team in enumerate(teams)}
    size = len(teams)
    if size == 0:
        return []
    rng = np.random.default_rng(zlib.crc32(seed.encode("utf-8")))
    # Each simulated season draws its own true strengths around the current ratings.
    base = np.array([ratings.get(team, BASE_RATING) for team in teams])
    strength = base[None, :] + rng.normal(0.0, rating_uncertainty, (simulations, size))
    totals = np.tile(np.array([points_now[team] for team in teams], dtype=float), (simulations, 1))
    pts = model.points
    home_awards = np.array([pts["win"], pts["extra_win"], pts["extra_loss"], pts["loss"], pts["draw"]], dtype=float)
    away_awards = np.array([pts["loss"], pts["extra_loss"], pts["extra_win"], pts["win"], pts["draw"]], dtype=float)
    for game in remaining:
        if game.home not in index or game.away not in index:
            continue
        home, away = index[game.home], index[game.away]
        p_home = win_probability(strength[:, home], strength[:, away], home_advantage)
        cumulative = np.cumsum(_outcome_probabilities(p_home, model), axis=1)
        draws = rng.random(simulations) * cumulative[:, -1]
        outcome = np.minimum((draws[:, None] > cumulative).sum(axis=1), 4)
        totals[:, home] += home_awards[outcome]
        totals[:, away] += away_awards[outcome]

    tiebreak = np.array([goal_diff_now.get(team, 0) for team in teams], dtype=float) * 1e-4
    keys = totals + tiebreak + rng.random((simulations, size)) * 1e-6
    order = np.argsort(-keys, axis=1)
    ranks = np.empty_like(order)
    ranks[np.arange(simulations)[:, None], order] = np.arange(size)[None, :]

    cut = min(playoff_teams, size)
    titles = np.zeros(size)
    run_playoffs = bool(rounds) and cut >= 2
    if run_playoffs:
        for sim in range(simulations):
            champion = _play_bracket(list(order[sim, :cut]), strength[sim], rounds, rng, home_advantage)
            titles[champion] += 1

    projections = []
    for team in teams:
        column = index[team]
        team_ranks = ranks[:, column]
        projections.append(
            TeamProjection(
                team=team,
                rating=ratings.get(team, BASE_RATING),
                points_now=points_now[team],
                projected_points=float(totals[:, column].mean()),
                projected_rank=float(team_ranks.mean() + 1),
                first=float((team_ranks == 0).mean()),
                top4=float((team_ranks < 4).mean()),
                playoffs=float((team_ranks < cut).mean()),
                title=float(titles[column] / simulations) if run_playoffs else None,
            )
        )
    projections.sort(key=lambda item: (-item.rating, item.team))
    return projections


def _play_bracket(seeds: list[int], strength: np.ndarray, rounds: Sequence[PlayoffRound], rng, home_advantage: float) -> int:
    """Champion of one simulated bracket; ``seeds`` are team columns, best seed first."""
    alive = list(seeds)
    plan = list(rounds)
    if plan and plan[0].teams < len(alive):
        # Play-in: the lowest seeds play for the last places of the next round.
        play_in = plan.pop(0)
        direct, contenders = alive[: len(alive) - play_in.teams], alive[len(alive) - play_in.teams :]
        alive = direct + _play_round(contenders, strength, play_in.wins_to_advance, rng, home_advantage)
    elif plan:
        alive = alive[: plan[0].teams]
    for current in plan:
        alive = alive[: current.teams]
        if len(alive) < 2:
            break
        alive = _play_round(alive, strength, current.wins_to_advance, rng, home_advantage)
    return alive[0]


def _play_round(alive: list[int], strength: np.ndarray, wins_to_advance: int, rng, home_advantage: float) -> list[int]:
    winners = []
    for position in range(len(alive) // 2):
        high, low = alive[position], alive[-(position + 1)]
        winners.append(_play_series(high, low, strength, wins_to_advance, rng, home_advantage))
    if len(alive) % 2:
        winners.append(alive[len(alive) // 2])
    # Keep seed order so the next round again pairs best against worst.
    return sorted(winners, key=alive.index)


def _play_series(high: int, low: int, strength: np.ndarray, wins_to_advance: int, rng, home_advantage: float) -> int:
    wins = {high: 0, low: 0}
    game = 0
    while max(wins.values()) < wins_to_advance:
        # Single games (a final) are on neutral ice; series alternate, the better seed at home first.
        edge = 0.0 if wins_to_advance == 1 else (home_advantage if game % 2 == 0 else -home_advantage)
        p_high = win_probability(strength[high], strength[low], edge)
        wins[high if rng.random() < p_high else low] += 1
        game += 1
    return high if wins[high] == wins_to_advance else low


def to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value
