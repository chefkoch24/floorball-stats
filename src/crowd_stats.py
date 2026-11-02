"""Attendance analysis across leagues and seasons.

Pure functions on the played games of the published game articles (attendance as the
leagues report it). Behind the "Crowds" page: leagues compared for one season, the
development over seasons, weekday and kick-off time, and regular season against playoffs.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from statistics import median

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
# Kick-off bands by start hour; the label is what the page shows.
KICKOFF_BANDS = (("Before 14:00", 0, 14), ("14:00–16:59", 14, 17), ("17:00–18:59", 17, 19), ("19:00 or later", 19, 25))
REGULAR, PLAYOFFS = "regular-season", "playoffs"
TOP_TEAMS = 3
MIN_GAMES_PER_BUCKET = 3


@dataclass(frozen=True)
class CrowdGame:
    league: str
    season: str
    phase: str
    day: date
    start_time: str
    home: str
    away: str
    attendance: int
    url: str


def _average(values: list[int]) -> float:
    return sum(values) / len(values)


def kickoff_hour(start_time: str) -> int | None:
    try:
        return int(str(start_time).split(":", 1)[0])
    except (TypeError, ValueError):
        return None


def kickoff_band(start_time: str) -> str | None:
    hour = kickoff_hour(start_time)
    if hour is None:
        return None
    return next((label for label, low, high in KICKOFF_BANDS if low <= hour < high), None)


def _home_averages(games: list[CrowdGame]) -> dict[str, float]:
    per_team: dict[str, list[int]] = defaultdict(list)
    for game in games:
        per_team[game.home].append(game.attendance)
    return {team: _average(values) for team, values in per_team.items()}


def season_line(games: list[CrowdGame]) -> dict | None:
    """Figures for the games of one league and season; None without a single crowd number."""
    if not games:
        return None
    crowds = [game.attendance for game in games]
    teams = _home_averages(games)
    ranked = sorted(teams.values(), reverse=True)
    top = max(games, key=lambda game: game.attendance)
    total = sum(crowds)
    return {
        "games": len(games),
        "average": _average(crowds),
        "median": median(crowds),
        "total": total,
        "highest": top.attendance,
        "highest_game": {"home": top.home, "away": top.away, "url": top.url, "day": top.day.isoformat()},
        # Largest against smallest home average: how uneven the league's crowds are.
        "gradient": ranked[0] / ranked[-1] if len(ranked) > 1 and ranked[-1] > 0 else None,
        "top_share": sum(ranked[:TOP_TEAMS]) / sum(ranked) if len(ranked) > TOP_TEAMS else None,
        "teams": len(teams),
    }


def _change(current: float, previous: float | None) -> float | None:
    return (current - previous) / previous if previous else None


def like_for_like_change(current: list[CrowdGame], previous: list[CrowdGame]) -> tuple[float | None, int]:
    """Change of the average crowd against the previous season, and the games it compares.

    A running season is only compared with the same number of first regular-season games of
    the previous one, so a long season with playoffs and finals does not skew the change.
    """
    def regular(games: list[CrowdGame]) -> list[CrowdGame]:
        return sorted((game for game in games if game.phase == REGULAR), key=lambda game: (game.day, game.start_time))

    now, before = regular(current), regular(previous)[: len(regular(current))]
    if not now or not before:
        return None, 0
    return _change(_average([g.attendance for g in now]), _average([g.attendance for g in before])), len(before)


def _bucket_rows(games: list[CrowdGame], key, labels: tuple[str, ...]) -> list[dict]:
    buckets: dict[str, list[int]] = defaultdict(list)
    for game in games:
        label = key(game)
        if label is not None:
            buckets[label].append(game.attendance)
    return [
        {"label": label, "games": len(buckets[label]), "average": _average(buckets[label]), "enough": len(buckets[label]) >= MIN_GAMES_PER_BUCKET}
        for label in labels
        if label in buckets
    ]


def weekday_rows(games: list[CrowdGame]) -> list[dict]:
    return _bucket_rows(games, lambda game: WEEKDAYS[game.day.weekday()], WEEKDAYS)


def kickoff_rows(games: list[CrowdGame]) -> list[dict]:
    return _bucket_rows(games, lambda game: kickoff_band(game.start_time), tuple(label for label, _low, _high in KICKOFF_BANDS))


def phase_rows(games: list[CrowdGame]) -> list[dict]:
    names = {REGULAR: "Regular season", PLAYOFFS: "Playoffs"}
    return _bucket_rows(games, lambda game: names.get(game.phase), tuple(names.values()))


def league_analysis(games: list[CrowdGame], seasons: list[str]) -> dict | None:
    """Everything the page shows for one league. ``seasons`` is newest first.

    Games whose attendance is missing or zero must be left out by the caller.
    """
    by_season: dict[str, list[CrowdGame]] = defaultdict(list)
    for game in games:
        by_season[game.season].append(game)
    lines = {season: season_line(by_season[season]) for season in seasons if by_season.get(season)}
    if not lines:
        return None
    latest = next(season for season in seasons if season in lines)
    previous = next((season for season in seasons[seasons.index(latest) + 1:] if season in lines), None)
    current = lines[latest]
    current["change"], current["change_games"] = like_for_like_change(by_season[latest], by_season[previous] if previous else [])
    current["previous_season"] = previous
    latest_games = by_season[latest]
    return {
        "season": latest,
        "current": current,
        "seasons": [{"season": season, **lines[season]} for season in seasons if season in lines],
        "weekdays": weekday_rows(latest_games),
        "kickoffs": kickoff_rows(latest_games),
        "phases": phase_rows(latest_games),
    }
