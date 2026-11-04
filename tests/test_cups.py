import json
from pathlib import Path

import pandas as pd
import pytest

from src import build_player_stats, build_player_stats_postgres as player_builder
from src import pipeline, scrape, scrape_czech, scrape_sweden, scrape_switzerland, scrape_torneopal
from src.competitions import (
    CUP_PHASE,
    STAGE_ELIMINATION,
    STAGE_GROUP,
    cup_columns,
    is_cup_category,
    is_cup_phase,
    tag_cup_csv,
    tag_cup_frame,
)
from src.generate_markdown import generate_markdown_files
from src.league_config import apply_league_config, load_league_config
from src.run_stats_engine import run_stats_pipeline

ROOT = Path(__file__).resolve().parents[1]
# National cups only: the IFF Champions Cup configs (iff-champions-cup-*) are a playoffs competition.
CUP_CONFIGS = sorted(
    path for path in (ROOT / "config" / "leagues").glob("*-cup-*.json") if not path.name.startswith("iff-")
)


def _game_rows(game_id: int, home: str, away: str, home_goals: int = 1, away_goals: int = 0, **extra) -> list[dict]:
    base = {
        "game_id": game_id,
        "game_date": "2026-10-07",
        "home_team_name": home,
        "away_team_name": away,
        "period": 1,
        "attendance": 100,
        "penalty_player_name": None,
        "assist_name": None,
        **extra,
    }
    return [
        {**base, "event_type": "goal", "event_team": home, "home_goals": home_goals, "guest_goals": away_goals,
         "sortkey": "1-05:00", "goal_type": "goal", "penalty_type": None, "scorer_name": "Alice Forward"},
        {**base, "event_type": "penalty", "event_team": away, "home_goals": home_goals, "guest_goals": away_goals,
         "sortkey": "1-12:00", "goal_type": None, "penalty_type": "penalty_2", "scorer_name": None,
         "penalty_player_name": "Pat Defender"},
    ]


# --- marker helpers ---------------------------------------------------------------------------


def test_cup_phase_and_category_identifiers():
    assert is_cup_phase(CUP_PHASE) and is_cup_phase(" cup ")
    assert not is_cup_phase("playoffs") and not is_cup_phase(None)
    assert is_cup_category("ch-26-27-cup") and is_cup_category("26-27-cup")
    assert not is_cup_category("ch-26-27-playoffs") and not is_cup_category("cup-final-regular-season")


def test_tag_cup_frame_fills_only_missing_markers():
    frame = pd.DataFrame(
        [
            {"game_id": 1, "competition_name": None, "tournament_stage_type": None, "tournament_stage_label": "Final"},
            {"game_id": 2, "competition_name": "Own Cup", "tournament_stage_type": "group-stage", "tournament_stage_label": None},
        ]
    )

    tagged = tag_cup_frame(frame, "Config Cup")

    assert tagged["competition_name"].tolist() == ["Config Cup", "Own Cup"]
    assert tagged["tournament_stage_type"].tolist() == [STAGE_ELIMINATION, STAGE_GROUP]
    assert tagged["tournament_stage_label"].tolist()[0] == "Final"
    assert "tournament_group" in tagged.columns


def test_tag_cup_csv_rewrites_file(tmp_path):
    path = tmp_path / "data_se-26-27_cup.csv"
    pd.DataFrame(_game_rows(1, "A", "B")).to_csv(path, index=False)

    assert tag_cup_csv(path, "Svenska Cupen Herrar") == 2
    assert set(pd.read_csv(path)["competition_name"]) == {"Svenska Cupen Herrar"}


def test_tag_cup_csv_accepts_an_empty_scrape(tmp_path):
    path = tmp_path / "data_se-26-27_cup.csv"
    path.write_text('""\n', encoding="utf-8")

    assert tag_cup_csv(path, "Svenska Cupen Herrar") == 0


def test_cup_pipeline_reports_an_empty_cup_instead_of_building_empty_pages(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "data_se-26-27_cup.csv").write_text('""\n', encoding="utf-8")

    with pytest.raises(ValueError, match="No cup games found"):
        pipeline.run_pipeline(
            league_id=None, season="se-26-27", phase="cup", backend="sweden",
            data_dir=str(tmp_path / "data"), content_dir=str(tmp_path / "content"), skip_scrape=True, database_url=None,
        )


# --- sources ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "competition, label, stage_type, group",
    [
        ("Svenska Cupen Herrar Omg 1", "Omgång 1", STAGE_ELIMINATION, None),
        ("Svenska Cupen Herrar Omg 2 Grupp C", "Omgång 2", STAGE_GROUP, "Grupp C"),
        ("Svenska Cupen Herrar Kvartsfinaler", "Kvartsfinaler", STAGE_ELIMINATION, None),
        ("Svenska Cupen Herrar Semifinal 1", "Semifinal 1", STAGE_ELIMINATION, None),
    ],
)
def test_sweden_cup_stage_comes_from_the_round_competition(competition, label, stage_type, group):
    fields = scrape_sweden._cup_fields({"CompetitionName": competition, "RoundName": "Omgång 3"}, "Svenska Cupen Herrar")

    assert fields["competition_name"] == "Svenska Cupen Herrar"
    assert fields["tournament_stage_label"] == label
    assert fields["tournament_stage_type"] == stage_type
    assert fields["tournament_group"] == group


def test_sweden_cup_competitions_come_from_the_tournament_listing(monkeypatch):
    calls = []

    class Response:
        def json(self):
            return [{"CompetitionID": 45813}, {"CompetitionID": 44846}, {"CompetitionID": 44846}, {"Name": "no id"}]

    monkeypatch.setattr(scrape_sweden, "_get_api_config", lambda: scrape_sweden.ApiConfig("https://api.test/", "t"))
    monkeypatch.setattr(scrape_sweden, "request_with_retries", lambda method, url, **kwargs: calls.append(url) or Response())

    assert scrape_sweden.fetch_cup_competition_ids(7012, season_id=44) == [44846, 45813]
    assert calls == ["https://api.test/seasons/44/competitioncategories/7012/competitionswithmatchesandstandings"]


def test_sweden_cup_rows_carry_round_markers_including_unplayed_games(monkeypatch, tmp_path):
    matches = {
        45813: [{"MatchID": 1, "HomeTeam": "A", "AwayTeam": "B", "MatchDateTime": "2026-10-07T19:00:00"},
                {"MatchID": 2, "HomeTeam": "C", "AwayTeam": "D", "MatchDateTime": "2027-01-05T19:00:00",
                 "CompetitionName": "Svenska Cupen Herrar Semifinal 1"}],
    }
    details = {
        1: {"MatchID": 1, "HomeTeam": "A", "AwayTeam": "B", "HomeMatchTeamID": 10, "AwayMatchTeamID": 11,
            "MatchDateTime": "2026-10-07T19:00:00", "GoalsHomeTeam": 1, "GoalsAwayTeam": 0,
            "CompetitionName": "Svenska Cupen Herrar Kvartsfinaler",
            "Events": [{"MatchEventType": "Mål", "IsHomeTeam": True, "Period": 1, "Minute": 5, "Second": 0,
                        "GoalsHomeTeam": 1, "GoalsAwayTeam": 0, "PlayerName": "Alice Forward"}]},
        2: {"MatchID": 2, "HomeTeam": "C", "AwayTeam": "D", "MatchDateTime": "2027-01-05T19:00:00",
            "CompetitionName": "Svenska Cupen Herrar Semifinal 1", "Events": []},
    }

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    def fake_request(method, url, **kwargs):
        if url.endswith("/competitions/45813/matches"):
            return Response(matches[45813])
        return Response(details[int(url.rsplit("/", 1)[1])])

    monkeypatch.setattr(scrape_sweden, "_get_api_config", lambda: scrape_sweden.ApiConfig("https://api.test/", "t"))
    monkeypatch.setattr(scrape_sweden, "request_with_retries", fake_request)
    monkeypatch.setattr(scrape_sweden, "_fetch_competition", lambda api_root, headers, cid: {"Name": "Svenska Cupen Herrar Kvartsfinaler"})

    frame = scrape_sweden.scrape_competitions_events(
        [45813], str(tmp_path / "se.csv"), include_unplayed=True, cup_name="Svenska Cupen Herrar", cup=True
    )

    by_game = frame.drop_duplicates("game_id").set_index("game_id")
    assert by_game.loc[1, "event_type"] == "goal"
    assert by_game.loc[1, "tournament_stage_label"] == "Kvartsfinaler"
    assert by_game.loc[2, "event_type"] == "scheduled"
    assert by_game.loc[2, "tournament_stage_label"] == "Semifinal 1"
    assert set(frame["competition_name"]) == {"Svenska Cupen Herrar"}


def test_swiss_cup_game_ids_cover_every_round_and_dedupe(monkeypatch):
    class Response:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    rounds = {"data": {"regions": [{"rows": [
        {"cells": [{"text": ["1/16"], "link": {"set_in_context": {"round": 11}}}]},
        {"cells": [{"text": ["1/8"], "link": {"set_in_context": {"round": 12}}}]},
    ]}]}}
    games = {
        "11": {"data": {"regions": [{"rows": [{"id": 5, "cells": []}, {"id": 6, "cells": []}]}]}},
        "12": {"data": {"regions": [[{"rows": [{"id": 6, "cells": []}, {"id": 7, "cells": []}]}]]}},
    }

    def fake_get(url, params=None, timeout=0, attempts=0):
        if url.endswith("/cups/406200"):
            return Response(rounds)
        assert params["mode"] == "cup" and params["tournament_id"] == "406200"
        return Response(games[params["round"]])

    monkeypatch.setattr(scrape_switzerland, "_get_with_retries", fake_get)

    assert scrape_switzerland.fetch_cup_game_ids(406200) == [5, 6, 7]


def test_swiss_cup_header_gives_competition_and_round():
    details = scrape_switzerland.GameDetails(
        home_team="Red Devils March-Höfe", away_team="SV Wiler-Ersigen", game_date="2026-09-13", game_start_time="19:00",
        result_string="1:9", goals_home=1, goals_away=9, attendance=353, venue=None, venue_address=None,
        header_text="Red Devils March-Höfe - SV Wiler-Ersigen - Mobiliar Unihockey Cup Männer 1/16-Final 2026/27",
    )

    fields = scrape_switzerland._cup_fields(details, None)

    assert fields["competition_name"] == "Mobiliar Unihockey Cup Männer"
    assert fields["tournament_stage_label"] == "1/16-Final"
    assert scrape_switzerland._cup_fields(details, "Configured")["competition_name"] == "Configured"


def test_swiss_cup_keeps_every_round_and_drops_byes(monkeypatch, tmp_path):
    def details_for(game_id):
        away = {1: "Freilos", 2: "Floorball Köniz", 3: "???"}[game_id]
        return scrape_switzerland.GameDetails(
            home_team="SV Wiler-Ersigen", away_team=away, game_date="2026-09-13", game_start_time="19:00",
            result_string="1:0", goals_home=1, goals_away=0, attendance=1, venue=None, venue_address=None,
            header_text=f"SV Wiler-Ersigen - {away} - Mobiliar Unihockey Cup Männer Viertelfinal 2026/27",
        )

    current = {}
    monkeypatch.setattr(scrape_switzerland, "_fetch_block", lambda game_id, block, **kw: current.setdefault("id", game_id) and str(game_id))
    monkeypatch.setattr(scrape_switzerland, "_parse_game_details", lambda html: details_for(int(html)))
    monkeypatch.setattr(scrape_switzerland, "_build_player_name_lookup", lambda game_id, details: {})
    monkeypatch.setattr(
        scrape_switzerland,
        "_parse_game_events",
        lambda html, game_id, details, player_name_lookup=None: _game_rows(game_id, details.home_team, details.away_team),
    )

    frame = scrape_switzerland.scrape_games(
        [1, 2, 3], str(tmp_path / "ch.csv"), phase_filter="cup", cup=True, cup_name="Mobiliar Unihockey Cup Männer"
    )

    assert set(frame["game_id"]) == {2}
    assert set(frame["tournament_stage_label"]) == {"Viertelfinal"}


def test_czech_cup_keeps_every_round_and_marks_rows(monkeypatch, tmp_path):
    matches = [
        scrape_czech.MatchSummary(1, "A", "B", "6:5", "odehráno", "1. kolo", "2026-08-06", None),
        scrape_czech.MatchSummary(2, "C", "D", "3:2", "odehráno", "osmifinále", "2026-10-31", None),
        scrape_czech.MatchSummary(3, "E", "F", None, None, "čtvrtfinále", "2027-01-10", None),
    ]
    monkeypatch.setattr(scrape_czech, "fetch_match_list", lambda url, year, session=None: matches)
    monkeypatch.setattr(
        scrape_czech,
        "fetch_match_events",
        lambda match_id, date, time, status, session=None: _game_rows(match_id, f"H{match_id}", f"G{match_id}"),
    )

    frame = scrape_czech.scrape_competition(
        ["https://example.test"], str(tmp_path / "cz.csv"), 2026, include_unplayed=True, phase="cup", cup_name="Pohár ČF mužů"
    )

    labels = frame.drop_duplicates("game_id").set_index("game_id")["tournament_stage_label"].to_dict()
    assert labels == {1: "1. kolo", 2: "osmifinále", 3: "čtvrtfinále"}
    assert set(frame["competition_name"]) == {"Pohár ČF mužů"}


def test_german_cup_rounds_come_from_the_spieltag(tmp_path):
    games = {
        1: {"home_team_name": "A", "guest_team_name": "B", "date": "2026-10-31", "start_time": "14:00", "audience": 5,
            "game_status": "ended", "result_string": "2:1", "players": {},
            "events": [{"event_type": "goal", "event_team": "home", "period": 1, "sortkey": "1-05:00", "home_goals": 1,
                        "guest_goals": 0, "number": 7}]},
        2: {"home_team_name": "C", "guest_team_name": "D", "date": "2026-12-19", "start_time": "13:00", "game_status": None,
            "players": {}, "events": []},
    }
    schedule = [{"game_id": 1, "game_day": 3}, {"game_id": 2, "game_day": 4}]

    frame = scrape._scrape_events_with(
        lambda path: schedule if path.endswith("schedule.json") else games[int(path.rsplit("/", 1)[1])],
        "leagues/2451/schedule.json",
        str(tmp_path / "de.csv"),
        cup=True,
        cup_name="FD-Pokal Herren",
    )

    labels = frame.drop_duplicates("game_id").set_index("game_id")["tournament_stage_label"].to_dict()
    assert labels == {1: "Round 3", 2: "Round 4"}
    assert set(frame["competition_name"]) == {"FD-Pokal Herren"}


def test_cup_import_rejects_backends_without_a_cup_source(tmp_path):
    for backend in ("slovakia", "latvia"):
        with pytest.raises(ValueError, match="No cup source"):
            pipeline._scrape_cup(
                backend=backend, league_id=None, raw_csv=tmp_path / "x.csv", cup_name=None, cup_sweden_category_id=None,
                cup_swiss_tournament_ids=None, czech_schedule_urls=None, czech_season_start_year=None,
            )


# --- config -----------------------------------------------------------------------------------


def test_cup_configs_cover_the_sources_we_have():
    assert [path.name for path in CUP_CONFIGS] == [
        "czech-cup-26-27.json", "czech-cup-women-26-27.json",
        "finland-cup-26-27.json", "finland-cup-women-26-27.json",
        "germany-cup-26-27.json", "germany-cup-women-26-27.json",
        "sweden-cup-26-27.json", "sweden-cup-women-26-27.json",
        "switzerland-cup-26-27.json", "switzerland-cup-women-26-27.json",
    ]


@pytest.mark.parametrize("path", CUP_CONFIGS, ids=lambda path: path.name)
def test_cup_config_is_a_cup_phase_with_a_marker_name(path):
    config = json.loads(path.read_text(encoding="utf-8"))

    assert config["phase"] == CUP_PHASE
    assert config["cup"]["competition_name"]
    assert config["season"].endswith("26-27")


def test_apply_league_config_exposes_the_cup_selectors():
    class Args:
        backend = "saisonmanager"
        league_id = None
        competition_id = None
        season = None
        phase = "regular-season"
        data_dir = "data"
        content_dir = "content"
        skip_scrape = False
        swiss_game_ids = swiss_schedule_url = swiss_league = swiss_season = swiss_game_class = swiss_group = swiss_start_round = None
        swiss_mode = "list"
        czech_schedule_url = czech_season_start_year = finland_schedule_url = finland_playoff_start_date = None
        slovakia_schedule_url = slovakia_regular_season_end = slovakia_regular_season_games_per_team = None
        latvia_calendar_url = latvia_season_start_year = None

    swiss = Args()
    apply_league_config(swiss, load_league_config(ROOT / "config/leagues/switzerland-cup-26-27.json"))
    sweden = Args()
    apply_league_config(sweden, load_league_config(ROOT / "config/leagues/sweden-cup-women-26-27.json"))

    assert (swiss.phase, swiss.season, swiss.cup_swiss_tournament_ids) == ("cup", "ch-26-27", [406200])
    assert (sweden.cup_name, sweden.cup_sweden_category_id) == ("Svenska Cupen Damer", 7013)


# --- separation from league data ---------------------------------------------------------------


def _write_csv(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_cup_pipeline_publishes_game_pages_only_and_leaves_league_files_alone(tmp_path):
    data_dir, content_dir = tmp_path / "data", tmp_path / "content"
    league_dir = content_dir / "se-26-27-regular-season"
    (league_dir / "teams").mkdir(parents=True)
    table_page = league_dir / "teams" / "storvreta-ibk-se-26-27-regular-season.md"
    table_page.write_text("league team page", encoding="utf-8")
    marker = {"competition_name": "Svenska Cupen Herrar", "tournament_stage_type": "elimination", "tournament_stage_label": "Kvartsfinaler"}
    _write_csv(data_dir / "data_se-26-27_cup.csv", _game_rows(7, "Storvreta IBK", "Mullsjö AIS", **marker))

    result = pipeline.run_pipeline(
        league_id=None, season="se-26-27", phase="cup", backend="sweden",
        data_dir=str(data_dir), content_dir=str(content_dir), skip_scrape=True, database_url=None,
    )

    cup_dir = content_dir / "se-26-27-cup"
    assert (result["games_written"], result["teams_written"], result["league_written"]) == (1, 0, 0)
    assert sorted(path.name for path in cup_dir.iterdir()) == ["games"]
    page = next((cup_dir / "games").glob("*.md")).read_text(encoding="utf-8")
    assert "Category: se-26-27-cup, game" in page
    assert "competition_name: Svenska Cupen Herrar" in page
    assert "tournament_stage_label: Kvartsfinaler" in page
    assert table_page.read_text(encoding="utf-8") == "league team page"
    assert not (league_dir / "games").exists()


def test_league_standings_are_built_from_league_events_only(tmp_path):
    league = _game_rows(1, "Team A", "Team B", 2, 1, tournament_stage_type=None)
    cup = _game_rows(2, "Team A", "Team C", 9, 0, competition_name="Cup", tournament_stage_type="elimination")
    league_csv = _write_csv(tmp_path / "data_se-26-27_regular_season.csv", league)
    _write_csv(tmp_path / "data_se-26-27_cup.csv", cup)

    stats = run_stats_pipeline(input_csv_path=str(league_csv), output_dir=str(tmp_path / "out"), season="se-26-27", phase="regular-season")

    assert set(stats["team_stats_enhanced"]) == {"Team A", "Team B"}
    assert [game["game_id"] for game in stats["game_stats"]] == [1]


def test_cup_markdown_generation_skips_team_and_league_pages(tmp_path):
    csv = _write_csv(tmp_path / "data_ch-26-27_cup.csv", _game_rows(3, "A", "B"))
    run_stats_pipeline(input_csv_path=str(csv), output_dir=str(tmp_path), season="ch-26-27", phase="cup")

    written = generate_markdown_files(
        game_stats_path=str(tmp_path / "game_stats.json"),
        team_stats_path=str(tmp_path / "team_stats_enhanced.json"),
        league_stats_path=str(tmp_path / "league_averages.json"),
        output_games_dir=str(tmp_path / "content" / "ch-26-27-cup" / "games"),
        output_teams_dir=str(tmp_path / "content" / "ch-26-27-cup" / "teams"),
        output_liga_dir=str(tmp_path / "content" / "ch-26-27-cup" / "liga"),
        season="ch-26-27",
        phase="cup",
    )

    assert written == (1, 0, 0)
    assert not (tmp_path / "content" / "ch-26-27-cup" / "teams").exists()
    assert not (tmp_path / "content" / "ch-26-27-cup" / "liga").exists()


def test_player_stats_ignore_cup_event_files_and_leave_out_cup_players_without_a_league_row(monkeypatch):
    for league_file in ("data_se-26-27_regular_season.csv", "data_26-27_playoffs.csv"):
        assert build_player_stats.FILE_PATTERN.match(league_file)
    for cup_file in ("data_se-26-27_cup.csv", "data_26-27_cup.csv", "data_chw-26-27_cup.csv"):
        assert not build_player_stats.FILE_PATTERN.match(cup_file)

    def event(season, phase, scorer):
        return {"season": season, "phase": phase, "event_type": "goal", "event_team": "A", "game_id": 1,
                "home_team_name": "A", "away_team_name": "B", "scorer_name": scorer, "assist_name": "", "penalty_player_name": ""}

    events = pd.DataFrame(
        [event("se-26-27", "regular-season", "League Scorer"), event("se-26-27", "cup", "Cup Scorer")]
    )
    written = {}
    monkeypatch.setattr(player_builder, "_load_events", lambda url: events)
    monkeypatch.setattr(player_builder, "_load_all_game_rosters", lambda url: pd.DataFrame())
    monkeypatch.setattr(player_builder, "_load_stored_player_stats", lambda url: pd.DataFrame())
    monkeypatch.setattr(player_builder, "_lineup_rows_for_prefix", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(player_builder, "_replace_player_stats_table", lambda url, frame: written.setdefault("frame", frame) is not None and len(frame))

    player_builder.build_player_stats_from_postgres(database_url="postgresql://test")

    frame = written["frame"]
    assert set(frame["phase"]) == {"regular-season"}
    assert frame["player"].tolist() == ["League Scorer"]


def test_postgres_rebuild_reads_cup_csvs_as_their_own_phase(monkeypatch, tmp_path):
    from src import build_postgres

    synced = []
    _write_csv(tmp_path / "data_se-26-27_cup.csv", _game_rows(1, "A", "B"))
    monkeypatch.setattr(build_postgres, "run_stats_pipeline", lambda **kwargs: {"phase_seen": kwargs["phase"]})
    monkeypatch.setattr(
        build_postgres,
        "sync_pipeline_outputs",
        lambda **kwargs: synced.append((kwargs["season"], kwargs["phase"], Path(kwargs["input_csv_path"]).stem)) or {
            key: 0 for key in ("events", "game_stats", "team_stats", "playoff_team_stats", "playdown_team_stats", "top4_team_stats", "league_stats")
        },
    )

    build_postgres.rebuild_from_event_csvs(database_url="postgresql://test", data_dir=str(tmp_path))

    assert synced == [("se-26-27", "cup", "data_se-26-27_cup")]


def test_cup_category_stays_outside_league_categories_and_gets_a_page_path():
    import pelicanconf as conf
    from plugins import insights

    assert not insights.CATEGORY_PATTERN.match("ch-26-27-cup")
    assert insights.CATEGORY_PATTERN.match("ch-26-27-regular-season")
    assert "cup" not in conf.SEASON_PHASES
    context = conf.league_context("chw-26-27-cup")
    assert (context["prefix"], context["season"], context["phase"]) == ("chw-", "26-27", "cup")
    assert conf.league_context("26-27-cup")["name"] == "Germany"
    for prefix in conf.CUP_PREFIXES:
        assert f"{prefix}26-27-cup/games" in conf.ARTICLE_PATHS
        assert f"{prefix}26-27-cup/teams" not in conf.ARTICLE_PATHS
    assert conf.category2string("se-26-27-cup") == "Sweden 26/27 Cup"


def test_cup_games_stay_out_of_team_calendars_and_form():
    import sys
    from datetime import datetime
    from types import SimpleNamespace

    sys.path.insert(0, str(ROOT / "plugins"))
    import share_assets

    def article(slug, category, kind="game", **fields):
        return SimpleNamespace(slug=slug, url=f"{slug}.html", category=SimpleNamespace(shortname=category, slug=category),
                               type=kind, date=datetime(2026, 10, 7), **fields)

    game_fields = dict(game_state="played", home_team="A", away_team="B", home_goals="3", away_goals="2",
                       start_time="19:00", game_id="1")
    articles = [
        article("league-game", "se-26-27-regular-season", **game_fields),
        article("cup-game", "se-26-27-cup", **{**game_fields, "game_id": "2", "home_goals": "0", "away_goals": "9"}),
        article("team-a", "se-26-27-regular-season", kind="team", team="A", title="A", rank="1", points="3", games="1"),
    ]
    settings = {
        "CURRENT_SEASON": "26-27",
        "LEAGUES": [{"prefix": "se-", "name": "Sweden", "title": "Sweden · SSL", "division": "men"}],
        "JINJA_FILTERS": {"category2string": lambda slug: slug, "crest_index": lambda name: 1, "team_initials": lambda name: name},
        "SITEURL": "",
    }

    share_assets.collect(SimpleNamespace(settings=settings, articles=articles))

    assert "og/cup-game.png" in share_assets._state.images
    games = {game_id for calendar in share_assets._state.calendars.values() for game_id in calendar["games"]}
    assert games == {"1"}
    assert articles[2].share_team["form"] == ["W"]


def test_cup_games_stay_out_of_the_head_to_head():
    import sys
    from datetime import date
    from types import SimpleNamespace

    sys.path.insert(0, str(ROOT / "plugins"))
    import pelicanconf as conf
    import team_versus
    from src import player_insights as pi

    def game(slug, category, home, away, home_goals, away_goals):
        return SimpleNamespace(
            slug=slug, url=f"{slug}.html", date=date(2026, 10, 7), type="game", game_state="played", game_id=slug,
            home_team=home, away_team=away, home_goals=str(home_goals), away_goals=str(away_goals), result_string="",
            game_events_b64=pi.encode_events([]), category=SimpleNamespace(slug=category),
        )

    articles = [
        game("league", "se-26-27-regular-season", "A", "B", 3, 2),
        game("cup", "se-26-27-cup", "A", "B", 0, 9),
        game("cup-only", "se-26-27-cup", "C", "D", 1, 0),
    ]
    settings = {
        "LEAGUES": [{"prefix": "se-", "name": "Sweden", "title": "Sweden · SSL", "division": "men"}],
        "JINJA_FILTERS": {"league_context": conf.league_context},
    }

    result = team_versus.build(SimpleNamespace(settings=settings, articles=articles))

    payload = result["payloads"]["se"]
    assert [team["name"] for team in payload["teams"]] == ["A", "B"]
    assert [row["score"] for row in payload["pairs"]["0-1"]["results"]] == ["3:2"]


def test_cup_games_get_a_game_story_that_starts_level_and_league_games_are_left_alone():
    import sys
    from datetime import date
    from types import SimpleNamespace

    sys.path.insert(0, str(ROOT / "plugins"))
    import insights
    import pelicanconf as conf
    from src import player_insights as pi

    def goal(minute, side, team):
        return {"minute": minute, "period": 1, "team": team, "side": side, "score": "", "event_kind": "goal", "title": "Scorer", "tag": "regular"}

    def game(slug, category):
        return SimpleNamespace(
            slug=slug, url=f"{slug}.html", date=date(2026, 10, 7), game_state="played", game_id=slug, type="game",
            home_team="A", away_team="B", home_goals="2", away_goals="1", start_time="19:00",
            game_events_b64=pi.encode_events([goal("03:00", "home", "A"), goal("08:00", "away", "B"), goal("15:00", "home", "A")]),
            timeline_max_minute="60.0", category=SimpleNamespace(slug=category),
        )

    cup, league = game("cup", "se-26-27-cup"), game("league", "se-26-27-regular-season")

    insights._attach_cup_stories({"se-26-27-cup": [cup], "se-26-27-regular-season": [league]}, conf.league_context)

    assert cup.game_story["even_start"] is True
    assert cup.game_story["winner"] == "A"
    assert [moment["team"] for moment in cup.game_story["key_moments"]]
    assert not hasattr(league, "game_story")


# --- Finland: Suomen Cup from the Torneopal result service --------------------------------------


def _torneopal_listed(match_id="1", status="Played", **overrides):
    return {
        "match_id": match_id, "status": status, "team_A_name": "SBS Masku", "team_B_name": "TPS",
        "date": "2026-10-18", "time": "16:00:00", "fs_A": "4", "fs_B": "6", "attendance": "255",
        "venue_name": "Hemmingin Liikuntahalli", "category_name": "Suomen Cup miehet", "group_name": "Suomen Cup miehet",
        "group_type": "knockout_final", "round_name": "Kahdeksasvälierä", **overrides,
    }


def _torneopal_event(code, side, event_id, period=1, seconds=257, score=(0, 1), name="Loponen Eetu", player_id="1", **extra):
    return {"code": code, "team": side, "event_id": event_id, "connected_event_id": "0", "period": str(period),
            "time_sec": seconds, "s_A": score[0], "s_B": score[1], "player_name": name, "player_id": player_id,
            "shirt_number": "9", **extra}


def _torneopal_detail(events):
    return {"events": events, "lineups": [
        {"player_id": "1", "first_name": "Eetu", "last_name": "Loponen"},
        {"player_id": "2", "first_name": "Kasper", "last_name": "Kulmala"},
        {"player_id": "3", "first_name": "Alex", "last_name": "Eklund"},
    ]}


def test_torneopal_game_rows_cover_goals_assists_penalties_and_shootout_winner():
    events = [
        _torneopal_event("vaihto", "B", "10"),
        _torneopal_event("maali", "B", "11", score=(0, 1)),
        _torneopal_event("syotto", "B", "12", name="Kulmala Kasper", player_id="2", connected_event_id="11"),
        _torneopal_event("2min", "A", "13", seconds=1089, name="Eklund Alex", player_id="3", description="ETA"),
        _torneopal_event("rpkmaali", "A", "14", period=5, seconds=2),
        _torneopal_event("maali", "A", "15", period=5, seconds=0, score=(4, 4), name="", player_id=""),
    ]

    rows = scrape_torneopal.match_rows(_torneopal_listed(), _torneopal_detail(events))

    assert [(row["event_type"], row["event_team"], row["sortkey"]) for row in rows] == [
        ("goal", "TPS", "1-04:17"), ("penalty", "SBS Masku", "1-18:09"), ("goal", "SBS Masku", "5-00:00"),
    ]
    goal, penalty, shootout = rows
    assert (goal["scorer_name"], goal["assist_name"], goal["home_goals"], goal["guest_goals"]) == ("Eetu Loponen", "Kasper Kulmala", 0, 1)
    assert (penalty["penalty_type"], penalty["penalty_player_name"]) == ("penalty_2", "Alex Eklund")
    assert shootout["period"] == 5 and shootout["scorer_name"] is None
    assert {row["competition_name"] for row in rows} == {"Suomen Cup miehet"}
    assert {row["tournament_stage_label"] for row in rows} == {"Kahdeksasvälierä"}
    assert rows[0]["result_string"] == "4:6" and rows[0]["attendance"] == 255


def test_torneopal_regional_groups_keep_their_group_and_games_without_scorers_keep_the_score():
    listed = _torneopal_listed(group_name="ES1", group_type="group_stage", round_name="SBS Graniitti", fs_A="3", fs_B="11")

    rows = scrape_torneopal.match_rows(listed, _torneopal_detail([_torneopal_event("vaihto", "B", "10")]))

    assert len(rows) == 1 and rows[0]["event_type"] == "result"
    assert (rows[0]["home_goals"], rows[0]["guest_goals"]) == (3, 11)
    assert (rows[0]["tournament_stage_type"], rows[0]["tournament_stage_label"], rows[0]["tournament_group"]) == ("group-stage", "ES1", "ES1")


def test_torneopal_planned_games_are_scheduled_and_forfeits_and_open_slots_are_dropped():
    planned = scrape_torneopal.match_rows(_torneopal_listed(status="Planned", fs_A="", fs_B=""), None)

    assert [row["event_type"] for row in planned] == ["scheduled"]
    assert planned[0]["tournament_stage_label"] == "Kahdeksasvälierä"
    assert scrape_torneopal.match_rows(_torneopal_listed(status="Forfeited"), None) == []
    assert scrape_torneopal.match_rows(_torneopal_listed(status="Planned", date="", fs_A="", fs_B=""), None) == []
    assert scrape_torneopal.is_placeholder_team("Voittaja ottelusta SB Naantali - TPS (3204)")
    assert scrape_torneopal.is_placeholder_team("")
    assert not scrape_torneopal.is_placeholder_team("Voima")


def test_torneopal_cup_scrape_skips_undrawn_slots_and_only_loads_played_games(tmp_path):
    loaded = []

    class FakeClient:
        def fetch_matches(self, category_id, competition_id):
            return [
                _torneopal_listed("1"),
                _torneopal_listed("2", status="Planned", fs_A="", fs_B=""),
                _torneopal_listed("3", status="Planned", team_A_name="Voittaja ottelusta X (3204)"),
            ]

        def fetch_match(self, match_id, game_date):
            loaded.append(match_id)
            return _torneopal_detail([_torneopal_event("maali", "B", "11")])

        def close(self):
            raise AssertionError("a client passed in stays open")

    frame = scrape_torneopal.scrape_cup(366, str(tmp_path / "fi.csv"), client=FakeClient())

    assert loaded == ["1"]
    assert sorted(frame["game_id"].unique()) == [1, 2]


def test_torneopal_client_caches_settled_games_and_rereads_recent_ones(tmp_path):
    from datetime import date

    captured = []

    class Client(scrape_torneopal.TorneopalWebClient):
        def _capture(self, url, call, **params):
            captured.append((url, call, params))
            return {"match": {"status": "Played", "events": [], "match_id": params["match_id"]}}

    client = Client(cache_dir=tmp_path, delay_seconds=0, today=date(2026, 11, 2))

    client.fetch_match("7", "2026-10-18")
    client.fetch_match("7", "2026-10-18")
    assert len(captured) == 1 and captured[0][1] == "getMatch"

    client.fetch_match("8", "2026-10-31")
    client.fetch_match("8", "2026-10-31")
    assert len(captured) == 3


def _stats_event(season, phase, scorer, team="A", game_id=1):
    return {"season": season, "phase": phase, "event_type": "goal", "event_team": team, "game_id": game_id,
            "home_team_name": team, "away_team_name": "B", "scorer_name": scorer, "assist_name": "", "penalty_player_name": ""}


def test_cup_stats_go_to_players_with_a_league_row_for_the_same_club(monkeypatch, capsys):
    events = pd.DataFrame(
        [
            _stats_event("se-26-27", "regular-season", "Sven Svensson", "A", 1),
            _stats_event("se-26-27", "cup", "Sven Svensson", "A", 2),
            _stats_event("se-26-27", "cup", "Sven Svensson", "A", 3),
            _stats_event("se-26-27", "cup", "Lower Leaguer", "Lower League FBC", 5),  # no league row at all
        ]
    )
    written = {}
    monkeypatch.setattr(player_builder, "_load_events", lambda url: events)
    monkeypatch.setattr(player_builder, "_load_all_game_rosters", lambda url: pd.DataFrame())
    monkeypatch.setattr(player_builder, "_load_stored_player_stats", lambda url: pd.DataFrame())
    monkeypatch.setattr(player_builder, "_lineup_rows_for_prefix", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(player_builder, "_replace_player_stats_table", lambda url, frame: written.setdefault("frame", frame) is not None and len(frame))

    player_builder.build_player_stats_from_postgres(database_url="postgresql://test")

    frame = written["frame"]
    cup = frame[frame["phase"] == "cup"]
    assert cup["player"].tolist() == ["Sven Svensson"]
    assert cup.iloc[0]["goals"] == 2 and cup.iloc[0]["team"] == "A"
    assert cup.iloc[0]["player_uid"] == frame[frame["phase"] == "regular-season"].iloc[0]["player_uid"]
    assert "left out 1 players" in capsys.readouterr().out


def test_match_cup_rows_compares_club_and_season_and_counts_the_players_left_out():
    league = pd.DataFrame([
        {"player_uid": "p1", "season": "ch-26-27", "team": "Club A"},
        {"player_uid": "p2", "season": "ch-25-26", "team": "Club B"},
        {"player_uid": "p3", "season": "ch-26-27", "team": "Club C / Club D"},
    ])
    cup = pd.DataFrame([
        {"player_uid": "p1", "season": "ch-26-27", "team": "Club A"},
        {"player_uid": "p2", "season": "ch-26-27", "team": "Club B"},  # league row is from an earlier season
        {"player_uid": "p3", "season": "ch-26-27", "team": "Club D"},  # joined clubs count
        {"player_uid": "p9", "season": "ch-26-27", "team": "Club A"},
    ])

    kept, dropped = player_builder.match_cup_rows(cup, league)

    assert kept["player_uid"].tolist() == ["p1", "p3"]
    assert dropped == 2


def _player_rows(**cup):
    base = {"player_uid": "player-x", "player": "Pia Player", "team": "Club A", "league": "Switzerland"}
    rows = [
        {**base, "season": "ch-25-26", "phase": "regular-season", "games": "20", "goals": "9", "assists": "9", "points": "18", "pim": "4"},
        {**base, "season": "ch-26-27", "phase": "regular-season", "games": "10", "goals": "5", "assists": "3", "points": "8", "pim": "2"},
        {**base, "season": "ch-26-27", "phase": "playoffs", "games": "2", "goals": "1", "assists": "1", "points": "2", "pim": "0"},
    ]
    if cup:
        rows.append({**base, "season": "ch-26-27", "phase": "cup", **cup})
    return rows


def test_player_page_adds_up_the_current_season_over_all_competitions_and_keeps_the_cup_in_the_history():
    from src.generate_player_markdown import _rows_to_markdown

    cup = {"games": "3", "goals": "4", "assists": "1", "points": "5", "pim": "2"}
    markdown, _ = _rows_to_markdown(_player_rows(**cup), "players", "2026-11-02")
    fields = dict(line.split(": ", 1) for line in markdown.splitlines() if ": " in line)

    assert (fields["current_games"], fields["current_goals"], fields["current_points"], fields["current_pim"]) == ("15", "10", "15", "4")
    assert (fields["cup_games"], fields["cup_goals"], fields["cup_assists"], fields["cup_points"], fields["cup_pim"]) == ("3", "4", "1", "5", "2")
    assert (fields["regular_games"], fields["playoff_games"]) == ("10", "2")
    assert "ch-26-27|cup|Switzerland|Club A|3|4|1|5|2" in fields["history_rows_csv"].split("||")
    # career_* stays league only, so the player comparison and the search index do not change
    assert (fields["career_games"], fields["career_goals"]) == ("32", "15")
    # without cup games the page is as before
    plain, _ = _rows_to_markdown(_player_rows(), "players", "2026-11-02")
    assert "cup_games: 0" in plain and "|cup|" not in plain


def test_player_page_shows_the_current_season_in_the_boxes_not_the_career():
    template = (ROOT / "themes" / "my-theme" / "templates" / "player.html").read_text(encoding="utf-8")
    boxes = template.split('<section class="kpi-grid">')[0]

    assert "article.current_games" in boxes and "article.current_points" in boxes
    assert "career_" not in boxes
    assert "all competitions" in boxes


def test_cup_only_players_get_no_page_and_cup_games_stay_out_of_the_player_rankings(tmp_path, monkeypatch):
    import src.generate_player_markdown as page_module
    import src.generate_player_stats_index_markdown as index_module

    cup_only = {"player_uid": "player-cup", "player": "Cup Only", "team": "Low FBC", "league": "Switzerland",
                "season": "ch-26-27", "phase": "cup", "rank": "1", "games": "2", "goals": "3", "assists": "0", "points": "3", "pim": "0"}
    rows = [
        {**cup_only, "player_uid": "player-x", "player": "Pia Player", "team": "Club A", "phase": "regular-season", "rank": "1"},
        {**cup_only, "player_uid": "player-x", "player": "Pia Player", "team": "Club A", "rank": "1"},
        cup_only,
    ]
    monkeypatch.setattr(page_module, "_load_rows_from_postgres", lambda url: rows)
    monkeypatch.setattr(page_module, "_load_alias_pairs_from_postgres", lambda url: [])
    monkeypatch.setattr(index_module, "_load_rows_from_postgres", lambda url: rows)

    pages = tmp_path / "players"
    page_module.generate_player_markdown(database_url="x", output_dir=str(pages))
    assert [path.name for path in pages.glob("*.md")] == ["player-x.md"]

    rankings = tmp_path / "player-stats"
    index_module.generate_player_stats_index_markdown(database_url="x", output_dir=str(rankings))
    assert [path.name for path in rankings.glob("*.md")] == ["ch-26-27-regular-season-players.md"]


def test_player_comparison_stays_with_the_league_when_the_page_counts_the_cup():
    from src import player_compare

    meta = {"slug": "player-x", "player": "Pia Player", "current_season": "ch-26-27", "current_games": "15", "current_goals": "10",
            "current_assists": "5", "current_points": "15", "current_pim": "4", "cup_games": "3", "cup_goals": "4",
            "cup_assists": "1", "cup_points": "5", "cup_pim": "2", "career_games": "32", "career_goals": "15"}

    payload = player_compare.player_payload(meta)

    assert payload["current"] == {"games": 12, "goals": 6, "assists": 4, "points": 10, "pim": 2}
    assert payload["career"]["games"] == 32


def test_cup_game_pages_link_their_teams_to_the_league_team_pages():
    import sys
    from datetime import datetime
    from types import SimpleNamespace as Obj

    sys.path.insert(0, str(ROOT / "plugins"))
    import seo
    from pelicanconf import category_seo_label, league_context

    game = Obj(type="game", slug="g", url="g.html", category=Obj(slug="ch-26-27-cup"), home_team="SV Wiler-Ersigen",
               away_team="Lower League FBC", date=datetime(2026, 11, 22), start_time="19:30")
    settings = {"SITEURL": "https://stats.example.com", "JINJA_FILTERS": {
        "league_context": league_context, "category_seo_label": category_seo_label}}
    pages = {("ch-26-27-regular-season", "svwilerersigen"): "wiler.html"}

    seo.collect(Obj(articles=[game], settings=settings, context={"TEAM_PAGES": pages}))

    assert game.seo_home_url == "wiler.html"
    assert game.seo_away_url == ""  # lower league: no team page, so no link


def _cup_game(round_name, home, away, home_goals, away_goals, day, **extra):
    from datetime import datetime
    from types import SimpleNamespace as Obj

    return Obj(type="game", url=f"{home}-{away}.html", category=Obj(shortname="ch-26-27-cup"), date=datetime(2026, 11, day),
               home_team=home, away_team=away, home_goals=str(home_goals), away_goals=str(away_goals), game_state="played",
               tournament_stage_label=round_name, competition_name="Mobiliar Unihockey Cup Männer", **extra)


def test_team_pages_list_the_cup_games_of_their_team_and_only_those():
    import sys
    from types import SimpleNamespace as Obj

    sys.path.insert(0, str(ROOT / "plugins"))
    import cup_games

    games = [
        _cup_game("1/16-Final", "Club A", "Low FBC", 7, 2, 1),
        _cup_game("1/8-Final", "Club B", "Club A", 4, 3, 8, home_goals_in_overtime="1"),
        _cup_game("1/8-Final", "Club C", "Club D", 1, 0, 8),
    ]
    team_a = Obj(type="team", team="Club A", category=Obj(shortname="ch-26-27-regular-season"))
    team_a_other_season = Obj(type="team", team="Club A", category=Obj(shortname="ch-25-26-regular-season"))
    team_e = Obj(type="team", team="Club E", category=Obj(shortname="ch-26-27-regular-season"))

    cup_games.collect(Obj(articles=[*games, team_a, team_a_other_season, team_e]))

    rows = team_a.cup_games
    assert [(row["round"], row["opponent"], row["outcome"], row["decision"], row["home"]) for row in rows] == [
        ("1/16-Final", "Low FBC", "W", "", True),
        ("1/8-Final", "Club B", "L", "OT", False),
    ]
    assert (rows[1]["goals_for"], rows[1]["goals_against"]) == (3, 4)
    assert not hasattr(team_a_other_season, "cup_games") and not hasattr(team_e, "cup_games")

    template = (ROOT / "themes" / "my-theme" / "templates" / "team.html").read_text(encoding="utf-8")
    assert "{% if article.cup_games %}" in template


def test_cup_game_stats_carry_no_per_opponent_columns(tmp_path):
    # points_against has one entry per team; for a cup of 100+ teams that added hundreds of
    # game_stats columns per season and hit Postgres' 1600 column limit (nightly run, 2 Nov 2026).
    cup = _game_rows(1, "Team A", "Team B", 3, 1) + _game_rows(2, "Team C", "Team D", 2, 0) + _game_rows(3, "Team A", "Team C", 1, 0)
    csv = _write_csv(tmp_path / "data_ch-26-27_cup.csv", cup)
    league_csv = _write_csv(tmp_path / "data_ch-26-27_regular_season.csv", cup)

    cup_stats = run_stats_pipeline(input_csv_path=str(csv), output_dir=str(tmp_path / "cup"), season="ch-26-27", phase="cup")
    league_stats = run_stats_pipeline(input_csv_path=str(league_csv), output_dir=str(tmp_path / "league"), season="ch-26-27", phase="regular-season")

    for game in cup_stats["game_stats"]:
        for key in ("home_stats", "away_stats", "home_pregame_stats", "away_pregame_stats"):
            assert "points_against" not in game[key]
    assert any("points_against" in game["home_stats"] for game in league_stats["game_stats"])
