from pathlib import Path

from src.generate_player_stats_index_markdown import generate_player_stats_index_markdown


def test_generate_player_stats_index_markdown_combines_wfc_tournament_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "player_stats_wfc.csv"
    csv_path.write_text(
        "\n".join(
            [
                "player_uid,player,team,league,season,phase,rank,games,goals,assists,points,pim",
                "player-a,Player A,Team A,IFF WFC,wfc-2024,regular-season,1,3,2,4,6,2",
                "player-b,Player B,Team B,IFF WFC,wfc-2024,regular-season,2,3,3,1,4,0",
                "player-a,Player A,Team A,IFF WFC,wfc-2024,playoffs,5,4,2,1,3,4",
                "player-c,Player C,Team C,IFF WFC,wfc-2024,playoffs,1,4,4,2,6,2",
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "content" / "player-stats"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "wfc-2024-regular-season-players.md").write_text("stale", encoding="utf-8")
    (output_dir / "wfc-2024-playoffs-players.md").write_text("stale", encoding="utf-8")
    (output_dir / "se-25-26-regular-season-players.md").write_text("keep", encoding="utf-8")

    written, removed = generate_player_stats_index_markdown(
        csv_path=str(csv_path),
        output_dir=str(output_dir),
        season_prefixes={"wfc"},
        prune_stale=False,
    )

    assert written == 1
    assert removed == 2

    target = output_dir / "wfc-2024-players.md"
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "Category: wfc-2024-players" in content
    assert "season_phase_key: wfc-2024-tournament" in content
    assert "phase: tournament" in content
    assert "player_count: 3" in content
    assert "1|player-a|Player A|Team A|7|4|5|9|6" in content
    assert "2|player-c|Player C|Team C|4|4|2|6|2" in content
    assert "3|player-b|Player B|Team B|3|3|1|4|0" in content

    assert not (output_dir / "wfc-2024-regular-season-players.md").exists()
    assert not (output_dir / "wfc-2024-playoffs-players.md").exists()
    assert (output_dir / "se-25-26-regular-season-players.md").exists()
