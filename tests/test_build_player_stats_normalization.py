from pathlib import Path

import pandas as pd

from src import build_player_stats
from src.build_player_stats import _merge_finalized_rows, _rows_from_event_csv, _rows_from_wfc_lineups


def test_rows_from_event_csv_normalizes_czech_suffix_and_case_variants(tmp_path: Path) -> None:
    source = tmp_path / "events.csv"
    pd.DataFrame(
        [
            {
                "event_type": "goal",
                "event_team": "HDT.cz Florbal Vary Bohemians",
                "game_id": 1,
                "scorer_name": "Jaroslav Petrák",
                "assist_name": "",
                "penalty_player_name": "",
            },
            {
                "event_type": "goal",
                "event_team": "HDT.cz Florbal Vary Bohemians",
                "game_id": 2,
                "scorer_name": "Jaroslav Petrák bez asistence",
                "assist_name": "",
                "penalty_player_name": "",
            },
            {
                "event_type": "goal",
                "event_team": "HDT.cz Florbal Vary Bohemians",
                "game_id": 3,
                "scorer_name": "Jaroslav Petrák z trestného střílení",
                "assist_name": "",
                "penalty_player_name": "",
            },
            {
                "event_type": "penalty",
                "event_team": "HDT.cz Florbal Vary Bohemians",
                "game_id": 4,
                "scorer_name": "",
                "assist_name": "",
                "penalty_player_name": "Jaroslav PETRÁK",
            },
            {
                "event_type": "goal",
                "event_team": "HDT.cz Florbal Vary Bohemians",
                "game_id": 5,
                "scorer_name": "Karel Petrák bez asistence",
                "assist_name": "",
                "penalty_player_name": "",
            },
            {
                "event_type": "penalty",
                "event_team": "HDT.cz Florbal Vary Bohemians",
                "game_id": 6,
                "scorer_name": "",
                "assist_name": "",
                "penalty_player_name": "Karel PETRÁK",
            },
        ]
    ).to_csv(source, index=False)

    result = _rows_from_event_csv(
        source,
        season="cz-25-26",
        phase="regular-season",
        league="Czech Republic",
        source_system="czech-republic",
    )

    players = set(result["player"].tolist())
    assert players == {"Jaroslav Petrák", "Karel Petrák"}
    assert all("bez asistence" not in player.lower() for player in players)
    assert all("trestn" not in player.lower() for player in players)

    jaroslav = result[result["player"] == "Jaroslav Petrák"].iloc[0]
    assert int(jaroslav["goals"]) == 3
    assert int(jaroslav["pim"]) == 2


def test_rows_from_event_csv_harmonizes_slovakia_name_order(tmp_path: Path) -> None:
    source = tmp_path / "events_sk.csv"
    pd.DataFrame(
        [
            {
                "event_type": "goal",
                "event_team": "1. FBC Trenčín",
                "game_id": 1,
                "scorer_name": "Hatala Šimon",
                "assist_name": "",
                "penalty_player_name": "",
            },
            {
                "event_type": "goal",
                "event_team": "1. FBC Trenčín",
                "game_id": 2,
                "scorer_name": "Šimon HATALA",
                "assist_name": "",
                "penalty_player_name": "",
            },
        ]
    ).to_csv(source, index=False)

    result = _rows_from_event_csv(
        source,
        season="sk-25-26",
        phase="regular-season",
        league="Slovakia",
        source_system="slovakia",
    )

    assert len(result) == 1
    row = result.iloc[0]
    assert row["player"] == "Šimon Hatala"
    assert int(row["goals"]) == 2


def test_rows_from_event_csv_harmonizes_slovakia_dot_separator(tmp_path: Path) -> None:
    source = tmp_path / "events_sk_dot.csv"
    pd.DataFrame(
        [
            {
                "event_type": "goal",
                "event_team": "1. FBC Trenčín",
                "game_id": 1,
                "scorer_name": "Tomáš Tvrdý",
                "assist_name": "",
                "penalty_player_name": "",
            },
            {
                "event_type": "penalty",
                "event_team": "1. FBC Trenčín",
                "game_id": 2,
                "scorer_name": "",
                "assist_name": "",
                "penalty_player_name": "Tomáš . Tvrdý",
            },
        ]
    ).to_csv(source, index=False)

    result = _rows_from_event_csv(
        source,
        season="sk-25-26",
        phase="regular-season",
        league="Slovakia",
        source_system="slovakia",
    )

    assert len(result) == 1
    row = result.iloc[0]
    assert row["player"] == "Tomáš Tvrdý"
    assert int(row["goals"]) == 1
    assert int(row["penalties"]) == 1


def test_rows_from_wfc_lineups_count_games_for_non_scorers(monkeypatch) -> None:
    class DummyAuth:
        access_token = "token"
        refresh_token = "refresh"

    monkeypatch.setattr(build_player_stats, "_load_wfc_auth_from_env", lambda: DummyAuth())
    monkeypatch.setattr(
        build_player_stats,
        "_fetch_wfc_game_lineups",
        lambda game_id, auth: {
            "HomeTeamGameTeamRoster": {
                "Players": [
                    {"FullName": "Scorer Player", "PlayerID": "11"},
                ],
                "Substitutes": [
                    {"FullName": "Bench Player", "PlayerID": "12"},
                ],
            },
            "AwayTeamGameTeamRoster": {
                "Players": [
                    {"FullName": "Away Player", "PlayerID": "21"},
                ],
                "Substitutes": [],
            },
        },
    )

    matches = pd.DataFrame(
        [
            {
                "game_id": 7239,
                "home_team_name": "Czechia",
                "away_team_name": "Latvia",
            }
        ]
    )
    lineup_rows = _rows_from_wfc_lineups(matches=matches, season="wfc-2024", phase="playoffs")

    bench_row = lineup_rows[lineup_rows["player"] == "Bench Player"].iloc[0]
    assert int(bench_row["games"]) == 1
    assert int(bench_row["points"]) == 0


def test_rows_from_wfc_lineups_accumulate_games_across_multiple_matches(monkeypatch) -> None:
    class DummyAuth:
        access_token = "token"
        refresh_token = "refresh"

    monkeypatch.setattr(build_player_stats, "_load_wfc_auth_from_env", lambda: DummyAuth())
    monkeypatch.setattr(
        build_player_stats,
        "_fetch_wfc_game_lineups",
        lambda game_id, auth: {
            "HomeTeamGameTeamRoster": {
                "Players": [
                    {"FullName": "Gabriel Kohonen", "PlayerID": "1691"},
                ],
                "Substitutes": [],
            },
            "AwayTeamGameTeamRoster": {
                "Players": [],
                "Substitutes": [],
            },
        },
    )

    matches = pd.DataFrame(
        [
            {"game_id": 7188, "home_team_name": "Sweden", "away_team_name": "Slovakia"},
            {"game_id": 7189, "home_team_name": "Sweden", "away_team_name": "Latvia"},
            {"game_id": 7192, "home_team_name": "Finland", "away_team_name": "Sweden"},
        ]
    )

    lineup_rows = _rows_from_wfc_lineups(matches=matches, season="wfc-2024", phase="regular-season")
    row = lineup_rows[lineup_rows["player"] == "Gabriel Kohonen"].iloc[0]
    assert int(row["games"]) == 3
    assert int(row["points"]) == 0


def test_wfc_lineups_merge_preserves_event_totals_and_updates_games(tmp_path: Path, monkeypatch) -> None:
    class DummyAuth:
        access_token = "token"
        refresh_token = "refresh"

    monkeypatch.setattr(build_player_stats, "_load_wfc_auth_from_env", lambda: DummyAuth())
    monkeypatch.setattr(
        build_player_stats,
        "_fetch_wfc_game_lineups",
        lambda game_id, auth: {
            "HomeTeamGameTeamRoster": {
                "Players": [
                    {"FullName": "Scorer Player", "PlayerID": "11"},
                ],
                "Substitutes": [
                    {"FullName": "Bench Player", "PlayerID": "12"},
                ],
            },
            "AwayTeamGameTeamRoster": {
                "Players": [],
                "Substitutes": [],
            },
        },
    )

    source = tmp_path / "wfc_events.csv"
    pd.DataFrame(
        [
            {
                "event_type": "goal",
                "event_team": "Czechia",
                "game_id": 7239,
                "home_team_name": "Czechia",
                "away_team_name": "Latvia",
                "scorer_name": "Scorer Player",
                "assist_name": "",
                "penalty_player_name": "",
            }
        ]
    ).to_csv(source, index=False)

    event_rows = _rows_from_event_csv(
        source,
        season="wfc-2024",
        phase="playoffs",
        league="IFF WFC",
        source_system="wfc",
    )
    matches = pd.read_csv(source, usecols=["game_id", "home_team_name", "away_team_name"]).drop_duplicates()
    lineup_rows = _rows_from_wfc_lineups(matches=matches, season="wfc-2024", phase="playoffs")
    merged = _merge_finalized_rows(
        [event_rows, lineup_rows],
        season="wfc-2024",
        phase="playoffs",
        league="IFF WFC",
        source_system="wfc",
    )

    scorer_row = merged[merged["player"] == "Scorer Player"].iloc[0]
    bench_row = merged[merged["player"] == "Bench Player"].iloc[0]
    assert int(scorer_row["games"]) == 1
    assert int(scorer_row["goals"]) == 1
    assert int(scorer_row["points"]) == 1
    assert int(bench_row["games"]) == 1
    assert int(bench_row["points"]) == 0
