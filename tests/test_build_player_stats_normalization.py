from pathlib import Path

import pandas as pd

from src.build_player_stats import _rows_from_event_csv


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
