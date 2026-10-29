import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins"))

import insights  # noqa: E402


def test_playoff_format_comes_from_the_league_configs():
    places, rounds = insights._playoff_format("cz-", "26-27")
    assert places == 10
    assert [round_.teams for round_ in rounds] == [4, 8, 4, 2]
    places, rounds = insights._playoff_format("", "26-27")
    assert places == 8 and rounds[0].wins_to_advance == 2
    assert insights._playoff_format("lvw-", "26-27") == (None, [])


def test_percent_labels_never_round_to_certainty():
    assert insights._percent(0.997) == ">99%"
    assert insights._percent(1.0) == "100%"
    assert insights._percent(0.001) == "<1%"
    assert insights._percent(0.0) == "0%"
    assert insights._percent(0.426) == "43%"
    assert insights._percent(None) == "–"


def test_category_pattern_covers_germany_and_prefixed_leagues():
    assert insights.CATEGORY_PATTERN.match("26-27-regular-season")["prefix"] == ""
    assert insights.CATEGORY_PATTERN.match("sew-26-27-playoffs")["prefix"] == "sew-"
    assert insights.CATEGORY_PATTERN.match("wfc-2024-playoffs") is None


def test_sparkline_scales_points_into_the_box():
    points = insights._sparkline([1500, 1550, 1450]).split()
    assert points[0].startswith("0.0,") and points[-1].startswith("240.0,")
    assert insights._sparkline([1500]) == ""
