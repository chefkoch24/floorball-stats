"""Clutch stats, scoring duos, Elo power ratings and season projections.

Runs at build time on the published game articles, like ``share_assets``: every
game article already carries its full event payload (``game_events_b64``) and
result, so no extra pipeline step or league refresh is needed and all leagues
stay in sync with their pages. The calculations live in ``src/player_insights.py``
and ``src/power_rankings.py`` so a pipeline step can reuse them later.

Attaches to articles:
- player: ``clutch`` (this season and all tracked games) and ``partners``
- team (current season): ``power`` (rating, rank, trend, projection, sparkline),
  ``duos`` and ``clutch_players``; every regular-season team: ``table_history``
- game: ``win_probability`` (pre-game, from the ratings before that game),
  ``game_story`` (live win chance line, lead changes, key moments, excitement) and
  moment labels (game winner, clutch, overtime) inside ``game_events_b64``

and ``LEAGUE_INSIGHTS[category slug]`` (with ``table_history`` for every regular
season) to the template context for league pages.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from pelican import signals

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import player_insights as pi  # noqa: E402
from src import power_rankings as pr  # noqa: E402
from src import standings_history as sh  # noqa: E402
from src import game_flow as gf  # noqa: E402

CONFIG_DIR = ROOT / "config" / "leagues"
CATEGORY_PATTERN = re.compile(r"^(?P<prefix>[a-z]*-?)(?P<season>\d{2}-\d{2})-(?P<phase>regular-season|playoffs)$")
# A probability is only shown once both teams have this many rated games behind them.
MIN_RATED_GAMES = 3
UPSET_THRESHOLD = 0.35
TREND_DAYS = 7
SIMULATIONS = 4000
SPARK_WIDTH, SPARK_HEIGHT = 240, 48
# Table history chart: rows in CSS pixels (one per table place), rounds spread over a
# 0..BUMP_WIDTH viewBox that the page stretches to the column width.
BUMP_ROW, BUMP_PAD, BUMP_WIDTH = 24, 10, 1000
# Game story chart: win chance from top (home 100%) to bottom (away 100%).
STORY_WIDTH, STORY_HEIGHT = 1000, 180


def _meta(article, key: str, default: str = "") -> str:
    value = getattr(article, key, default)
    if isinstance(value, list):
        value = value[0] if value else default
    text = str(value if value is not None else default).strip()
    return "" if text in {"None", "nan", "n.a."} else text


def _int(article, key: str) -> int | None:
    try:
        return int(float(_meta(article, key)))
    except ValueError:
        return None


def _category(article) -> str:
    return article.category.slug if article.category else ""


def _decision(article) -> str:
    result = _meta(article, "result_string")
    if (_int(article, "home_goals_in_penalty_shootout") or 0) + (_int(article, "away_goals_in_penalty_shootout") or 0) or "n.P" in result:
        return pr.SHOOTOUT
    if (_int(article, "home_goals_in_overtime") or 0) + (_int(article, "away_goals_in_overtime") or 0) or "n.V" in result:
        return pr.OVERTIME
    return pr.REGULATION


def _player_link(player: pi.PlayerRef, player_slugs: set[str]) -> dict:
    return {"name": player.name, "url": f"{player.uid}.html" if player.uid in player_slugs else ""}


def _percent(value: float | None) -> str:
    if value is None:
        return "–"
    if value >= 0.995 and value < 1:
        return ">99%"
    if 0 < value < 0.005:
        return "<1%"
    return f"{value * 100:.0f}%"


def _playoff_format(prefix: str, season: str) -> tuple[int | None, list[pr.PlayoffRound]]:
    """Playoff places and rounds from ``config/leagues`` (None when the league has no playoff config)."""
    for path in sorted(CONFIG_DIR.glob("*.json")):
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if config.get("season") != f"{prefix}{season}" or config.get("phase") != "playoffs":
            continue
        rounds = [
            pr.PlayoffRound(name=item.get("name", ""), teams=int(item["teams"]), wins_to_advance=int(item.get("wins_to_advance", 1)))
            for item in config.get("playoff_rounds", [])
            if item.get("teams")
        ]
        places = config.get("playoff_teams_count") or (rounds[0].teams if rounds else None)
        return (int(places) if places else None), rounds
    return None, []


def _sparkline(points: list[float]) -> str:
    if len(points) < 2:
        return ""
    low, high = min(points), max(points)
    span = max(high - low, 1.0)
    step = SPARK_WIDTH / (len(points) - 1)
    return " ".join(
        f"{index * step:.1f},{(SPARK_HEIGHT - 4) - (value - low) / span * (SPARK_HEIGHT - 8):.1f}" for index, value in enumerate(points)
    )


def _clutch_rows(leaders, player_slugs: set[str]) -> list[dict]:
    return [{**_player_link(player, player_slugs), "team": team, **line.as_dict()} for player, team, line in leaders]


def _duo_rows(duos: list[pi.Duo], player_slugs: set[str]) -> list[dict]:
    return [
        {
            "first": _player_link(duo.first, player_slugs),
            "second": _player_link(duo.second, player_slugs),
            "team": duo.team,
            "goals": duo.goals,
            "first_to_second": duo.first_to_second,
            "second_to_first": duo.second_to_first,
        }
        for duo in duos
    ]


def collect(generator) -> None:
    settings = generator.settings
    current_season = settings.get("CURRENT_SEASON", "")
    articles = list(generator.articles)
    player_slugs = {article.slug for article in articles if _meta(article, "type") == "player"}

    games_by_category: dict[str, list] = defaultdict(list)
    teams_by_category: dict[str, list] = defaultdict(list)
    for article in articles:
        kind = _meta(article, "type")
        if kind == "game":
            games_by_category[_category(article)].append(article)
        elif kind == "team":
            teams_by_category[_category(article)].append(article)

    league_context: dict[str, dict] = defaultdict(dict)
    _attach_player_insights(articles, games_by_category, teams_by_category, player_slugs, league_context)
    _attach_power(games_by_category, teams_by_category, current_season, league_context)
    _attach_table_history(games_by_category, teams_by_category, settings["JINJA_FILTERS"]["crest_index"], league_context)
    generator.context["LEAGUE_INSIGHTS"] = dict(league_context)
    # Parameters and limits for the "How our stats work" page, so it always matches the code.
    generator.context["INSIGHTS_MODEL"] = {
        **pr.model_parameters(),
        "simulations": SIMULATIONS,
        "upset_threshold": UPSET_THRESHOLD,
        "min_rated_games": MIN_RATED_GAMES,
        "trend_days": TREND_DAYS,
        "late_minute": pi.PERIOD_MINUTES * pi.REGULATION_PERIODS - pi.LATE_MINUTE_IN_PERIOD,
        "round_gap_days": sh.ROUND_GAP_DAYS,
    }


def _attach_player_insights(articles, games_by_category, teams_by_category, player_slugs, league_context) -> None:
    games = []
    game_articles = {}
    for category, items in games_by_category.items():
        season = pi.season_of(category)
        for article in items:
            if _meta(article, "game_state") != "played":
                continue
            events = pi.decode_events(_meta(article, "game_events_b64"))
            if not events:
                continue
            game_id = _meta(article, "game_id") or article.slug
            games.append(pi.GameEvents(category=category, season=season, game_id=game_id, events=events))
            game_articles[(category, game_id)] = (article, events)

    insights = pi.build_insights(games)

    for key, flagged in insights.moments.items():
        article, events = game_articles[key]
        article.game_events_b64 = pi.encode_events(pi.label_moments(events, flagged))

    for article in articles:
        kind = _meta(article, "type")
        if kind == "player":
            uid = _meta(article, "player_uid") or article.slug
            season = _meta(article, "current_season")
            season_line = insights.clutch.get(season, {}).get(uid)
            total_line = insights.clutch.get("all", {}).get(uid)
            if total_line is None:
                continue
            article.clutch = {
                "season": season,
                "season_line": season_line.as_dict() if season_line else None,
                "all": total_line.as_dict(),
            }
            article.partners = [
                {**_player_link(partner, player_slugs), "goals_from": goals_from, "assists_to": assists_to}
                for partner, goals_from, assists_to in insights.partners(season, uid)
            ]
        elif kind == "team":
            category = _category(article)
            team = _meta(article, "team") or _meta(article, "title")
            duos = insights.top_duos(category, team=team, limit=5)
            article.duos = _duo_rows(duos, player_slugs)
            leaders = [item for item in insights.clutch_leaders(category, limit=200) if item[1] == team][:3]
            article.clutch_players = _clutch_rows(leaders, player_slugs)

    for category in teams_by_category:
        league_context[category]["clutch_leaders"] = _clutch_rows(insights.clutch_leaders(category, limit=5), player_slugs)
        league_context[category]["duos"] = _duo_rows(insights.top_duos(category, limit=5), player_slugs)


def _game_result(article, season: str, phase: str) -> pr.GameResult:
    played = _meta(article, "game_state") == "played"
    return pr.GameResult(
        game_id=_meta(article, "game_id") or article.slug,
        season=season,
        phase=phase,
        day=pr.to_date(article.date),
        order=_meta(article, "start_time"),
        home=_meta(article, "home_team"),
        away=_meta(article, "away_team"),
        played=played,
        home_goals=_int(article, "home_goals") or 0,
        away_goals=_int(article, "away_goals") or 0,
        decision=_decision(article) if played else pr.REGULATION,
        home_points=_int(article, "home_points"),
        away_points=_int(article, "away_points"),
    )


def _attach_power(games_by_category, teams_by_category, current_season, league_context) -> None:
    chains: dict[str, list[tuple]] = defaultdict(list)
    for category, items in games_by_category.items():
        match = CATEGORY_PATTERN.match(category)
        if not match:
            continue
        for article in items:
            if not _meta(article, "home_team") or not _meta(article, "away_team"):
                continue
            chains[match["prefix"]].append((article, _game_result(article, match["season"], match["phase"])))

    for prefix, entries in chains.items():
        results = [result for _, result in entries]
        run = pr.run_elo(results)
        experience: dict[str, int] = defaultdict(int)
        for article, result in sorted(entries, key=lambda item: (item[1].season, item[1].sort_key)):
            home_rating, away_rating, p_home = run.pregame[result.game_id]
            rated = min(experience[result.home], experience[result.away]) >= MIN_RATED_GAMES
            if result.played:
                experience[result.home] += 1
                experience[result.away] += 1
            if not rated:
                continue
            winner_p = None
            if result.played and result.home_goals != result.away_goals:
                winner_p = p_home if result.home_goals > result.away_goals else 1 - p_home
            article.win_probability = {
                "home": p_home,
                "away": 1 - p_home,
                "home_label": _percent(p_home),
                "away_label": _percent(1 - p_home),
                "home_rating": round(home_rating),
                "away_rating": round(away_rating),
                "played": result.played,
                "upset": winner_p is not None and winner_p < UPSET_THRESHOLD,
                "winner_label": _percent(winner_p) if winner_p is not None else "",
            }

        _attach_game_stories(entries, run, league_context)

        category = f"{prefix}{current_season}-regular-season"
        team_articles = teams_by_category.get(category, [])
        season_results = [result for result in results if result.season == current_season and result.phase == "regular-season"]
        if not team_articles or not any(result.played for result in season_results):
            continue
        _league_power(prefix, category, current_season, run, results, season_results, team_articles, entries, league_context)


def _clock(minute: float) -> str:
    if minute > gf.REGULATION_MINUTES:
        rest = minute - gf.REGULATION_MINUTES
        return f"OT {int(rest):02d}:{round((rest % 1) * 60):02d}"
    seconds = round(minute * 60)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _story_goals(article) -> list[gf.FlowGoal]:
    """Goals in play order from the event payload, or from the timeline fields when a game has no events."""
    goals = []
    for index, event in enumerate(pi.decode_events(_meta(article, "game_events_b64"))):
        if event.get("event_kind") != "goal" or event.get("side") not in ("home", "away"):
            continue
        try:
            period = int(event.get("period") or 0)
        except (TypeError, ValueError):
            continue
        if period < 1 or period >= pi.SHOOTOUT_PERIOD or str(event.get("minute") or "").upper().startswith("PS"):
            continue
        in_period = pi.minute_in_period(event.get("minute"), period)
        if in_period is None:
            continue
        scorer = "Own goal" if event.get("tag") == pi.OWN_GOAL_TAG else str(event.get("title") or "")
        goals.append(gf.FlowGoal(minute=gf.goal_minute(period, in_period), side=event["side"], scorer=scorer, index=index))
    if goals:
        return goals
    minutes = [float(value) for value in _meta(article, "timeline_minutes_csv").split(",") if value.strip()]
    diffs = [int(float(value)) for value in _meta(article, "timeline_diffs_csv").split(",") if value.strip()]
    for position in range(1, min(len(minutes), len(diffs))):
        side = "home" if diffs[position] > diffs[position - 1] else "away"
        goals.append(gf.FlowGoal(minute=minutes[position], side=side))
    return goals


def _penalty_bands(article, side: str, end: float) -> list[dict]:
    starts = [float(value) for value in _meta(article, f"{side}_penalty_minutes_csv").split(",") if value.strip()]
    ends = [float(value) for value in _meta(article, f"{side}_penalty_ends_csv").split(",") if value.strip()]
    bands = []
    for position, start in enumerate(starts):
        stop = ends[position] if position < len(ends) else start + 2
        stop = max(stop, start + 0.3)
        bands.append({"x": round(start / end * STORY_WIDTH, 1), "w": round((stop - start) / end * STORY_WIDTH, 1)})
    return bands


def _attach_game_stories(entries, run: pr.EloRun, league_context) -> None:
    by_category: dict[str, list] = defaultdict(list)
    for article, result in entries:
        if not result.played:
            continue
        goals = _story_goals(article)
        if not goals:
            continue
        pregame = run.pregame[result.game_id][2]
        timeline_end = float(_meta(article, "timeline_max_minute") or gf.REGULATION_MINUTES)
        story = gf.game_story(pregame, goals, result.home_goals, result.away_goals, timeline_end)
        end = story.end_minute

        def x(minute: float) -> float:
            return round(minute / end * STORY_WIDTH, 1)

        def y(chance: float) -> float:
            return round((1 - chance) * STORY_HEIGHT, 1)

        teams = {"home": result.home, "away": result.away}
        line = " ".join(f"{x(minute)},{y(chance)}" for minute, chance in story.points)
        mid = STORY_HEIGHT / 2
        article.game_story = {
            "width": STORY_WIDTH,
            "height": STORY_HEIGHT,
            "line": line,
            "area": f"0,{mid} {line} {STORY_WIDTH},{mid}",
            "periods": [x(minute) for minute in (20.0, 40.0, 60.0) if minute < end],
            "period_labels": [
                {"label": label, "left": round((start + stop) / 2 / end * 100, 2)}
                for label, start, stop in (("P1", 0, 20), ("P2", 20, 40), ("P3", 40, 60), ("OT", 60, end))
                if start < end
            ],
            "goals": [
                {"x": x(goal.minute), "y": y(chance), "side": goal.side, "title": f"{_clock(goal.minute)} {score} {goal.scorer or teams[goal.side]}"}
                for goal, score, chance in story.goals
            ],
            "penalties": {side: _penalty_bands(article, side, end) for side in ("home", "away")},
            "lead_changes": story.lead_changes,
            "ties": story.ties,
            "largest_lead": story.largest_lead,
            "comeback": story.comeback,
            "winner": teams.get(story.winner, ""),
            "excitement": story.excitement,
            "key_moments": [
                {
                    "clock": _clock(moment.goal.minute),
                    "team": teams[moment.goal.side],
                    "scorer": moment.goal.scorer,
                    "score": moment.score,
                    "before": _percent(moment.before if moment.goal.side == "home" else 1 - moment.before),
                    "after": _percent(moment.after if moment.goal.side == "home" else 1 - moment.after),
                }
                for moment in story.key_moments
                if moment.swing >= 0.05
            ],
        }
        by_category[_category(article)].append(article)

    # Excitement is read against the other games of the same season phase.
    for category, articles in by_category.items():
        values = sorted(article.game_story["excitement"] for article in articles)
        for article in articles:
            below = sum(1 for value in values if value < article.game_story["excitement"])
            article.game_story["percentile"] = round(100 * below / max(1, len(values) - 1)) if len(values) > 1 else None
        dramatic = sorted(articles, key=lambda article: -article.game_story["excitement"])[:3]
        league_context[category]["most_exciting"] = [
            {
                "url": article.url,
                "home": _meta(article, "home_team"),
                "away": _meta(article, "away_team"),
                "score": f"{_int(article, 'home_goals')}:{_int(article, 'away_goals')}",
                "date": article.date,
                "lead_changes": article.game_story["lead_changes"],
                "comeback": article.game_story["comeback"],
            }
            for article in dramatic
        ]


def _attach_table_history(games_by_category, teams_by_category, crest_index, league_context) -> None:
    for category, team_articles in teams_by_category.items():
        match = CATEGORY_PATTERN.match(category)
        if not match or match["phase"] != "regular-season":
            continue
        teams = {(_meta(article, "team") or _meta(article, "title")): article for article in team_articles}
        played = []
        for article in games_by_category.get(category, []):
            result = _game_result(article, match["season"], match["phase"])
            if not result.played or result.home not in teams or result.away not in teams:
                continue
            home_points, away_points = result.home_points, result.away_points
            if home_points is None or away_points is None:
                home_points, away_points = _default_points(result)
            played.append(
                sh.PlayedGame(result.day, result.home, result.away, result.home_goals, result.away_goals, home_points, away_points)
            )
        official = {team: _int(article, "rank") for team, article in teams.items()}
        history = sh.standings_history(played, teams, {team: rank for team, rank in official.items() if rank is not None})
        if len(history.rounds) < 2:
            continue
        league_context[category]["table_history"] = _bump_chart(history, teams, crest_index)
        for team, article in teams.items():
            positions = history.positions.get(team, [])
            article.table_history = {
                "chart": _bump_chart(history, teams, crest_index, highlight=team),
                "best": history.best(team),
                "worst": history.worst(team),
                "now": positions[-1] if positions else None,
                "rounds": len(history.rounds),
            }


def _default_points(result: pr.GameResult) -> tuple[int, int]:
    points = pr.DEFAULT_POINTS
    if result.home_goals == result.away_goals:
        return points["draw"], points["draw"]
    win, loss = ("win", "loss") if result.decision == pr.REGULATION else ("extra_win", "extra_loss")
    return (points[win], points[loss]) if result.home_goals > result.away_goals else (points[loss], points[win])


def _bump_chart(history: sh.StandingsHistory, teams: dict, crest_index, highlight: str | None = None) -> dict:
    """Geometry for the table history: one polyline per team, place 1 at the top."""
    count = len(history.positions)
    rounds = len(history.rounds)
    height = BUMP_PAD * 2 + BUMP_ROW * (count - 1)

    def x(index: int) -> float:
        return round(index * BUMP_WIDTH / (rounds - 1), 1)

    def y(position: int) -> int:
        return BUMP_PAD + (position - 1) * BUMP_ROW

    tick_every = 1 if rounds <= 12 else (2 if rounds <= 24 else 5)
    ticks = [
        {"label": round_.number, "left": round(index * 100 / (rounds - 1), 2)}
        for index, round_ in enumerate(history.rounds)
        if round_.number == 1 or round_.number % tick_every == 0 or index == rounds - 1
    ]
    lines = []
    # The followed team is drawn last, so it lies on top.
    ordered = sorted(history.positions.items(), key=lambda item: (item[0] == highlight, -(item[1][-1] if item[1] else 0)))
    for team, positions in ordered:
        if not positions:
            continue
        article = teams.get(team)
        lines.append(
            {
                "team": team,
                "url": article.url if article is not None else "",
                "crest": crest_index(team),
                "active": team == highlight,
                "points": " ".join(f"{x(index)},{y(position)}" for index, position in enumerate(positions)),
                "dots": [{"x": x(index), "y": y(position)} for index, position in enumerate(positions)],
                "end_y": y(positions[-1]),
                "now": positions[-1],
                "summary": f"{team}: " + ", ".join(str(position) for position in positions),
            }
        )
    return {
        "width": BUMP_WIDTH,
        "height": height,
        "rows": [{"position": position, "y": y(position)} for position in range(1, count + 1)],
        "ticks": ticks,
        "lines": lines,
        "labels": sorted(lines, key=lambda line: line["now"]),
        "rounds": rounds,
        "last_day": history.rounds[-1].last_day,
    }


def _league_power(prefix, category, current_season, run, results, season_results, team_articles, entries, league_context):
    teams = {(_meta(article, "team") or _meta(article, "title")): article for article in team_articles}
    ratings = {team: run.ratings.get(team, pr.BASE_RATING) for team in teams}
    power_order = sorted(teams, key=lambda team: (-ratings[team], team))
    power_rank = {team: position + 1 for position, team in enumerate(power_order)}

    latest = max(result.day for result in season_results if result.played)
    cutoff = latest - timedelta(days=TREND_DAYS - 1)
    earlier_results = [result for result in results if result.played and result.day < cutoff]
    trend: dict[str, float] = {}
    previous_rank: dict[str, int] = {}
    if any(result.season == current_season for result in earlier_results):
        earlier = pr.run_elo(earlier_results).ratings
        before = {team: earlier.get(team, pr.BASE_RATING) for team in teams}
        trend = {team: ratings[team] - before[team] for team in teams}
        previous_rank = {team: position + 1 for position, team in enumerate(sorted(teams, key=lambda team: (-before[team], team)))}

    remaining = [result for result in season_results if not result.played]
    playoffs_started = any(result.played and result.phase == "playoffs" and result.season == current_season for result in results)
    places, rounds = _playoff_format(prefix, current_season)
    projections = {}
    if not playoffs_started:
        model = pr.league_model([result for result in results if result.phase == "regular-season"])
        points_now = {team: _int(article, "points") or 0 for team, article in teams.items()}
        goal_diff = {team: _int(article, "goal_difference") or 0 for team, article in teams.items()}
        simulated = pr.simulate_season(
            ratings,
            points_now,
            goal_diff,
            remaining,
            model,
            playoff_teams=places or 0,
            rounds=rounds if places else (),
            simulations=SIMULATIONS,
            seed=category,
        )
        projections = {item.team: item for item in simulated}

    season_ids = {result.game_id for result in season_results}
    played_in_order = sorted((result for result in season_results if result.played), key=lambda result: result.sort_key)
    histories = {}
    for team in teams:
        season_points = [value for _, value, game_id in run.history.get(team, []) if game_id in season_ids]
        first_game = next((result for result in played_in_order if team in (result.home, result.away)), None)
        if first_game is not None:
            home_rating, away_rating, _ = run.pregame[first_game.game_id]
            season_points.insert(0, home_rating if first_game.home == team else away_rating)
        histories[team] = season_points

    rows = []
    for team in power_order:
        projection = projections.get(team)
        article = teams[team]
        change = trend.get(team)
        rank_change = (previous_rank[team] - power_rank[team]) if team in previous_rank else None
        row = {
            "team": team,
            "url": article.url,
            "power_rank": power_rank[team],
            "teams": len(teams),
            "rating": round(ratings[team]),
            "trend": round(change) if change is not None else None,
            "rank_change": rank_change,
            "table_rank": _meta(article, "rank"),
            "points": _int(article, "points") or 0,
            "projected_points": round(projection.projected_points) if projection else None,
            "first": _percent(projection.first) if projection else "–",
            "top4": _percent(projection.top4) if projection else "–",
            "playoffs": _percent(projection.playoffs) if projection and places else "–",
            "title": _percent(projection.title) if projection and projection.title is not None else "–",
            "spark": _sparkline(histories.get(team, [])),
            "season_start": round(histories[team][0]) if histories.get(team) else None,
        }
        article.power = row
        rows.append(row)

    upsets = []
    for article, result in entries:
        probability = getattr(article, "win_probability", None)
        if result.season != current_season or result.phase != "regular-season" or not probability or not probability["upset"]:
            continue
        winner_home = result.home_goals > result.away_goals
        upsets.append(
            {
                "url": article.url,
                "winner": result.home if winner_home else result.away,
                "loser": result.away if winner_home else result.home,
                "score": f"{max(result.home_goals, result.away_goals)}:{min(result.home_goals, result.away_goals)}",
                "chance": probability["winner_label"],
                "p": probability["home"] if winner_home else probability["away"],
                "date": article.date,
            }
        )
    upsets.sort(key=lambda item: item["p"])

    league_context[category]["power"] = {
        "rows": rows,
        "remaining": len(remaining),
        "simulated": bool(projections),
        "places": places,
        "has_title": bool(projections) and bool(rounds) and bool(places),
        "playoffs_started": playoffs_started,
        "simulations": SIMULATIONS,
        "upsets": upsets[:3],
    }


def register() -> None:
    signals.article_generator_finalized.connect(collect)
