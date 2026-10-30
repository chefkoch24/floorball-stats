"""What is at stake in an upcoming game, in one sentence.

Input is ``power_rankings.simulate_season(stakes=...)``: for each team of a
game its chance (now, after a win, after a loss) to finish first, to reach the
playoffs and to win the title. The first situation that applies picks the
sentence; its wording rotates between two or three variants by game id, so
neighbouring games read differently but every build writes the same text.

Situations, in order: securing a playoff place, playoff hopes almost over, a
duel at the playoff line, a big playoff swing, the title race, first place.
When nothing much changes there is no sentence.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass

CLINCH = 0.995
OUT = 0.005
# "Secures" and "all but over" only when the place is really open today.
OPEN_LOW, OPEN_HIGH = 0.05, 0.95
DUEL_LOW, DUEL_HIGH = 0.2, 0.8
PLAYOFF_SWING = 0.15
TITLE_SWING = 0.08
FIRST_SWING = 0.10

TEMPLATES = {
    "clinch": [
        "A win secures {team}'s playoff place.",
        "{team} can lock up a playoff place with a win.",
        "Win and {team} are in the playoffs for sure.",
    ],
    "out": [
        "Lose and {team}'s playoff hopes are all but over.",
        "{team} need points: a loss leaves almost no way into the playoffs.",
    ],
    "duel": [
        "Six-pointer at the playoff line: {home} at {home_now}, {away} at {away_now}.",
        "Both teams are fighting for the playoffs: {home} {home_now}, {away} {away_now}.",
    ],
    "swing": [
        "A win lifts {team}'s playoff chance from {now} to {win}, a loss drops it to {loss}.",
        "{team}'s playoff chance: {now} today, {win} with a win, {loss} with a loss.",
        "Big one for {team}: a win means a {win} playoff chance, a loss {loss}.",
    ],
    "title": [
        "A title-race game: {team}'s championship odds move between {loss} and {win}.",
        "The title race is on: {team} win the championship in {win} of simulated seasons after a win, {loss} after a loss.",
    ],
    "first": [
        "It's about first place: a win puts {team}'s chance of topping the table at {win}, a loss at {loss}.",
        "First place in sight: {team} finish top in {win} of simulated seasons with a win, {loss} with a loss.",
    ],
    "headline": [
        "Game of the week",
        "The game that matters most this week",
        "Biggest stakes this week",
    ],
}


def percent(value: float) -> str:
    if 0.995 <= value < 1:
        return ">99%"
    if 0 < value < 0.005:
        return "<1%"
    return f"{value * 100:.0f}%"


@dataclass
class Stake:
    situation: str
    sentence: str
    weight: float  # how much the game moves, for picking the game of the week


def _variant(situation: str, game_id: str) -> str:
    options = TEMPLATES[situation]
    return options[zlib.crc32(f"{situation}:{game_id}".encode("utf-8")) % len(options)]


def _swing(metric) -> float:
    if not metric or metric[1] is None or metric[2] is None:
        return 0.0
    return metric[1] - metric[2]


def describe(game_id: str, home: str, away: str, stakes: dict) -> Stake | None:
    teams = {"home": home, "away": away}
    weight = sum(abs(_swing(stakes[side].get(name))) * factor for side in teams for name, factor in (("playoffs", 1.0), ("title", 1.0), ("first", 0.5)))

    def pick(situation: str, side: str, metric: tuple | None = None, **extra) -> Stake:
        values = {}
        if metric:
            values = {"now": percent(metric[0]), "win": percent(metric[1]), "loss": percent(metric[2])}
        text = _variant(situation, game_id).format(team=teams[side], home=home, away=away, **values, **extra)
        return Stake(situation=situation, sentence=text, weight=weight)

    # The team with more at stake leads the sentence.
    sides = sorted(teams, key=lambda side: -abs(_swing(stakes[side].get("playoffs"))))
    for side in sides:
        playoffs = stakes[side].get("playoffs")
        if playoffs and playoffs[1] is not None and playoffs[1] >= CLINCH and playoffs[0] <= OPEN_HIGH:
            return pick("clinch", side)
    for side in sides:
        playoffs = stakes[side].get("playoffs")
        if playoffs and playoffs[2] is not None and playoffs[2] <= OUT and playoffs[0] >= OPEN_LOW:
            return pick("out", side)
    home_playoffs, away_playoffs = stakes["home"].get("playoffs"), stakes["away"].get("playoffs")
    if home_playoffs and away_playoffs and all(DUEL_LOW <= metric[0] <= DUEL_HIGH for metric in (home_playoffs, away_playoffs)):
        return pick("duel", "home", home_now=percent(home_playoffs[0]), away_now=percent(away_playoffs[0]))
    side = sides[0]
    if abs(_swing(stakes[side].get("playoffs"))) >= PLAYOFF_SWING:
        return pick("swing", side, stakes[side]["playoffs"])
    by_title = sorted(teams, key=lambda side: -abs(_swing(stakes[side].get("title"))))
    if abs(_swing(stakes[by_title[0]].get("title"))) >= TITLE_SWING:
        return pick("title", by_title[0], stakes[by_title[0]]["title"])
    by_first = sorted(teams, key=lambda side: -abs(_swing(stakes[side].get("first"))))
    if abs(_swing(stakes[by_first[0]].get("first"))) >= FIRST_SWING:
        return pick("first", by_first[0], stakes[by_first[0]]["first"])
    return None


def headline(game_id: str) -> str:
    return _variant("headline", game_id)
