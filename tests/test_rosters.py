import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins"))

import rosters  # noqa: E402


def test_team_key_ignores_accents_case_and_punctuation():
    assert rosters.team_key("FBŠ Hummel Hattrick Brno") == rosters.team_key("fbs hummel-hattrick brno")


def test_parse_player_rows_skips_broken_rows():
    rows = rosters.parse_player_rows("1|player-a|Anna|Team X|4|2|3|5|2||broken||2|player-b|Bea|Team Y|3|0|1|1|0")
    assert [(r["name"], r["url"], r["points"]) for r in rows] == [("Anna", "player-a.html", 5), ("Bea", "player-b.html", 1)]


def test_build_rosters_groups_by_phase_and_team_sorted_by_points():
    rows = rosters.parse_player_rows(
        "1|p1|Low|Malmö FBC|5|1|0|1|0||2|p2|High|Malmo FBC|5|4|4|8|2||3|p3|Other|Karlstad IBF|5|9|9|18|0"
    )
    built = rosters.build_rosters({"se-26-27-regular-season": rows})
    malmo = built[("se-26-27-regular-season", rosters.team_key("Malmö FBC"))]
    assert [r["name"] for r in malmo] == ["High", "Low"]
    assert ("se-26-27-regular-season", rosters.team_key("Karlstad IBF")) in built
