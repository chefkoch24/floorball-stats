import pandas as pd

from src import build_player_stats_postgres as builder


def test_partial_rebuild_keeps_other_leagues_and_recomputes_selected(monkeypatch):
    events = pd.DataFrame(
        [
            {"season": "se-26-27", "phase": "regular-season", "event_type": "goal", "event_team": "A", "game_id": 1,
             "home_team_name": "A", "away_team_name": "B", "scorer_name": "Sven Svensson", "assist_name": "", "penalty_player_name": ""},
            {"season": "cz-26-27", "phase": "regular-season", "event_type": "goal", "event_team": "C", "game_id": 2,
             "home_team_name": "C", "away_team_name": "D", "scorer_name": "Jan Novák", "assist_name": "", "penalty_player_name": ""},
        ]
    )
    stored = pd.DataFrame(
        [{"player_uid": "stored-se", "source_system": "sweden", "source_player_id": "", "source_person_id": "",
          "player": "Sven Svensson", "title": "", "slug": "", "category": "", "team": "A", "league": "Sweden",
          "season": "se-26-27", "phase": "regular-season", "rank": 1, "games": 9, "goals": 9, "assists": 0,
          "points": 9, "pim": 0, "penalties": 0}]
    )
    lineup_calls = []
    written = {}
    monkeypatch.setattr(builder, "_load_events", lambda url: events)
    monkeypatch.setattr(builder, "_load_all_game_rosters", lambda url: pd.DataFrame())
    monkeypatch.setattr(builder, "_load_stored_player_stats", lambda url: stored)
    monkeypatch.setattr(
        builder,
        "_lineup_rows_for_prefix",
        lambda prefix, matches, season, phase, game_rosters=None: lineup_calls.append(prefix) or pd.DataFrame(),
    )
    monkeypatch.setattr(builder, "_replace_player_stats_table", lambda url, frame: written.setdefault("frame", frame) is not None and len(frame))

    builder.build_player_stats_from_postgres(database_url="postgresql://test", only_prefixes={"cz"})

    frame = written["frame"]
    assert lineup_calls == ["cz"]
    assert frame[frame["season"] == "se-26-27"]["player_uid"].tolist() == ["stored-se"]
    assert frame[frame["season"] == "cz-26-27"]["player"].tolist() == ["Jan Novák"]
