import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "plugins"))

import connect_feed as feed  # noqa: E402

FILTERS = {
    "crest_index": lambda name: len(name) % 8 + 1,
    "team_initials": lambda name: name[:3].upper(),
    "category2string": lambda slug: f"League {slug}",
    "league_context": lambda slug: {"division": "women" if slug.startswith("sew") else "men"},
    "fmt_time": lambda value, default="TBD": value or default,
}
SETTINGS = {
    "CURRENT_SEASON": "26-27",
    "SITEURL": "https://stats.example",
    "LEAGUES": [
        {"prefix": "se-", "name": "Sweden", "title": "Sweden · SSL", "division": "men"},
        {"prefix": "sew-", "name": "Sweden", "title": "Sweden · SSL Damer", "division": "women"},
    ],
}


def game(day, category="se-26-27-regular-season", state="scheduled", **meta):
    return SimpleNamespace(
        date=datetime(2026, 10, day, 18, 30), category=SimpleNamespace(shortname=category), url=f"g{day}.html",
        metadata={"type": "game", "home_team": "Pixbo IBK", "away_team": "Mullsjö AIS", "game_state": state, "start_time": "18:30", **meta},
        win_probability={"home_label": "62%", "away_label": "38%"},
    )


def test_games_cover_a_window_around_today_with_chances_for_upcoming_games() -> None:
    articles = [game(30), game(26, state="played", home_goals="5", away_goals="4", home_goals_in_overtime="1"), game(29, category="se-25-26-regular-season")]
    rows = feed.games(articles, SETTINGS, FILTERS, date(2026, 10, 30))
    assert [row["date"] for row in rows] == ["2026-10-30"]  # the 26th is more than three days back, last season is out
    row = rows[0]
    assert row["homeChance"] == "62%" and row["state"] == "scheduled"
    assert row["url"] == "https://stats.example/g30.html"
    played = feed.games([game(28, state="played", home_goals="5", away_goals="4", home_goals_in_overtime="1")], SETTINGS, FILTERS, date(2026, 10, 30))[0]
    assert (played["homeGoals"], played["awayGoals"], played["decision"], played["homeChance"]) == (5, 4, "OT", None)


def test_power_takes_the_top_of_each_current_league_by_division() -> None:
    rows = [{"power_rank": rank, "team": f"Team {rank}", "rating": 1800 - rank, "trend": None, "url": f"t{rank}.html"} for rank in range(1, 9)]
    insights = {"se-26-27-regular-season": {"power": {"rows": rows}}, "se-25-26-regular-season": {"power": {"rows": rows}}}
    out = feed.power(insights, SETTINGS, FILTERS)
    assert out["women"] == []
    league = out["men"][0]
    assert league["league"] == "SSL" and league["url"] == "https://stats.example/category/se-26-27-regular-season.html"
    assert [team["rank"] for team in league["teams"]] == [1, 2, 3, 4, 5]


def test_leaders_keep_points_and_goals_boards() -> None:
    boards = {"men": {"boards": [
        {"key": "points", "title": "Points", "unit": "P", "entries": [{"rank": 1, "name": "A", "team": "T", "value": "24", "code": "SWE", "url": "player-a.html"}]},
        {"key": "assists", "title": "Assists", "unit": "A", "entries": []},
    ]}}
    out = feed.leaders(boards, SETTINGS)
    assert [board["key"] for board in out["men"]] == ["points"]
    assert out["men"][0]["entries"][0]["url"] == "https://stats.example/player-a.html"
