"""In-game win probability and the story of a finished game.

The live win probability combines the pre-game chance from the Elo ratings
with the score and the time left:

    logit p = W_PRIOR_EARLY * prior * f + W_PRIOR_LATE * prior * (1 - f) + W_LEAD * diff / sqrt(f + LEAD_DAMPING)

with ``prior`` the logit of the pre-game home win chance, ``f`` the share of
regulation time left and ``diff`` home goals minus away goals. A lead weighs
more the less time is left; once regulation is over a lead has won and a tie
goes to overtime, where only a little of the pre-game edge remains.

The weights were fitted (logistic regression, October 2026) on every minute of
1814 decided 25-26 and 26-27 games of all league chains: log loss 0.410 against
0.558 for the pre-game chance alone, and predicted and observed home-win rates
agree within a few points per decile.

``game_story`` turns a game's goals into the probability line, lead changes,
ties, the largest lead, the comeback the winner made, the goals that moved the
probability most and an excitement value: the total movement of the line.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

REGULATION_MINUTES = 60.0
W_PRIOR_EARLY = 1.146
W_PRIOR_LATE = 0.389
W_LEAD = 0.486
LEAD_DAMPING = 0.03
SAMPLE_STEP = 0.5


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def live_win_probability(pregame_home: float, minute: float, diff: int) -> float:
    """Home team's chance to win at ``minute`` with goal difference ``diff`` (home minus away)."""
    prior = _logit(pregame_home)
    if minute >= REGULATION_MINUTES:
        if diff:
            return 1.0 if diff > 0 else 0.0
        return _sigmoid(W_PRIOR_LATE * prior)
    left = max(0.0, (REGULATION_MINUTES - minute) / REGULATION_MINUTES)
    z = W_PRIOR_EARLY * prior * left + W_PRIOR_LATE * prior * (1 - left) + W_LEAD * diff / math.sqrt(left + LEAD_DAMPING)
    return _sigmoid(z)


@dataclass(frozen=True)
class FlowGoal:
    minute: float  # game clock, overtime continues after 60
    side: str  # "home" or "away"
    scorer: str = ""
    index: int = -1  # position in the game event payload, -1 when unknown


@dataclass
class KeyMoment:
    goal: FlowGoal
    score: str
    before: float
    after: float

    @property
    def swing(self) -> float:
        return abs(self.after - self.before)


@dataclass
class GameStory:
    points: list[tuple[float, float]] = field(default_factory=list)  # (minute, home win chance)
    goals: list[tuple[FlowGoal, str, float]] = field(default_factory=list)  # goal, score after, chance after
    end_minute: float = REGULATION_MINUTES
    lead_changes: int = 0
    ties: int = 0
    largest_lead: dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    comeback: int = 0
    winner: str = ""
    excitement: float = 0.0
    key_moments: list[KeyMoment] = field(default_factory=list)


def goal_minute(period: int, minute_in_period: float) -> float:
    if period > 3:
        return REGULATION_MINUTES + minute_in_period
    return (period - 1) * 20.0 + minute_in_period


def game_story(pregame_home: float, goals: list[FlowGoal], final_home: int, final_away: int, end_minute: float | None = None) -> GameStory:
    goals = sorted(goals, key=lambda goal: goal.minute)
    last_goal = goals[-1].minute if goals else 0.0
    end = max(REGULATION_MINUTES, end_minute or 0.0, last_goal)
    story = GameStory(end_minute=end)
    story.winner = "home" if final_home > final_away else ("away" if final_away > final_home else "")

    home = away = 0
    leader = ""
    deficit = {"home": 0, "away": 0}
    minute = 0.0
    previous = live_win_probability(pregame_home, 0.0, 0)
    story.points.append((0.0, previous))
    for goal in goals:
        # The line drifts with the clock between goals.
        while minute + SAMPLE_STEP < goal.minute and minute + SAMPLE_STEP <= REGULATION_MINUTES:
            minute += SAMPLE_STEP
            value = live_win_probability(pregame_home, minute, home - away)
            story.excitement += abs(value - previous)
            previous = value
            story.points.append((minute, value))
        before = live_win_probability(pregame_home, goal.minute, home - away)
        story.excitement += abs(before - previous)
        story.points.append((goal.minute, before))
        if goal.side == "home":
            home += 1
        else:
            away += 1
        after = live_win_probability(pregame_home, goal.minute, home - away)
        if goal.minute > REGULATION_MINUTES:
            after = 1.0 if goal.side == "home" else 0.0
        story.excitement += abs(after - before)
        story.points.append((goal.minute, after))
        previous = after
        minute = goal.minute

        score = f"{home}:{away}"
        story.goals.append((goal, score, after))
        story.key_moments.append(KeyMoment(goal=goal, score=score, before=before, after=after))
        new_leader = "home" if home > away else ("away" if away > home else "")
        # ``leader`` keeps the last team in front through ties, so 1:0, 1:1, 1:2 is one lead change.
        if new_leader and leader and new_leader != leader:
            story.lead_changes += 1
        if not new_leader:
            story.ties += 1
        if new_leader:
            story.largest_lead[new_leader] = max(story.largest_lead[new_leader], abs(home - away))
            leader = new_leader
        deficit["home"] = max(deficit["home"], away - home)
        deficit["away"] = max(deficit["away"], home - away)

    while minute + SAMPLE_STEP <= min(end, REGULATION_MINUTES):
        minute += SAMPLE_STEP
        value = live_win_probability(pregame_home, minute, home - away)
        story.excitement += abs(value - previous)
        previous = value
        story.points.append((minute, value))
    if story.winner:
        final = 1.0 if story.winner == "home" else 0.0
        story.excitement += abs(final - previous)
        story.points.append((end, final))
        story.comeback = deficit[story.winner]
    else:
        story.points.append((end, previous))
    # The three biggest swings, told in the order they happened.
    biggest = sorted(story.key_moments, key=lambda moment: -moment.swing)[:3]
    story.key_moments = sorted(biggest, key=lambda moment: moment.goal.minute)
    return story
