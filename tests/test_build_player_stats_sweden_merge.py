from pathlib import Path

import pandas as pd

import src.build_player_stats as bps


def test_sweden_women_csv_path_merges_events_with_lineups(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "data_sew-26-27_regular_season.csv").write_text(
        "event_type,event_team,period,sortkey,game_id,home_team_name,away_team_name,home_goals,guest_goals,"
        "goal_type,penalty_type,game_date,game_start_time,attendance,game_status,ingame_status,result_string,"
        "scorer_name,assist_name,scorer_number,assist_number,penalty_player_name\n"
        "goal,Warberg IC,1,1-17:27,1693038,Malmö FBC,Warberg IC,0.0,1.0,goal,,2026-09-19,12:30:00,130.0,4,,0-1,"
        "Tova Nydenfeldt,Dessie Johansson,18.0,44.0,\n",
        encoding="utf-8",
    )

    def fake_lineups(match_ids, season, phase, league="Sweden"):
        # Since 2026 the lineups only prove participation; they carry no goals.
        stats = pd.DataFrame(
            [
                {"player_uid": bps._canonical_player_uid(name), "source_player_id": "", "source_person_id": "",
                 "player": name, "team": "Warberg IC", "games": 1, "goals": 0, "assists": 0, "points": 0, "pim": 0,
                 "penalties": 0}
                for name in ["Tova Nydenfeldt", "Dessie Johansson", "Lina Bench"]
            ]
        )
        return bps._finalize_rows(stats, season=season, phase=phase, league=league, source_system="sweden")

    monkeypatch.setattr(bps, "_rows_from_sweden_lineups", fake_lineups)

    output_csv = data_dir / "player_stats.csv"
    bps.build_player_stats(str(data_dir), str(output_csv), season_prefixes={"sew"})

    result = pd.read_csv(output_csv).set_index("player")
    assert set(result["league"]) == {"Sweden Women"}
    assert result.loc["Tova Nydenfeldt", ["games", "goals", "points"]].tolist() == [1, 1, 1]
    assert result.loc["Dessie Johansson", ["games", "assists"]].tolist() == [1, 1]
    assert result.loc["Lina Bench", ["games", "points"]].tolist() == [1, 0]
