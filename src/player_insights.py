"""Clutch goals and scoring partnerships from the published game event payload.

Input is the event list behind ``game_events_b64`` (see
``run_stats_engine._build_game_events_payload``): one dict per goal, penalty or
period break with ``period``, ``minute``, ``side``, ``score`` (after the event),
scorer ``title``/``title_uid`` and ``assist``/``assist_uid``.

Definitions (shown in the stat guides on the site):

- Game-winning goal (GWG): the goal that gave the winner one more goal than the
  loser's final total. Games decided by penalty shots have none.
- Go-ahead goal: a goal that broke a tie. Equalizer: a goal that tied the game.
- Clutch goal: a go-ahead goal or an equalizer in the last ten minutes of the
  third period or in overtime. Clutch points are clutch goals plus assists on them.
- Duo: two players of one team who assisted each other's goals, counted in both
  directions.

Penalty-shootout goals never count, own goals count for the score only.
"""

from __future__ import annotations

import base64
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

PERIOD_MINUTES = 20
REGULATION_PERIODS = 3
LATE_MINUTE_IN_PERIOD = 10
OWN_GOAL_TAG = "own_goal"
SHOOTOUT_PERIOD = 5

GWG = "gwg"
GO_AHEAD = "go_ahead"
EQUALIZER = "equalizer"
OVERTIME = "overtime"
CLUTCH = "clutch"

_MINUTE_PATTERN = re.compile(r"(\d+):(\d{1,2})")
_SCORE_PATTERN = re.compile(r"^\s*(\d+)\s*:\s*(\d+)\s*$")


def decode_events(encoded: str) -> list[dict]:
    if not encoded:
        return []
    try:
        events = json.loads(base64.b64decode(encoded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return []
    return [event for event in events if isinstance(event, dict)] if isinstance(events, list) else []


def encode_events(events: list[dict]) -> str:
    return base64.b64encode(json.dumps(events, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).decode("ascii")


def minute_in_period(minute: object, period: int) -> float | None:
    """Minute within the period; some sources (Czech Republic) count the game clock across periods."""
    match = _MINUTE_PATTERN.search(str(minute or ""))
    if not match:
        return None
    value = int(match.group(1)) + int(match.group(2)) / 60
    offset = PERIOD_MINUTES * (period - 1)
    if 1 < period <= REGULATION_PERIODS and value > PERIOD_MINUTES:
        value -= offset
    return value


def _period(event: dict) -> int:
    try:
        return int(event.get("period") or 0)
    except (TypeError, ValueError):
        return 0


def _is_shootout(event: dict) -> bool:
    return _period(event) >= SHOOTOUT_PERIOD or str(event.get("minute") or "").strip().upper().startswith("PS")


def _parse_score(value: object) -> tuple[int, int] | None:
    match = _SCORE_PATTERN.match(str(value or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


@dataclass(frozen=True)
class PlayerRef:
    key: str
    name: str
    uid: str = ""


def player_ref(name: object, uid: object, team: str) -> PlayerRef | None:
    text = str(name or "").strip()
    if not text:
        return None
    player_uid = str(uid or "").strip()
    # Leagues without player ids (women's leagues) still get duos by name within a team.
    return PlayerRef(key=player_uid or f"{team}|{text}", name=text, uid=player_uid)


@dataclass
class GoalMoment:
    index: int
    side: str
    team: str
    scorer: PlayerRef | None
    assist: PlayerRef | None
    flags: set[str] = field(default_factory=set)


def goal_moments(events: list[dict]) -> list[GoalMoment]:
    """Goals in play order with their GWG / go-ahead / equalizer / clutch flags."""
    goals: list[tuple[int, dict, tuple[int, int], tuple[int, int]]] = []
    home = away = 0
    for index, event in enumerate(events):
        if event.get("event_kind") != "goal" or _is_shootout(event):
            continue
        side = event.get("side")
        if side not in ("home", "away"):
            continue
        # The published score after the goal wins over our own count (a feed may miss a goal).
        after = _parse_score(event.get("score"))
        if after is None or (after[0] if side == "home" else after[1]) < 1:
            after = (home + 1, away) if side == "home" else (home, away + 1)
        before = (after[0] - 1, after[1]) if side == "home" else (after[0], after[1] - 1)
        home, away = after
        goals.append((index, event, before, after))

    final_home, final_away = (home, away)
    winner = "home" if final_home > final_away else ("away" if final_away > final_home else "")
    winning_total = min(final_home, final_away) + 1

    moments: list[GoalMoment] = []
    for index, event, before, after in goals:
        side = event["side"]
        team = str(event.get("team") or "")
        own, other = (before[0], before[1]) if side == "home" else (before[1], before[0])
        is_own_goal = event.get("tag") == OWN_GOAL_TAG
        scorer = None if is_own_goal else player_ref(event.get("title"), event.get("title_uid"), team)
        assist = None if is_own_goal else player_ref(event.get("assist"), event.get("assist_uid"), team)
        flags: set[str] = set()
        if own == other:
            flags.add(GO_AHEAD)
        elif own + 1 == other:
            flags.add(EQUALIZER)
        if winner == side and (after[0] if side == "home" else after[1]) == winning_total:
            flags.add(GWG)
        period = _period(event)
        if period > REGULATION_PERIODS:
            flags.add(OVERTIME)
        minute = minute_in_period(event.get("minute"), period)
        is_late = period > REGULATION_PERIODS or (
            period == REGULATION_PERIODS and minute is not None and minute >= LATE_MINUTE_IN_PERIOD
        )
        if is_late and flags & {GO_AHEAD, EQUALIZER}:
            flags.add(CLUTCH)
        moments.append(GoalMoment(index=index, side=side, team=team, scorer=scorer, assist=assist, flags=flags))
    return moments


@dataclass
class ClutchLine:
    goals: int = 0
    assists: int = 0
    gwg: int = 0
    go_ahead: int = 0
    equalizers: int = 0
    overtime_goals: int = 0
    clutch_goals: int = 0
    clutch_assists: int = 0

    @property
    def clutch_points(self) -> int:
        return self.clutch_goals + self.clutch_assists

    def as_dict(self) -> dict:
        return {
            "goals": self.goals,
            "assists": self.assists,
            "gwg": self.gwg,
            "go_ahead": self.go_ahead,
            "equalizers": self.equalizers,
            "overtime_goals": self.overtime_goals,
            "clutch_goals": self.clutch_goals,
            "clutch_assists": self.clutch_assists,
            "clutch_points": self.clutch_points,
        }


@dataclass
class Duo:
    first: PlayerRef
    second: PlayerRef
    team: str
    first_to_second: int = 0
    second_to_first: int = 0

    @property
    def goals(self) -> int:
        return self.first_to_second + self.second_to_first

    def as_dict(self) -> dict:
        return {
            "first": self.first,
            "second": self.second,
            "team": self.team,
            "goals": self.goals,
            "first_to_second": self.first_to_second,
            "second_to_first": self.second_to_first,
        }


@dataclass
class GameEvents:
    category: str
    season: str
    game_id: str
    events: list[dict]


@dataclass
class Insights:
    # scope ("all", a season like "se-26-27", or a category slug) -> player key -> line
    clutch: dict[str, dict[str, ClutchLine]] = field(default_factory=lambda: defaultdict(dict))
    players: dict[str, PlayerRef] = field(default_factory=dict)
    player_teams: dict[tuple[str, str], str] = field(default_factory=dict)
    # scope -> pair key -> Duo
    duos: dict[str, dict[tuple[str, str], Duo]] = field(default_factory=lambda: defaultdict(dict))
    # (category, game_id) -> event index -> flags
    moments: dict[tuple[str, str], dict[int, set[str]]] = field(default_factory=dict)

    def clutch_leaders(self, scope: str, limit: int = 5) -> list[tuple[PlayerRef, str, ClutchLine]]:
        lines = [
            (self.players[key], self.player_teams.get((scope, key), ""), line)
            for key, line in self.clutch.get(scope, {}).items()
            if line.clutch_points > 0
        ]
        lines.sort(key=lambda item: (-item[2].clutch_points, -item[2].clutch_goals, -item[2].gwg, item[0].name))
        return lines[:limit]

    def top_duos(self, scope: str, team: str | None = None, limit: int = 5) -> list[Duo]:
        duos = [duo for duo in self.duos.get(scope, {}).values() if team is None or duo.team == team]
        duos.sort(key=lambda duo: (-duo.goals, -max(duo.first_to_second, duo.second_to_first), duo.first.name, duo.second.name))
        return duos[:limit]

    def partners(self, scope: str, player_key: str, limit: int = 3) -> list[tuple[PlayerRef, int, int]]:
        """(partner, goals the player scored from the partner's pass, assists the player gave the partner)."""
        rows: dict[str, list] = {}
        for duo in self.duos.get(scope, {}).values():
            if duo.first.key == player_key:
                rows[duo.second.key] = [duo.second, duo.second_to_first, duo.first_to_second]
            elif duo.second.key == player_key:
                rows[duo.first.key] = [duo.first, duo.first_to_second, duo.second_to_first]
        ordered = sorted(rows.values(), key=lambda row: (-(row[1] + row[2]), row[0].name))
        return [tuple(row) for row in ordered[:limit]]


def season_of(category: str) -> str:
    """Season key as player pages use it: 'se-26-27-regular-season' -> 'se-26-27', '26-27-playoffs' -> '26-27'."""
    return re.sub(r"-(?:regular-season|playoffs)$", "", category)


def build_insights(games: Iterable[GameEvents]) -> Insights:
    insights = Insights()

    def line(scope: str, player: PlayerRef, team: str) -> ClutchLine:
        insights.players.setdefault(player.key, player)
        insights.player_teams[(scope, player.key)] = team
        return insights.clutch[scope].setdefault(player.key, ClutchLine())

    for game in games:
        moments = goal_moments(game.events)
        flagged = {moment.index: set(moment.flags) for moment in moments if moment.flags & {GWG, CLUTCH, OVERTIME}}
        if flagged:
            insights.moments[(game.category, game.game_id)] = flagged
        scopes = ("all", game.season, game.category)
        for moment in moments:
            if moment.scorer:
                for scope in scopes:
                    scorer_line = line(scope, moment.scorer, moment.team)
                    scorer_line.goals += 1
                    scorer_line.gwg += GWG in moment.flags
                    scorer_line.go_ahead += GO_AHEAD in moment.flags
                    scorer_line.equalizers += EQUALIZER in moment.flags
                    scorer_line.overtime_goals += OVERTIME in moment.flags
                    scorer_line.clutch_goals += CLUTCH in moment.flags
            if moment.assist:
                for scope in scopes:
                    assist_line = line(scope, moment.assist, moment.team)
                    assist_line.assists += 1
                    assist_line.clutch_assists += CLUTCH in moment.flags
            if moment.scorer and moment.assist and moment.scorer.key != moment.assist.key:
                first, second = sorted((moment.assist, moment.scorer), key=lambda player: player.key)
                for scope in scopes:
                    duo = insights.duos[scope].setdefault(
                        (first.key, second.key), Duo(first=first, second=second, team=moment.team)
                    )
                    duo.team = moment.team
                    if moment.assist.key == first.key:
                        duo.first_to_second += 1
                    else:
                        duo.second_to_first += 1
    return insights


def label_moments(events: list[dict], flagged: dict[int, set[str]]) -> list[dict]:
    """Copy of the events with a short ``moment`` label on game-winning, clutch and overtime goals."""
    labelled = []
    for index, event in enumerate(events):
        flags = flagged.get(index)
        if flags:
            parts = []
            if GWG in flags:
                parts.append("Game winner")
            if CLUTCH in flags and OVERTIME not in flags:
                parts.append("Clutch")
            if OVERTIME in flags:
                parts.append("Overtime")
            event = {**event, "moment": " · ".join(parts)}
        labelled.append(event)
    return labelled
