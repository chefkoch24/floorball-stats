"""Powerplay and shorthanded goals from a game's event payload.

Pure functions on the event list behind ``game_events_b64`` (see
``run_stats_engine._build_game_events_payload``), so the Pelican build needs no database
and no refresh of the league data. The rules are the stats engine's own
(``utils.add_penalties`` / ``is_powerplay`` / ``is_boxplay``): a minor penalty lasts two
minutes, a double minor and a match penalty count as two penalties. One difference: both
teams share one penalty state, so a powerplay goal also ends the opponent's penalty for
the other side (the stats engine tracks each team in a separate pass).
"""
from __future__ import annotations

from dataclasses import dataclass

from src import player_insights as pi
from src.utils import add_penalties, is_boxplay, is_powerplay

POWERPLAY = "pp"
SHORTHANDED = "sh"
PENALTY_SECONDS = 120


def _seconds(event: dict) -> int | None:
    try:
        period = int(event.get("period") or 0)
    except (TypeError, ValueError):
        return None
    if period <= 0 or period >= pi.SHOOTOUT_PERIOD:
        return None
    in_period = pi.minute_in_period(event.get("minute"), period)
    if in_period is None:
        return None
    return int((period - 1) * pi.PERIOD_MINUTES * 60 + round(in_period * 60))


def goal_situations(events: list[dict]) -> dict[int, str]:
    """Event index -> ``pp`` or ``sh`` for goals scored with a man up or down.

    Goals at even strength, in the shootout and own goals are left out. ``events`` must be
    in game order, as the payload is.
    """
    penalties: dict[str, list[int]] = {"home": [], "away": []}
    situations: dict[int, str] = {}
    for index, event in enumerate(events):
        side = event.get("side")
        kind = event.get("event_kind")
        if side not in penalties or kind not in ("goal", "penalty"):
            continue
        now = _seconds(event)
        if now is None:
            continue
        for queue in penalties.values():
            if queue and now - queue[0] >= PENALTY_SECONDS:
                queue.pop(0)
        if kind == "penalty":
            add_penalties(str(event.get("tag") or ""), penalties[side], now)
            continue
        if event.get("tag") == pi.OWN_GOAL_TAG:
            continue
        other = "away" if side == "home" else "home"
        if is_powerplay(now, penalties[side], penalties[other]):
            situations[index] = POWERPLAY
            penalties[other].pop(0)
        elif is_boxplay(now, penalties[side], penalties[other]):
            situations[index] = SHORTHANDED
    return situations


def label_situations(events: list[dict]) -> list[dict]:
    """Copy of the events with ``situation`` (``pp`` / ``sh``) on powerplay and shorthanded goals."""
    situations = goal_situations(events)
    return [{**event, "situation": situations[index]} if index in situations else event for index, event in enumerate(events)]


# --- League view: powerplay and boxplay per team -------------------------------------------------

SCATTER_PADDING = 0.12
SCATTER_MIN_SPAN = 10.0


@dataclass(frozen=True)
class TeamSpecials:
    team: str
    url: str
    games: int
    pp_goals: int
    pp_opportunities: int
    bp_goals_against: int
    bp_opportunities: int
    sh_goals: int


def _percent(part: int, whole: int) -> float | None:
    return part / whole * 100 if whole > 0 else None


def _axis(values: list[float]) -> tuple[float, float]:
    low, high = min(values), max(values)
    pad = max((high - low) * SCATTER_PADDING, (SCATTER_MIN_SPAN - (high - low)) / 2, 0.0)
    return max(low - pad, 0.0), min(high + pad, 100.0)


def _position(value: float, low: float, high: float) -> float:
    return round((value - low) / (high - low) * 100, 1) if high > low else 50.0


def league_table(teams: list[TeamSpecials]) -> dict | None:
    """Rows for the special teams table and the scatter (powerplay % against penalty kill %).

    Powerplay % is goals per powerplay, penalty kill % the share of penalties killed without
    a goal against (the ``boxplay_efficiency`` of the team stats). Returns None while no team
    has had a powerplay. Scatter positions are percentages of the plot box, ``x`` from the
    left and ``y`` from the bottom; the cross marks the league average.
    """
    if not any(team.pp_opportunities for team in teams):
        return None
    rows = []
    for team in teams:
        killed = team.bp_opportunities - team.bp_goals_against
        rows.append(
            {
                "team": team.team,
                "url": team.url,
                "games": team.games,
                "pp_goals": team.pp_goals,
                "pp_opportunities": team.pp_opportunities,
                "pp_percent": _percent(team.pp_goals, team.pp_opportunities),
                "bp_goals_against": team.bp_goals_against,
                "bp_opportunities": team.bp_opportunities,
                "bp_percent": _percent(killed, team.bp_opportunities),
                "sh_goals": team.sh_goals,
            }
        )
    plotted = [row for row in rows if row["pp_percent"] is not None and row["bp_percent"] is not None]
    league_pp = _percent(sum(t.pp_goals for t in teams), sum(t.pp_opportunities for t in teams))
    league_bp = _percent(
        sum(t.bp_opportunities - t.bp_goals_against for t in teams), sum(t.bp_opportunities for t in teams)
    )
    scatter = None
    if plotted and league_pp is not None and league_bp is not None:
        x_low, x_high = _axis([row["pp_percent"] for row in plotted] + [league_pp])
        y_low, y_high = _axis([row["bp_percent"] for row in plotted] + [league_bp])
        for row in plotted:
            row["x"] = _position(row["pp_percent"], x_low, x_high)
            row["y"] = _position(row["bp_percent"], y_low, y_high)
        scatter = {
            "x_range": (round(x_low), round(x_high)),
            "y_range": (round(y_low), round(y_high)),
            "mid_x": _position(league_pp, x_low, x_high),
            "mid_y": _position(league_bp, y_low, y_high),
        }
    return {"rows": rows, "league_pp": league_pp, "league_bp": league_bp, "scatter": scatter}
