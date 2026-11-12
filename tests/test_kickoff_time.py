import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "plugins"))

from kickoff_time import kickoff_label, kickoff_parts, timezone_for_prefix, tournament_kickoff_parts  # noqa: E402
from pelicanconf import fmt_kickoff  # noqa: E402


def plain(text):
    return text.replace("\u00a0", " ")


def label(prefix, start="18:30", day=date(2026, 11, 12), **kwargs):
    return plain(kickoff_label(kickoff_parts(day, start, prefix, **kwargs)))


def test_finnish_and_latvian_games_show_local_time_and_german_time():
    assert label("fi-") == "18:30 EET (17:30 CET)"
    assert label("fiw-") == "18:30 EET (17:30 CET)"
    assert label("lv-") == "18:30 EET (17:30 CET)"


def test_summer_time_changes_the_zone_names_but_not_the_gap():
    assert label("fi-", day=date(2026, 7, 4)) == "18:30 EEST (17:30 CEST)"


def test_leagues_on_german_time_show_the_plain_clock_time():
    for prefix in ("", "dew-", "se-", "sew-", "cz-", "ch-", "sk-"):
        assert label(prefix) == "18:30", prefix


def test_always_label_names_the_zone_even_on_german_time():
    assert label("cc-", always_label=True) == "18:30 CET"


def test_german_time_on_another_day_is_flagged():
    assert label("fi-", start="00:30") == "00:30 EET (23:30 CET, day before)"


def test_missing_or_invalid_times_give_nothing():
    assert kickoff_parts(date(2026, 11, 12), "TBD", "fi-") is None
    assert kickoff_parts(date(2026, 11, 12), "", "fi-") is None
    assert kickoff_parts(date(2026, 11, 12), "25:99", "fi-") is None
    assert kickoff_parts(None, "18:30", "fi-") is None
    assert kickoff_label(None) == ""


def test_seconds_and_datetimes_are_accepted():
    assert kickoff_parts(datetime(2026, 11, 12, 0, 0), "18:30:00", "fi-")["local"] == "18:30"


def test_unknown_prefix_falls_back_to_berlin():
    assert timezone_for_prefix("xx-").key == "Europe/Berlin"
    assert timezone_for_prefix("fiw-").key == "Europe/Helsinki"


def game(category, start="18:30"):
    return SimpleNamespace(date=datetime(2026, 11, 12), category=SimpleNamespace(shortname=category), start_time=start)


def test_fmt_kickoff_reads_the_league_from_the_game_category():
    assert plain(fmt_kickoff(game("fi-26-27-regular-season"))) == "18:30 EET (17:30 CET)"
    assert fmt_kickoff(game("26-27-regular-season")) == "18:30"
    assert plain(fmt_kickoff(game("cc-26-27-playoffs"))) == "18:30 CET"
    assert plain(fmt_kickoff(game("fi-26-27-cup"))) == "18:30 EET (17:30 CET)"


def test_fmt_kickoff_reads_cup_rows_and_falls_back_for_missing_times():
    row = {"date": datetime(2026, 11, 12), "category": "fi-26-27-cup", "start_time": "18:30"}
    assert plain(fmt_kickoff(row)) == "18:30 EET (17:30 CET)"
    assert fmt_kickoff(game("fi-26-27-regular-season", start="")) == "TBD"
    assert fmt_kickoff(game("fi-26-27-regular-season", start="TBD")) == "TBD"
    assert fmt_kickoff(game("fi-26-27-regular-season", start=None), "") == ""


def test_wfc_times_are_stored_in_utc_and_shown_in_the_host_city():
    parts = tournament_kickoff_parts(date(2024, 12, 11), "08:30", "wfc-2024-playoffs")
    assert plain(kickoff_label(parts)) == "09:30 CET"
    assert plain(fmt_kickoff(game("wfc-2024-regular-season", start="08:30"))) == "09:30 CET"


def test_unlisted_tournament_is_labelled_utc_with_the_german_time():
    assert plain(kickoff_label(tournament_kickoff_parts(date(2026, 12, 11), "08:30", "wfc-2026-playoffs"))) == "08:30 UTC (09:30 CET)"


def test_tournament_helper_ignores_league_categories():
    assert tournament_kickoff_parts(date(2026, 11, 12), "18:30", "fi-26-27-regular-season") is None


def test_labels_only_wrap_between_local_and_german_time():
    text = kickoff_label(kickoff_parts(date(2026, 11, 12), "18:30", "fi-"))
    assert text.split(" ") == ["18:30\u00a0EET", "(17:30\u00a0CET)"]
