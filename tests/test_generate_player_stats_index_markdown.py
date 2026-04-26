from pathlib import Path

import src.generate_player_stats_index_markdown as generate_player_stats_index_markdown_module
from src.generate_player_stats_index_markdown import generate_player_stats_index_markdown


def test_generate_player_stats_index_markdown_combines_wfc_tournament_rows(tmp_path: Path, monkeypatch) -> None:
    rows = [
        {"player_uid": "player-a", "player": "Player A", "team": "Team A", "league": "IFF WFC", "season": "wfc-2024", "phase": "regular-season", "rank": "1", "games": "3", "goals": "2", "assists": "4", "points": "6", "pim": "2"},
        {"player_uid": "player-b", "player": "Player B", "team": "Team B", "league": "IFF WFC", "season": "wfc-2024", "phase": "regular-season", "rank": "2", "games": "3", "goals": "3", "assists": "1", "points": "4", "pim": "0"},
        {"player_uid": "player-a", "player": "Player A", "team": "Team A", "league": "IFF WFC", "season": "wfc-2024", "phase": "playoffs", "rank": "5", "games": "4", "goals": "2", "assists": "1", "points": "3", "pim": "4"},
        {"player_uid": "player-c", "player": "Player C", "team": "Team C", "league": "IFF WFC", "season": "wfc-2024", "phase": "playoffs", "rank": "1", "games": "4", "goals": "4", "assists": "2", "points": "6", "pim": "2"},
    ]
    monkeypatch.setattr(generate_player_stats_index_markdown_module, "_load_rows_from_postgres", lambda database_url: rows)

    output_dir = tmp_path / "content" / "player-stats"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "wfc-2024-regular-season-players.md").write_text("stale", encoding="utf-8")
    (output_dir / "wfc-2024-playoffs-players.md").write_text("stale", encoding="utf-8")
    (output_dir / "se-25-26-regular-season-players.md").write_text("keep", encoding="utf-8")

    written, removed = generate_player_stats_index_markdown(
        database_url="postgresql://test",
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
