import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins"))

import insights  # noqa: E402
from src import power_rankings as pr  # noqa: E402


def _team(name, rank):
    return SimpleNamespace(team=name, title=name, rank=str(rank), url=f"{name}.html", category=SimpleNamespace(slug="se-26-27-regular-season"))


def _game(game_id, home, away, home_goals=0, away_goals=0, played=True, decision=pr.REGULATION):
    article = SimpleNamespace(url=f"g{game_id}.html", date=date(2026, 10, game_id), category=SimpleNamespace(slug="se-26-27-regular-season"))
    points = None
    if played:
        points = (3, 0) if home_goals > away_goals else (0, 3)
        if decision != pr.REGULATION:
            points = (2, 1) if home_goals > away_goals else (1, 2)
    result = pr.GameResult(str(game_id), "26-27", "regular-season", article.date, "18:00", home, away, played, home_goals, away_goals, decision, *(points or (None, None)))
    return article, result


def test_matrix_reads_from_the_row_team_and_splits_top_from_rest():
    teams = [_team(name, rank) for rank, name in enumerate(["A", "B", "C", "D", "E"], start=1)]
    entries = [
        _game(1, "A", "B", 5, 3),
        _game(2, "C", "A", 4, 3, decision=pr.OVERTIME),
        _game(3, "E", "A", played=False),
    ]
    run = pr.run_elo([result for _, result in entries])
    context = {"se-26-27-regular-season": {}}
    insights._head_to_head("se-26-27-regular-season", entries, run, teams, context)
    matrix = context["se-26-27-regular-season"]["matrix"]
    assert matrix["teams"] == ["A", "B", "C", "D", "E"]
    row_a = matrix["rows"][0]
    cells = {cell["opponent"]: cell for cell in row_a["cells"] if cell}
    assert row_a["cells"][0] is None
    assert cells["B"]["games"][0]["score"] == "5:3" and cells["B"]["games"][0]["tone"] == "w"
    assert cells["C"]["games"][0]["letter"] == "OTL" and cells["C"]["ppg"] == "1.0"
    assert cells["E"]["games"][0]["chance"].endswith("%")
    # A beat B (3) and lost to C after overtime (1): 2.00 per game against the top 4, nothing played against E.
    assert row_a["vs_top"] == "2.00" and row_a["vs_rest"] == "–"
    row_b = matrix["rows"][1]
    assert {cell["opponent"]: cell for cell in row_b["cells"] if cell}["A"]["games"][0]["score"] == "3:5"
