from src.scrape_czech import _is_playout_round


def test_is_playout_round_detects_common_variants():
    assert _is_playout_round("Play-down") is True
    assert _is_playout_round("Play down - round 2") is True
    assert _is_playout_round("Playout") is True
    assert _is_playout_round("Play-out") is True
    assert _is_playout_round("Čtvrtfinále") is False
    assert _is_playout_round(None) is False
