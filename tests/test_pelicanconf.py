from datetime import datetime, time

from pelicanconf import fmt_time


def test_fmt_time_keeps_hours_and_minutes_only():
    assert fmt_time("18:30:00") == "18:30"
    assert fmt_time("18:30") == "18:30"
    assert fmt_time(time(18, 30, 45)) == "18:30"
    assert fmt_time(datetime(2026, 3, 20, 18, 30, 45)) == "18:30"


def test_fmt_time_handles_empty_values():
    assert fmt_time(None) == "TBD"
    assert fmt_time("") == "TBD"
    assert fmt_time("None") == "TBD"
    assert fmt_time("TBD") == "TBD"
