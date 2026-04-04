from pathlib import Path

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
