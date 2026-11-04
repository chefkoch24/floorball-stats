import json
from pathlib import Path

import pandas as pd

from src import build_player_stats, scrape_champions_cup
from src.build_player_stats import _rows_from_wfc_lineups
from src.league_config import apply_league_config, load_league_config
from src.run_stats_engine import _assign_wfc_playoff_rounds
from src.scrape_champions_cup import (
    build_game_row,
    fetch_competition_games,
    make_team_normalizer,
    national_league_prefix,
    parse_game_time,
    parse_team_display_name,
    stage_metadata,
)
from src.scrape_wfc import _overview_event_to_row
from src import pipeline


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config" / "leagues"


def _game(**overrides):
    game = {
        "GameID": 8885,
        "GameStatusID": 3,
        "GameTime": "2026-10-01T17:00:00.000Z",
        "LeagueName": "Women's Southern Conference Quarterfinals",
        "LeagueDisplayName": "Women's Southern Conference Quarterfinals",
        "FederationOrCupName": "IFF Champions Cup 2027",
        "HomeTeamDisplayName": "Bulldogs Brno (CZE) Women",
        "AwayTeamDisplayName": "Zug United (SUI) Women",
        "HomeTeamScore": 5,
        "AwayTeamScore": 3,
        "FinalResultTypeID": 1,
        "ArenaName": "Hala Vodova",
        "Spectators": 450,
    }
    game.update(overrides)
    return game


def test_team_display_names_split_into_club_country_and_division():
    assert parse_team_display_name("Storvreta IBK (SWE) Men") == ("Storvreta IBK", "SWE", "men")
    assert parse_team_display_name("Zug United (SUI) Women") == ("Zug United", "SUI", "women")
    assert parse_team_display_name("Plain Name") == ("Plain Name", None, None)
    assert national_league_prefix("CZE", "women") == "czw"
    assert national_league_prefix("SUI", "men") == "ch"
    assert national_league_prefix("NOR", "men") is None


def test_team_names_are_mapped_to_national_league_names():
    normalize = make_team_normalizer({"Tatran Stresovice": "Tatran Střešovice"})

    assert normalize("Tatran Stresovice (CZE) Men") == "Tatran Střešovice"
    assert normalize("Nokian KrP (FIN) Men") == "Nokian KrP"


def test_stage_metadata_reads_round_and_conference_from_league_name():
    quarter = stage_metadata({"LeagueName": "Men's Northern Conference Quarterfinals"})
    semi = stage_metadata({"LeagueName": "Women's Semi-finals"})
    final = stage_metadata({"LeagueName": "Men's Final"})

    assert quarter["tournament_round"] == "Quarter-finals"
    assert quarter["tournament_group"] == "Northern Conference"
    assert quarter["tournament_stage_type"] == "elimination"
    assert semi["tournament_round"] == "Semi-finals"
    assert semi["tournament_group"] is None
    assert final["tournament_round"] == "Final"
    assert final["tournament_round_order"] > semi["tournament_round_order"] > quarter["tournament_round_order"]


def test_kick_off_times_are_converted_to_local_time():
    assert parse_game_time("2026-08-22T15:00:00.000Z") == ("2026-08-22", "17:00")
    assert parse_game_time("2026-11-04T18:30:00.000Z") == ("2026-11-04", "19:30")
    assert parse_game_time("") == (None, None)


def test_scheduled_games_with_zero_score_stay_scheduled():
    row = build_game_row(_game(GameStatusID=1, HomeTeamScore=0, AwayTeamScore=0), make_team_normalizer())

    assert row["event_type"] == "scheduled"
    assert row["home_goals"] is None
    assert row["game_status"] == "Scheduled"


def test_tiebreak_overtime_flag_does_not_change_two_legged_score():
    normalize = make_team_normalizer({"Bulldogs Brno": "GC System Bulldogs Brno"})
    second_leg = build_game_row(_game(), normalize)
    final = build_game_row(_game(LeagueName="Women's Final", HomeTeamScore=4, AwayTeamScore=3), normalize)

    assert second_leg["result_string"] == "5-3"
    assert second_leg["home_team_name"] == "GC System Bulldogs Brno"
    assert second_leg["tournament_round"] == "Quarter-finals"
    assert final["result_string"] == "4-3 OT"


def test_events_use_fifteen_minute_periods():
    game = _game()
    metadata = stage_metadata(game)
    blurb = {
        "IsGoal": True,
        "Description": "Assist by: 23. Gerig",
        "GameMinute": "44:39",
        "GameClockSecond": 879,
        "IsAwayTeamAction": True,
        "Score": "5-3",
        "Title": "7. Laila Ediz",
    }
    row = _overview_event_to_row(
        blurb,
        game,
        metadata,
        {},
        normalize_team=make_team_normalizer(),
        parse_game_time=parse_game_time,
        period_seconds=scrape_champions_cup.PERIOD_SECONDS,
    )
    overtime = _overview_event_to_row(
        {**blurb, "GameMinute": "47:10", "GameClockSecond": 130},
        game,
        metadata,
        {},
        normalize_team=make_team_normalizer(),
        parse_game_time=parse_game_time,
        period_seconds=scrape_champions_cup.PERIOD_SECONDS,
    )

    assert (row["period"], row["sortkey"]) == (3, "3-14:39")
    assert row["event_team"] == "Zug United"
    assert row["scorer_name"] == "Laila Ediz"
    assert row["assist_name"] == "Gerig"
    assert row["game_date"] == "2026-10-01"
    assert overtime["period"] == 4


def test_competition_games_are_split_by_division_and_deduplicated(monkeypatch):
    previous = [_game(GameID=1, LeagueName="Men's Semi-finals"), _game(GameID=2)]
    coming = [
        _game(GameID=1, LeagueName="Men's Semi-finals", GameStatusID=1),
        _game(GameID=3, LeagueName="Men's Semi-finals", GameStatusID=1),
    ]

    def fake_fetch(league_organizer_id, *, auth, endpoint):
        return previous if endpoint == "getpreviousleagueorganizergames" else coming

    monkeypatch.setattr(scrape_champions_cup, "fetch_previous_league_organizer_games", fake_fetch)
    games = fetch_competition_games(853, auth=object(), division="men")

    assert sorted(game["GameID"] for game in games) == [1, 3]
    assert next(game for game in games if game["GameID"] == 1)["GameStatusID"] == 3


def test_canonical_round_names_become_playoff_rounds():
    df = pd.DataFrame(
        [
            {"game_id": 1, "tournament_stage_type": "elimination", "tournament_round": "Quarter-finals"},
            {"game_id": 2, "tournament_stage_type": "elimination", "tournament_round": "Semi-finals"},
        ]
    )

    assert _assign_wfc_playoff_rounds(df)["playoff_round"].tolist() == ["Quarter-finals", "Semi-finals"]


def test_lineup_games_count_once_when_roster_and_lineup_list_a_player(monkeypatch):
    class DummyAuth:
        access_token = "token"
        refresh_token = "refresh"

    monkeypatch.setattr(build_player_stats, "_load_wfc_auth_from_env", lambda: DummyAuth())
    monkeypatch.setattr(
        build_player_stats,
        "_fetch_wfc_game_lineups",
        lambda game_id, auth: {
            "HomeTeamGameTeamRoster": {"Players": [{"FullName": "Pablo Mariotti", "PlayerID": "11"}]},
            "HomeTeamLineUp": {"GameLineUpPlayers": [{"FullName": "Pablo Mariotti", "MemberID": ""}]},
            "AwayTeamGameTeamRoster": {"Players": [{"FullName": "Simon Stransky", "PlayerID": "21"}]},
        },
    )
    matches = pd.DataFrame(
        [
            {"game_id": 8875, "home_team_name": "Floorball Thurgau", "away_team_name": "AMIX Florbal MB"},
            {"game_id": 8878, "home_team_name": "Floorball Thurgau", "away_team_name": "AMIX Florbal MB"},
        ]
    )
    rows = _rows_from_wfc_lineups(matches=matches, season="cc-26-27", phase="playoffs", league="IFF Champions Cup")

    mariotti = rows[rows["player"] == "Pablo Mariotti"].iloc[0]
    assert int(mariotti["games"]) == 2
    assert mariotti["source_player_id"] == "11"
    assert mariotti["league"] == "IFF Champions Cup"
    assert set(rows["team"]) == {"Floorball Thurgau", "AMIX Florbal MB"}


def test_champions_cup_configs_wire_the_backend(monkeypatch):
    for name, division, season in [
        ("iff-champions-cup-26-27-playoffs.json", "men", "cc-26-27"),
        ("iff-champions-cup-women-26-27-playoffs.json", "women", "ccw-26-27"),
    ]:
        monkeypatch.setattr("sys.argv", ["pipeline", "--league_config", str(CONFIG_DIR / name)])
        args = pipeline.parse_args()
        apply_league_config(args, load_league_config(args.league_config))

        assert args.backend == "champions_cup"
        assert args.season == season
        assert args.phase == "playoffs"
        assert args.champions_cup_league_organizer_id == 853
        assert args.champions_cup_division == division
        assert args.champions_cup_team_aliases
        assert [r["name"] for r in args.playoff_rounds] == ["Quarter-finals", "Semi-finals", "Final"]
        assert args.playoff_rounds[0]["series_type"] == "two-legged"


def test_champions_cup_prefixes_are_registered_for_player_pages():
    from src import generate_player_markdown, generate_player_stats_index_markdown

    assert build_player_stats.LEAGUE_INFO["cc"]["league"] == "IFF Champions Cup"
    assert build_player_stats.LEAGUE_INFO["ccw"]["league"] == "IFF Champions Cup Women"
    assert generate_player_markdown._is_tournament_season("cc-26-27")
    assert generate_player_stats_index_markdown._is_tournament_season("ccw-26-27")


def test_champions_cup_categories_are_labelled_and_linked(tmp_path, monkeypatch):
    import pelicanconf

    assert "cc-26-27-playoffs/games" in pelicanconf.ARTICLE_PATHS
    assert "ccw-26-27-playoffs/teams" in pelicanconf.ARTICLE_PATHS
    assert "ccw-" in pelicanconf.WOMEN_LEAGUE_PREFIXES
    assert pelicanconf.category2string("cc-26-27-playoffs") == "IFF Champions Cup 26/27 Playoffs"
    assert pelicanconf.league_context("ccw-26-27-playoffs")["division"] == "women"

    teams = tmp_path / "content" / "czw-26-27-regular-season" / "teams"
    teams.mkdir(parents=True)
    (teams / "tatran.md").write_text(
        "Date: 2026-10-01\nTitle: Tatran Střešovice\nSlug: tatran-czw-26-27-regular-season\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(pelicanconf, "PATH", str(tmp_path / "content"))
    monkeypatch.setattr(pelicanconf, "_NATIONAL_TEAM_PAGES", None)

    page = pelicanconf.national_team_page("Tatran Střešovice", "ccw-26-27-playoffs")
    assert page["url"] == "tatran-czw-26-27-regular-season.html"
    assert page["title"] == "Czech Republic · ČEZ Extraliga žen"
    assert pelicanconf.national_team_page("Tatran Střešovice", "cc-26-27-playoffs") is None
    assert pelicanconf.national_team_page("Tatran Střešovice", "czw-26-27-regular-season") is None
