"""Direct comparison of two teams over all tracked seasons of a league.

Input is every played game of one league (all seasons, regular season and
playoffs) as a ``Duel``: the game with its goals and penalties in play order
(``team_trends.Game``), the way it ended and its special-teams numbers. The
result for a pair of teams only counts the games these two played against each
other:

- Results: date, home team, score with "n.V." (overtime) or "n.P." (penalty
  shots), link to the game. Newest first. The record counts a win after
  overtime or penalty shots as an overtime win (OTW), like the form guide.
- Scorers: goals, assists and points of each team's players in these games.
  Own goals count for the team but not for a player.
- Penalties: every penalty in these games, by kind and per penalised player.
- Goal timing: goals of both teams in 5-minute blocks of regulation, plus overtime.
- Special teams: powerplay% is powerplay goals per powerplay, boxplay% is
  1 - goals against per boxplay, both from the per-game counts the pipeline
  already computes. Time with a man up or down is the sum of the per-game
  seconds; it is only reported when every game of the pair has them.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from src import player_insights as pi
from src import team_trends as tt
from src.player_insights import PlayerRef

TOP_PLAYERS = 5
DECISION_LABELS = {"overtime": "n.V.", "shootout": "n.P."}


@dataclass(frozen=True)
class SideSpecials:
    """One team's special teams in one game (counts as the pipeline publishes them)."""

    powerplay: int = 0
    powerplay_goals: int = 0
    boxplay: int = 0
    boxplay_goals_against: int = 0
    powerplay_seconds: int | None = None
    boxplay_seconds: int | None = None


@dataclass(frozen=True)
class Duel:
    game: tt.Game
    season: str
    phase: str
    decision: str = ""  # "", "n.V." or "n.P."
    home: SideSpecials = field(default_factory=SideSpecials)
    away: SideSpecials = field(default_factory=SideSpecials)

    def specials(self, team: str) -> SideSpecials:
        return self.home if team == self.game.home else self.away


PlayerUrl = Callable[[PlayerRef], str]


def _percent(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def _clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def _result_row(duel: Duel) -> dict:
    game = duel.game
    return {
        "date": game.day.isoformat(),
        "season": duel.season.replace("-", "/"),
        "phase": duel.phase,
        "home": game.home,
        "away": game.away,
        "score": f"{game.home_goals}:{game.away_goals}",
        "decision": duel.decision,
        "url": game.url,
    }


def _record(duels: list[Duel], team: str) -> dict:
    counts = {"W": 0, "OTW": 0, "D": 0, "OTL": 0, "L": 0}
    goals_for = goals_against = 0
    for duel in duels:
        counts[tt.letter(duel.game, team)] += 1
        own, other = duel.game.score_for(team)
        goals_for += own
        goals_against += other
    return {**counts, "games": len(duels), "goals_for": goals_for, "goals_against": goals_against}


def _named(rows: dict[str, dict], player: PlayerRef, player_url: PlayerUrl, **start: int) -> dict:
    """One row per player name: some feeds carry a player id on a team's events only in some games."""
    row = rows.setdefault(player.name, {"name": player.name, "url": "", **start})
    row["url"] = row["url"] or player_url(player)
    return row


def _scorers(duels: list[Duel], team: str, player_url: PlayerUrl) -> list[dict]:
    lines: dict[str, dict] = {}
    for duel in duels:
        side = duel.game.side_of(team)
        for goal in duel.game.goals:
            if goal.side != side:
                continue
            if goal.scorer:
                _named(lines, goal.scorer, player_url, goals=0, assists=0)["goals"] += 1
            if goal.assist:
                _named(lines, goal.assist, player_url, goals=0, assists=0)["assists"] += 1
    rows = [{**item, "points": item["goals"] + item["assists"]} for item in lines.values()]
    rows.sort(key=lambda item: (-item["points"], -item["goals"], item["name"]))
    return rows[:TOP_PLAYERS]


def _penalties(duels: list[Duel], team: str, player_url: PlayerUrl) -> dict:
    kinds: dict[str, int] = defaultdict(int)
    players: dict[str, dict] = {}
    total = 0
    for duel in duels:
        side = duel.game.side_of(team)
        for penalty in duel.game.penalties:
            if penalty.side != side:
                continue
            total += 1
            kinds[penalty.kind] += 1
            if penalty.player:
                _named(players, penalty.player, player_url, count=0)["count"] += 1
    top = sorted(players.values(), key=lambda item: (-item["count"], item["name"]))[:TOP_PLAYERS]
    return {
        "total": total,
        "per_game": round(total / len(duels), 2) if duels else None,
        "kinds": {kind: kinds[kind] for kind in (*tt.PENALTY_KINDS, "Other") if kinds.get(kind)},
        "players": top,
    }


def _timing(duels: list[Duel], teams: tuple[str, str]) -> dict:
    blocks = int(tt.REGULATION // tt.BLOCK_MINUTES)
    counts = {team: [0] * blocks for team in teams}
    overtime = {team: 0 for team in teams}
    for duel in duels:
        for goal in duel.game.goals:
            team = duel.game.home if goal.side == "home" else duel.game.away
            if goal.minute >= tt.REGULATION:
                overtime[team] += 1
            else:
                counts[team][int(goal.minute // tt.BLOCK_MINUTES)] += 1
    return {
        "labels": [f"{index * tt.BLOCK_MINUTES}–{(index + 1) * tt.BLOCK_MINUTES}" for index in range(blocks)],
        "goals": counts,
        "overtime": overtime,
    }


def _special_teams(duels: list[Duel], team: str) -> dict:
    sides = [duel.specials(team) for duel in duels]
    opponents = [duel.specials(duel.game.opponent(team)) for duel in duels]
    powerplay = sum(side.powerplay for side in sides)
    powerplay_goals = sum(side.powerplay_goals for side in sides)
    boxplay = sum(side.boxplay for side in sides)
    boxplay_against = sum(side.boxplay_goals_against for side in sides)
    # Our man-up seconds are the opponent's man-down seconds, so either feed gives both.
    pp_seconds = [side.powerplay_seconds if side.powerplay_seconds is not None else other.boxplay_seconds for side, other in zip(sides, opponents)]
    bp_seconds = [side.boxplay_seconds if side.boxplay_seconds is not None else other.powerplay_seconds for side, other in zip(sides, opponents)]
    pp_total = None if not duels or any(value is None for value in pp_seconds) else sum(pp_seconds)
    bp_total = None if not duels or any(value is None for value in bp_seconds) else sum(bp_seconds)
    return {
        "powerplay": powerplay,
        "powerplay_goals": powerplay_goals,
        "powerplay_pct": _percent(powerplay_goals, powerplay),
        "boxplay": boxplay,
        "boxplay_goals_against": boxplay_against,
        "boxplay_pct": _percent(boxplay - boxplay_against, boxplay),
        "powerplay_time": _clock(pp_total) if pp_total is not None else None,
        "boxplay_time": _clock(bp_total) if bp_total is not None else None,
    }


def versus(duels: list[Duel], teams: tuple[str, str], player_url: PlayerUrl = lambda player: "") -> dict:
    """Everything the comparison page shows for two teams; ``duels`` holds only their games."""
    ordered = sorted(duels, key=lambda duel: (duel.game.day, duel.game.game_id), reverse=True)
    first, second = teams
    return {
        "results": [_result_row(duel) for duel in ordered],
        "record": {first: _record(ordered, first), second: _record(ordered, second)},
        "scorers": {team: _scorers(ordered, team, player_url) for team in teams},
        "penalties": {team: _penalties(ordered, team, player_url) for team in teams},
        "timing": _timing(ordered, teams),
        "special": {team: _special_teams(ordered, team) for team in teams},
    }


def league_payload(duels: list[Duel], team_urls: dict[str, str] | None = None, player_url: PlayerUrl = lambda player: "") -> dict:
    """All pairs of one league. ``pairs`` is keyed ``"i-j"`` with the indexes into ``teams`` (i < j)."""
    names = sorted({name for duel in duels for name in (duel.game.home, duel.game.away)}, key=str.casefold)
    index = {name: position for position, name in enumerate(names)}
    grouped: dict[tuple[int, int], list[Duel]] = defaultdict(list)
    for duel in duels:
        pair = tuple(sorted((index[duel.game.home], index[duel.game.away])))
        if pair[0] != pair[1]:
            grouped[pair].append(duel)
    pairs = {f"{i}-{j}": versus(items, (names[i], names[j]), player_url) for (i, j), items in sorted(grouped.items())}
    opponents: dict[int, list[int]] = defaultdict(list)
    for i, j in grouped:
        opponents[i].append(j)
        opponents[j].append(i)
    return {
        "teams": [{"name": name, "url": (team_urls or {}).get(name, "")} for name in names],
        "opponents": {str(key): sorted(value) for key, value in sorted(opponents.items())},
        "pairs": pairs,
    }



def team_rows(payload: dict, team: str, opponents: list[str] | None = None) -> list[dict]:
    """One team's record against every opponent of a ``league_payload`` that it has played.

    Rows follow the order of ``opponents`` (the league table), or the payload's team order
    when none is given; opponents the team has not met are left out.
    """
    names = [item["name"] for item in payload["teams"]]
    if team not in names:
        return []
    own = names.index(team)
    met = {names[index]: index for index in payload["opponents"].get(str(own), [])}
    rows = []
    for name in opponents if opponents is not None else names:
        index = met.get(name)
        if index is None:
            continue
        record = payload["pairs"][f"{min(own, index)}-{max(own, index)}"]["record"][team]
        rows.append({"team": name, **{key: record[key] for key in ("games", "W", "OTW", "OTL", "L", "goals_for", "goals_against")}})
    return rows


def man_advantage_seconds(events: list[dict], home: str, away: str) -> tuple[int, int] | None:
    """(home, away) seconds with a man up from the game's event payload, or None.

    Reuses the stats engine's ``stat_powerplay_seconds`` on a frame rebuilt from the
    payload (the same events the ``events`` table holds), so the page needs no
    database at build time. Returns None while the engine has no such stat or the
    game has no penalties and goals to work with.
    """
    from src import run_stats_engine as engine

    stat = getattr(engine, "stat_powerplay_seconds", None)
    if stat is None:
        return None
    rows = []
    for event in events:
        kind = event.get("event_kind")
        if kind not in ("goal", "penalty") or event.get("side") not in ("home", "away"):
            continue
        try:
            period = int(event.get("period") or 0)
        except (TypeError, ValueError):
            continue
        in_period = pi.minute_in_period(event.get("minute"), period) if period else None
        if in_period is None or period >= pi.SHOOTOUT_PERIOD:
            continue
        rows.append(
            {
                "event_type": engine.EVENT_GOAL if kind == "goal" else engine.EVENT_PENALTY,
                "event_team": home if event["side"] == "home" else away,
                "penalty_type": event.get("tag") if kind == "penalty" else None,
                "period": period,
                "time_in_s": int((period - 1) * pi.PERIOD_MINUTES * 60 + round(in_period * 60)),
            }
        )
    if not rows:
        return None
    frame = pd.DataFrame(rows)
    return int(stat(frame, home)), int(stat(frame, away))
