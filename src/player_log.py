"""Per-player game log and powerplay / shorthanded goal totals from the game event payloads.

Pure functions on the labelled events behind ``game_events_b64`` (see
``special_teams.label_situations``), so the Pelican build needs no database. The sources
publish no line-ups, so a player appears in the log of the games where they scored or set
up a goal; games without a point are not in it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from src import special_teams as sp

WIN, LOSS, DRAW, OT_WIN, OT_LOSS = "W", "L", "D", "OTW", "OTL"


@dataclass(frozen=True)
class LogGame:
    category: str
    season: str
    phase: str
    competition: str
    day: date
    url: str
    home: str
    away: str
    home_goals: int
    away_goals: int
    extra_time: bool
    events: tuple[dict, ...]


def result_letter(own: int, other: int, extra_time: bool) -> str:
    if own == other:
        return DRAW
    if own > other:
        return OT_WIN if extra_time else WIN
    return OT_LOSS if extra_time else LOSS


def _uid(value: object) -> str:
    return str(value or "").strip()


def build_game_logs(games: Iterable[LogGame]) -> dict[str, list[dict]]:
    """Player uid -> game rows, newest first."""
    lines: dict[tuple[str, str], dict] = {}
    for game in games:
        for event in game.events:
            if event.get("event_kind") != "goal" or event.get("side") not in ("home", "away"):
                continue
            if event.get("tag") == "own_goal":
                continue
            side = event["side"]
            for field, key in (("title_uid", "goals"), ("assist_uid", "assists")):
                uid = _uid(event.get(field))
                if not uid:
                    continue
                line = lines.setdefault((uid, game.url), _new_line(game, side))
                line[key] += 1
                if key == "goals" and event.get("situation") == sp.POWERPLAY:
                    line["pp"] += 1
                elif key == "goals" and event.get("situation") == sp.SHORTHANDED:
                    line["sh"] += 1
    logs: dict[str, list[dict]] = {}
    for (uid, _url), line in lines.items():
        line["points"] = line["goals"] + line["assists"]
        logs.setdefault(uid, []).append(line)
    for rows in logs.values():
        rows.sort(key=lambda row: (row["date"], row["url"]), reverse=True)
    return logs


def _new_line(game: LogGame, side: str) -> dict:
    home = side == "home"
    own, other = (game.home_goals, game.away_goals) if home else (game.away_goals, game.home_goals)
    return {
        "date": game.day.isoformat(),
        "season": game.season,
        "phase": game.phase,
        "competition": game.competition,
        "team": game.home if home else game.away,
        "opponent": game.away if home else game.home,
        "home": home,
        "score": f"{own}:{other}",
        "result": result_letter(own, other, game.extra_time),
        "url": game.url,
        "goals": 0,
        "assists": 0,
        "pp": 0,
        "sh": 0,
    }


def special_totals(rows: list[dict]) -> dict[str, int]:
    """Powerplay and shorthanded goals over a player's logged games."""
    return {"pp": sum(row["pp"] for row in rows), "sh": sum(row["sh"] for row in rows), "games": len(rows)}
