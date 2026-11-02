import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins"))

import player_compare  # noqa: E402
from src import player_compare as pc  # noqa: E402


def _meta(**overrides):
    meta = {
        "player": "Janne Autio", "title": "Janne Autio", "player_uid": "player-03f5", "slug": "player-03f5",
        "team": "SPV", "league": "Finland", "season_count": "2", "current_season": "fi-26-27",
        "current_games": "4", "current_goals": "1", "current_assists": "3", "current_points": "4", "current_pim": "0",
        "career_games": "17", "career_goals": "12", "career_assists": "7", "career_points": "19", "career_pim": "2",
    }
    meta.update(overrides)
    return meta


def _article(uid="player-03f5", **extra):
    values = {"type": "player", "slug": uid, **_meta(player_uid=uid, slug=uid), **extra}
    return SimpleNamespace(**values)


def test_season_label_reads_club_and_tournament_seasons():
    assert pc.season_label("fi-26-27") == "2026/27"
    assert pc.season_label("26-27") == "2026/27"
    assert pc.season_label("sew-25-26") == "2025/26"
    assert pc.season_label("wfc-2024") == "2024"
    assert pc.season_label("") == ""


def test_index_row_is_short_and_follows_the_field_order():
    row = pc.index_row(_meta())
    assert dict(zip(pc.INDEX_FIELDS, row)) == {
        "uid": "player-03f5", "name": "Janne Autio", "team": "SPV", "league": "Finland",
        "season": "fi-26-27", "games": 17,
    }


def test_the_page_slug_identifies_a_player_even_when_two_pages_share_a_player_uid():
    meta = _meta(slug="player-dcc8", player_uid="player-e950")
    assert pc.index_row(meta)[0] == "player-dcc8"
    payload = pc.player_payload(meta)
    assert (payload["uid"], payload["url"]) == ("player-dcc8", "player-dcc8.html")


def test_index_row_falls_back_to_the_latest_season_without_career_totals():
    row = pc.index_row(_meta(career_games="", career_points="None"))
    assert row[5:] == [4]


def test_index_orders_regulars_first():
    rows = [["a", "Zed", "T", "L", "s", 5], ["b", "Bob", "T", "L", "s", 40], ["c", "Amy", "T", "L", "s", 40]]
    payload = pc.index_payload(rows)
    assert [row[0] for row in payload["players"]] == ["c", "b", "a"]
    assert payload["fields"] == list(pc.INDEX_FIELDS)


def test_player_payload_carries_totals_clutch_and_share():
    clutch = {
        "season": "fi-26-27",
        "season_line": {"gwg": 1, "clutch_points": 2, "game_changing": 3, "goals": 9},
        "all": {"gwg": 2, "clutch_points": 5, "game_changing": 6, "goals": 20},
    }
    trends = {"share": 21, "points": 4, "team_goals": 19, "point_streak": 3}
    payload = pc.player_payload(_meta(), clutch=clutch, trends=trends, team_url="12-spv.html")
    assert payload["uid"] == "player-03f5"
    assert payload["url"] == "player-03f5.html"
    assert payload["team_url"] == "12-spv.html"
    assert payload["season_label"] == "2026/27"
    assert payload["seasons"] == 2
    assert payload["current"] == {"games": 4, "goals": 1, "assists": 3, "points": 4, "pim": 0}
    assert payload["career"] == {"games": 17, "goals": 12, "assists": 7, "points": 19, "pim": 2}
    assert payload["clutch"] == {"current": {"gwg": 1, "clutch_points": 2, "game_changing": 3}, "all": {"gwg": 2, "clutch_points": 5, "game_changing": 6}}
    assert payload["share"] == {"share": 21, "points": 4, "team_goals": 19}


def test_repeated_clubs_of_a_season_are_listed_once():
    meta = _meta(team="Storvreta IBK / Visby IBK / Visby IBK / Storvreta IBK", league="Sweden / Sweden")
    assert pc.index_row(meta)[2:4] == ["Storvreta IBK / Visby IBK", "Sweden"]
    assert pc.player_payload(meta)["team"] == "Storvreta IBK / Visby IBK"


def test_player_payload_without_insights_has_no_clutch_or_share():
    payload = pc.player_payload(_meta())
    assert payload["clutch"] == {"current": None, "all": None}
    assert payload["share"] is None


def test_player_payload_uses_the_latest_season_when_career_totals_are_missing():
    meta = _meta()
    for key in [key for key in meta if key.startswith("career_")]:
        del meta[key]
    assert pc.player_payload(meta)["career"] == pc.player_payload(meta)["current"]


def test_a_share_of_zero_is_kept():
    payload = pc.player_payload(_meta(), trends={"share": 0, "points": 0, "team_goals": 12})
    assert payload["share"] == {"share": 0, "points": 0, "team_goals": 12}


def test_plugin_writes_an_index_and_a_file_per_player_from_the_articles():
    articles = [
        _article("player-aaa", clutch={"season_line": None, "all": {"gwg": 1, "clutch_points": 0, "game_changing": 1}}, team_page_url="9-spv.html"),
        _article("player-bbb", player_trends={"share": 10, "points": 2, "team_goals": 20}),
        SimpleNamespace(type="game", slug="game-1"),
    ]
    files = player_compare.player_files(articles)
    assert set(files) == {"index.json", "player-aaa.json", "player-bbb.json"}
    assert files["player-aaa.json"]["team_url"] == "9-spv.html"
    assert files["player-aaa.json"]["clutch"]["all"]["gwg"] == 1
    assert files["player-bbb.json"]["share"]["share"] == 10
    assert len(files["index.json"]["players"]) == 2


def test_plugin_reads_meta_values_that_pelican_wraps_in_lists():
    article = _article("player-aaa", team=["SPV"])
    assert player_compare.player_files([article])["player-aaa.json"]["team"] == "SPV"


def test_plugin_skips_player_pages_without_a_name():
    nameless = _article("player-zzz", player="", title="")
    assert set(player_compare.player_files([nameless])) == {"index.json"}


def test_write_emits_json_files_into_the_output_folder(tmp_path):
    generator = SimpleNamespace(articles=[_article("player-aaa")], output_path=str(tmp_path))
    player_compare.write(generator, writer=None)
    folder = tmp_path / "compare-players"
    assert json.loads((folder / "player-aaa.json").read_text())["name"] == "Janne Autio"
    index = json.loads((folder / "index.json").read_text())
    assert index["players"][0][0] == "player-aaa"


def test_write_ignores_generators_without_articles(tmp_path):
    player_compare.write(SimpleNamespace(output_path=str(tmp_path)), writer=None)
    assert not (tmp_path / "compare-players").exists()


def test_pelican_loads_the_plugin_and_the_menu_and_player_page_link_to_the_page():
    conf = (ROOT / "pelicanconf.py").read_text()
    assert "'player_compare'" in conf
    base = (ROOT / "themes/my-theme/templates/base.html").read_text()
    assert "/compare-players.html" in base
    player = (ROOT / "themes/my-theme/templates/player.html").read_text()
    assert "compare-players.html?a={{ article.slug }}" in player
    page = (ROOT / "content/pages/compare-players.md").read_text()
    assert "Template: player_compare" in page
    assert 'id="compare-players"' in (ROOT / "themes/my-theme/templates/stats_explained.html").read_text()


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_player_compare_script_logic():
    """Runs tests/js/player-compare.test.js (node:test) against themes/my-theme/static/js/player-compare.js."""
    result = subprocess.run(
        ["node", "--test", str(ROOT / "tests" / "js" / "player-compare.test.js")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
