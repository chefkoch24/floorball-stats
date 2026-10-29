"""Clutch stats, scoring duos, Elo power ratings and season projections.

Runs at build time on the published game articles, like ``share_assets``: every
game article already carries its full event payload (``game_events_b64``) and
result, so no extra pipeline step or league refresh is needed and all leagues
stay in sync with their pages. The calculations live in ``src/player_insights.py``
and ``src/power_rankings.py`` so a pipeline step can reuse them later.

Attaches to articles:
- player: ``clutch`` (this season and all tracked games) and ``partners``
- team (current season): ``power`` (rating, rank, trend, projection, sparkline),
  ``duos`` and ``clutch_players``
- game: ``win_probability`` (pre-game, from the ratings before that game) and
  moment labels (game winner, clutch, overtime) inside ``game_events_b64``

and ``LEAGUE_INSIGHTS[category slug]`` to the template context for league pages.
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

CONFIG_DIR = ROOT / "config" / "leagues"
CATEGORY_PATTERN = re.compile(r"^(?P<prefix>[a-z]*-?)(?P<season>\d{2}-\d{2})-(?P<phase>regular-season|playoffs)$")
# A probability is only shown once both teams have this many rated games behind them.
MIN_RATED_GAMES = 3
UPSET_THRESHOLD = 0.35
TREND_DAYS = 7
SIMULATIONS = 4000
SPARK_WIDTH, SPARK_HEIGHT = 240, 48


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
    generator.context["LEAGUE_INSIGHTS"] = dict(league_context)


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

        category = f"{prefix}{current_season}-regular-season"
        team_articles = teams_by_category.get(category, [])
        season_results = [result for result in results if result.season == current_season and result.phase == "regular-season"]
        if not team_articles or not any(result.played for result in season_results):
            continue
        _league_power(prefix, category, current_season, run, results, season_results, team_articles, entries, league_context)


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
