import requests

from src import scrape_sweden
from src.scrape_sweden import ApiConfig, expand_competition_ids_by_category


COMPETITIONS = {
    # 25/26: regular season + quarter-final series in playoff category 670
    40693: {"CompetitionID": 40693, "CategoryID": 10, "PlayOffCategoryID": 670, "SeasonID": 43},
    43813: {"CompetitionID": 43813, "CategoryID": 670, "PlayOffCategoryID": 0, "SeasonID": 43},
    43814: {"CompetitionID": 43814, "CategoryID": 670, "PlayOffCategoryID": 0, "SeasonID": 43},
    # 26/27: regular season, playoff series not necessarily published yet
    44033: {"CompetitionID": 44033, "CategoryID": 10, "PlayOffCategoryID": 670, "SeasonID": 44},
    46001: {"CompetitionID": 46001, "CategoryID": 670, "PlayOffCategoryID": 0, "SeasonID": 44},
}


def _patch_api(monkeypatch, federation_ids):
    def _dead_category_endpoint(api_root, headers, category_id):
        raise requests.HTTPError("404")

    monkeypatch.setattr(scrape_sweden, "_get_api_config", lambda: ApiConfig(api_root="https://example.test/", token="t"))
    monkeypatch.setattr(
        scrape_sweden,
        "_fetch_federation_competitions",
        lambda api_root, headers, federation_id=1: [
            {"CompetitionID": cid, "CategoryID": COMPETITIONS[cid]["CategoryID"], "SeasonID": None} for cid in federation_ids
        ],
    )
    monkeypatch.setattr(scrape_sweden, "_fetch_competition", lambda api_root, headers, cid: dict(COMPETITIONS.get(cid, {})))
    monkeypatch.setattr(scrape_sweden, "_fetch_competition_category_competitions", _dead_category_endpoint)


def test_regular_season_competition_without_published_playoffs_resolves_to_nothing(monkeypatch):
    _patch_api(monkeypatch, federation_ids=[44033])

    assert expand_competition_ids_by_category([44033]) == []


def test_regular_season_competition_resolves_same_season_playoff_series(monkeypatch):
    _patch_api(monkeypatch, federation_ids=[44033, 46001])

    assert expand_competition_ids_by_category([44033]) == [46001]


def test_explicit_playoff_series_ignore_other_seasons(monkeypatch):
    # Federation list only holds the current (26/27) season.
    _patch_api(monkeypatch, federation_ids=[44033, 46001])

    assert expand_competition_ids_by_category([43813, 43814]) == [43813, 43814]


def test_event_side_is_resolved_from_match_team_id():
    from src.scrape_sweden import _event_to_row

    match = {
        "MatchID": 1693404,
        "HomeTeam": "Warberg IC",
        "AwayTeam": "Storvreta IBK",
        "HomeMatchTeamID": 3282782,
        "AwayMatchTeamID": 3282783,
        "MatchDateTime": "2026-09-18T19:00:00",
        "GoalsHomeTeam": 3,
        "GoalsAwayTeam": 6,
    }
    empty_net = {
        "MatchEventType": "Mål i tom bur",
        "MatchTeamID": 3282783,
        "Period": 3,
        "Minute": 19,
        "Second": 10,
        "GoalsHomeTeam": 3,
        "GoalsAwayTeam": 6,
        "PlayerName": "Filip Eriksson",
        "PlayerAssistName": "Pascal Schmuki",
    }
    goalie_change = {"MatchEventType": "Målvakt - In", "MatchTeamID": 3282782, "Period": 1}

    row = _event_to_row(empty_net, match)

    assert row["event_type"] == "goal"
    assert row["event_team"] == "Storvreta IBK"
    assert row["sortkey"] == "3-19:10"
    assert _event_to_row(goalie_change, match) is None
