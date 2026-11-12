import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src import build_search_index

ROOT = Path(__file__).resolve().parents[1]


def _page(path: Path, **meta: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{key}: {value}" for key, value in meta.items()) + "\n\nbody\n", encoding="utf-8")


def _label(slug: str) -> str:
    return f"label {slug}"


def _title(slug: str) -> str:
    if slug.startswith("se-"):
        return "Sweden · SSL"
    if slug.startswith("sew-"):
        return "Sweden · SSL Damer"
    return ""


@pytest.fixture()
def index(tmp_path):
    content = tmp_path / "content"
    for uid, name, team, season, points in (
        ("player-1", "Eppu Suhanto", "Oilers", "fi-26-27", "13"),
        ("player-2", "Old Timer", "Classic", "fi-24-25", "40"),
        ("player-3", "Young Star", "Oilers", "fi-26-27", "30"),
    ):
        _page(content / "players" / f"{uid}.md", Slug=uid, player=name, team=team, league="Finland",
              current_season=season, current_points=points)
    # Same club in three season/phase pages and in the women's league.
    for category in ("se-25-26-regular-season", "se-26-27-playoffs", "se-26-27-regular-season"):
        _page(content / category / "teams" / "storvreta.md", Slug=f"storvreta-{category}", team="Storvreta IBK",
              Category=f"{category}, teams")
        (content / category / "games").mkdir(parents=True, exist_ok=True)
    _page(content / "sew-26-27-regular-season" / "teams" / "storvreta.md", Slug="storvreta-w", team="Storvreta IBK",
          Category="sew-26-27-regular-season, teams")
    _page(content / "player-stats" / "se-26-27-regular-season-players.md", Slug="se-26-27-regular-season-players",
          type="player_stats")
    target = tmp_path / "index.json"
    build_search_index.build_search_index(str(content), str(target), seo_label=_label, league_title=_title)
    return json.loads(target.read_text())


def test_players_come_with_team_season_and_weight(index):
    players = [row for row in index["items"] if row["type"] == "player"]
    assert [row["name"] for row in players] == ["Young Star", "Eppu Suhanto", "Old Timer"]
    assert players[0]["subtitle"] == "Oilers · Finland · 2026/27"
    assert players[0]["url"] == "/player-3.html"
    assert players[0]["weight"] > players[2]["weight"]


def test_every_player_page_is_indexed(index):
    assert sum(row["type"] == "player" for row in index["items"]) == 3


def test_a_club_has_one_row_per_league_pointing_at_the_newest_page(index):
    teams = [row for row in index["items"] if row["type"] == "team"]
    assert sorted((row["subtitle"], row["url"]) for row in teams) == [
        ("Sweden · SSL Damer · 2026/27", "/storvreta-w.html"),
        ("Sweden · SSL · 2026/27", "/storvreta-se-26-27-regular-season.html"),
    ]


def test_leagues_cover_every_season_page_and_player_tables(index):
    leagues = [row for row in index["items"] if row["type"] == "league"]
    urls = {row["url"] for row in leagues}
    assert urls == {
        "/category/se-25-26-regular-season.html", "/category/se-26-27-playoffs.html",
        "/category/se-26-27-regular-season.html", "/category/sew-26-27-regular-season.html",
        "/category/se-26-27-regular-season-players.html",
    }
    current = next(row for row in leagues if row["url"].endswith("se-26-27-regular-season.html"))
    assert (current["name"], current["subtitle"]) == ("Sweden · SSL", "2026/27 · Regular season")
    tables = next(row for row in leagues if row["url"].endswith("-players.html"))
    assert tables["subtitle"] == "2026/27 · Player stats"
    # Current regular season ahead of the playoffs and of the previous season.
    order = [row["url"] for row in leagues]
    assert order.index("/category/se-26-27-regular-season.html") < order.index("/category/se-26-27-playoffs.html")
    assert order.index("/category/se-26-27-playoffs.html") < order.index("/category/se-25-26-regular-season.html")


def test_index_has_a_version_and_a_count(index):
    assert index["version"] == 2
    assert index["item_count"] == len(index["items"])


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_search_ranking_logic() -> None:
    """Runs tests/js/search-rank.test.js (node:test) against the ranking helper."""
    result = subprocess.run(
        ["node", "--test", str(ROOT / "tests" / "js" / "search-rank.test.js")],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_committed_index_has_all_three_kinds_and_every_player():
    index = json.loads((ROOT / "themes/my-theme/static/search/search-index.json").read_text())
    kinds = {row["type"] for row in index["items"]}
    assert kinds == {"player", "team", "league"}
    players = sum(row["type"] == "player" for row in index["items"])
    assert players == len(list((ROOT / "content/players").glob("*.md")))
