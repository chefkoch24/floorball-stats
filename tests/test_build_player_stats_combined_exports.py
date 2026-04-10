from pathlib import Path

import pandas as pd

from src.build_player_stats import build_player_stats


def test_build_player_stats_prefers_existing_per_league_exports(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    (data_dir / "player_stats_de.csv").write_text(
        "player_uid,player,team,league,season,phase,rank,games,goals,assists,points,pim,penalties\n"
        "de-1,Max Muster,Club DE,Germany,25-26,regular-season,1,10,8,7,15,4,2\n",
        encoding="utf-8",
    )
    (data_dir / "player_stats_se.csv").write_text(
        "player_uid,player,team,league,season,phase,rank,games,goals,assists,points,pim,penalties\n"
        "se-1,Sven Svensson,Club SE,Sweden,se-25-26,regular-season,1,11,9,6,15,2,1\n",
        encoding="utf-8",
    )

    output_csv = data_dir / "player_stats.csv"
    written = build_player_stats(str(data_dir), str(output_csv))

    assert written == 2
    result = pd.read_csv(output_csv)
    assert set(result["league"]) == {"Germany", "Sweden"}
    assert set(result["phase"]) == {"regular-season"}
