from pathlib import Path

import src.generate_player_markdown as generate_player_markdown_module
from src.generate_player_markdown import generate_player_markdown


def test_generate_player_markdown_writes_expected_file(tmp_path: Path):
    csv_path = tmp_path / "players.csv"
    csv_path.write_text(
        "player,team,league,season,games,goals,assists,points\n"
        "Max Muster,Test Club,Demo League,25-26,10,8,7,15\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "content" / "players"
    written, removed = generate_player_markdown(
        csv_path=str(csv_path),
        output_dir=str(output_dir),
        default_category="players",
    )

    assert written == 1
    assert removed == 0

    target = output_dir / "max-muster.md"
    assert target.exists()

    content = target.read_text(encoding="utf-8")
    assert "type: player" in content
    assert "player: Max Muster" in content
    assert "team: Test Club" in content
    assert "points: 15" in content


def test_generate_player_markdown_groups_seasons_into_single_player_page(tmp_path: Path):
    csv_path = tmp_path / "players.csv"
    csv_path.write_text(
        "player_uid,player,team,league,season,phase,games,goals,assists,points,pim\n"
        "max-muster-sweden,Max Muster,Club A,Sweden SSL,se-24-25,regular-season,20,10,10,20,12\n"
        "max-muster-sweden,Max Muster,Club A,Sweden SSL,se-25-26,regular-season,22,12,11,23,10\n"
        "max-muster-sweden,Max Muster,Club A,Sweden SSL,se-25-26,playoffs,6,3,4,7,2\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "content" / "players"
    written, removed = generate_player_markdown(
        csv_path=str(csv_path),
        output_dir=str(output_dir),
        default_category="players",
    )

    assert written == 1
    assert removed == 0

    target = output_dir / "max-muster-sweden.md"
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "current_season: se-25-26" in content
    assert "previous_season: se-24-25" in content
    assert "current_points: 30" in content
    assert "regular_points: 23" in content
    assert "playoff_points: 7" in content
    assert "previous_points: 20" in content


def test_generate_player_markdown_merges_full_history_for_partial_source(tmp_path: Path):
    partial_csv_path = tmp_path / "players_wfc.csv"
    partial_csv_path.write_text(
        "player_uid,player,team,league,season,phase,games,goals,assists,points,pim\n"
        "player-1,Gabriel Kohonen,Sweden,IFF WFC,wfc-2024,regular-season,2,2,3,5,0\n"
        "player-1,Gabriel Kohonen,Sweden,IFF WFC,wfc-2024,playoffs,1,1,0,1,0\n",
        encoding="utf-8",
    )

    full_csv_path = tmp_path / "players_full.csv"
    full_csv_path.write_text(
        "player_uid,player,team,league,season,phase,games,goals,assists,points,pim\n"
        "player-1,Gabriel Kohonen,Storvreta IBK,Sweden,se-25-26,regular-season,26,22,50,72,16\n"
        "player-1,Gabriel Kohonen,Storvreta IBK,Sweden,se-25-26,playoffs,5,6,7,13,5\n"
        "player-1,Gabriel Kohonen,Sweden,IFF WFC,wfc-2024,regular-season,2,2,3,5,0\n"
        "player-1,Gabriel Kohonen,Sweden,IFF WFC,wfc-2024,playoffs,1,1,0,1,0\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "content" / "players"
    written, removed = generate_player_markdown(
        csv_path=str(partial_csv_path),
        merge_csv_path=str(full_csv_path),
        output_dir=str(output_dir),
        default_category="players",
        season_prefixes={"wfc"},
        prune_stale=False,
    )

    assert written == 1
    assert removed == 0

    target = output_dir / "player-1.md"
    content = target.read_text(encoding="utf-8")
    assert "current_season: se-25-26" in content
    assert "current_season_is_tournament: no" in content
    assert "previous_season: wfc-2024" in content
    assert "current_points: 85" in content
    assert "previous_points: 6" in content
    assert "career_points: 91" in content
    assert "history_rows_csv: se-25-26|playoffs|Sweden|Storvreta IBK|5|6|7|13|5||se-25-26|regular-season|Sweden|Storvreta IBK|26|22|50|72|16||wfc-2024|tournament|IFF WFC|Sweden|3|3|3|6|0" in content


def test_generate_player_markdown_dedupes_same_season_rows_with_blank_source_ids(tmp_path: Path):
    partial_csv_path = tmp_path / "players_wfc.csv"
    partial_csv_path.write_text(
        "player_uid,source_system,source_player_id,player,team,league,season,phase,games,goals,assists,points,pim\n"
        "player-1,wfc,1691,Gabriel Kohonen,Sweden,IFF WFC,wfc-2024,regular-season,2,2,3,5,0\n"
        "player-1,wfc,1691,Gabriel Kohonen,Sweden,IFF WFC,wfc-2024,playoffs,1,1,0,1,0\n",
        encoding="utf-8",
    )

    full_csv_path = tmp_path / "players_full.csv"
    full_csv_path.write_text(
        "player_uid,source_system,source_player_id,player,team,league,season,phase,games,goals,assists,points,pim\n"
        "player-1,sweden,409141,Gabriel Kohonen,Storvreta IBK,Sweden,se-25-26,regular-season,26,22,50,72,16\n"
        "player-1,sweden,409141,Gabriel Kohonen,Storvreta IBK,Sweden,se-25-26,playoffs,5,6,7,13,5\n"
        "player-1,wfc,,Gabriel Kohonen,Sweden,IFF WFC,wfc-2024,regular-season,2,2,3,5,0\n"
        "player-1,wfc,,Gabriel Kohonen,Sweden,IFF WFC,wfc-2024,playoffs,1,1,0,1,0\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "content" / "players"
    written, removed = generate_player_markdown(
        csv_path=str(partial_csv_path),
        merge_csv_path=str(full_csv_path),
        output_dir=str(output_dir),
        default_category="players",
        season_prefixes={"wfc"},
        prune_stale=False,
    )

    assert written == 1
    assert removed == 0

    target = output_dir / "player-1.md"
    content = target.read_text(encoding="utf-8")
    assert content.count("wfc-2024|tournament|IFF WFC|Sweden|3|3|3|6|0") == 1


def test_generate_player_markdown_combines_current_tournament_season(tmp_path: Path):
    csv_path = tmp_path / "players_wfc.csv"
    csv_path.write_text(
        "player_uid,player,team,league,season,phase,games,goals,assists,points,pim\n"
        "player-1,Gabriel Kohonen,Sweden,IFF WFC,wfc-2024,regular-season,3,2,3,5,0\n"
        "player-1,Gabriel Kohonen,Sweden,IFF WFC,wfc-2024,playoffs,3,1,0,1,0\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "content" / "players"
    written, removed = generate_player_markdown(
        csv_path=str(csv_path),
        output_dir=str(output_dir),
        default_category="players",
        season_prefixes={"wfc"},
        prune_stale=False,
    )

    assert written == 1
    assert removed == 0

    content = (output_dir / "player-1.md").read_text(encoding="utf-8")
    assert "current_season: wfc-2024" in content
    assert "current_season_is_tournament: yes" in content
    assert "current_games: 6" in content
    assert "current_points: 6" in content
    assert "regular_games: 0" in content
    assert "playoff_games: 0" in content
    assert "history_rows_csv: wfc-2024|tournament|IFF WFC|Sweden|6|3|3|6|0" in content


def test_generate_player_markdown_merges_prefix_scoped_history_from_database(tmp_path: Path, monkeypatch) -> None:
    rows = [
        {
            "player_uid": "player-1",
            "source_system": "wfc",
            "source_player_id": "1691",
            "player": "Gabriel Kohonen",
            "team": "Sweden",
            "league": "IFF WFC",
            "season": "wfc-2024",
            "phase": "regular-season",
            "games": "3",
            "goals": "2",
            "assists": "3",
            "points": "5",
            "pim": "0",
        },
        {
            "player_uid": "player-1",
            "source_system": "wfc",
            "source_player_id": "1691",
            "player": "Gabriel Kohonen",
            "team": "Sweden",
            "league": "IFF WFC",
            "season": "wfc-2024",
            "phase": "playoffs",
            "games": "3",
            "goals": "1",
            "assists": "0",
            "points": "1",
            "pim": "0",
        },
        {
            "player_uid": "player-1",
            "source_system": "sweden",
            "source_player_id": "409141",
            "player": "Gabriel Kohonen",
            "team": "Storvreta IBK",
            "league": "Sweden",
            "season": "se-25-26",
            "phase": "regular-season",
            "games": "26",
            "goals": "22",
            "assists": "50",
            "points": "72",
            "pim": "16",
        },
        {
            "player_uid": "player-1",
            "source_system": "sweden",
            "source_player_id": "409141",
            "player": "Gabriel Kohonen",
            "team": "Storvreta IBK",
            "league": "Sweden",
            "season": "se-25-26",
            "phase": "playoffs",
            "games": "5",
            "goals": "6",
            "assists": "7",
            "points": "13",
            "pim": "5",
        },
    ]
    monkeypatch.setattr(generate_player_markdown_module, "_load_rows_from_postgres", lambda database_url: rows)

    output_dir = tmp_path / "content" / "players"
    written, removed = generate_player_markdown(
        csv_path=str(tmp_path / "unused.csv"),
        database_url="postgresql://example",
        output_dir=str(output_dir),
        default_category="players",
        season_prefixes={"wfc"},
        prune_stale=False,
    )

    assert written == 1
    assert removed == 0

    content = (output_dir / "player-1.md").read_text(encoding="utf-8")
    assert "current_season: se-25-26" in content
    assert "previous_season: wfc-2024" in content
    assert "career_points: 91" in content
    assert "history_rows_csv: se-25-26|playoffs|Sweden|Storvreta IBK|5|6|7|13|5||se-25-26|regular-season|Sweden|Storvreta IBK|26|22|50|72|16||wfc-2024|tournament|IFF WFC|Sweden|6|3|3|6|0" in content
