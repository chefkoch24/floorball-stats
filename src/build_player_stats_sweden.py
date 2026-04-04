import argparse
from pathlib import Path
import re

import pandas as pd

from src.utils import normalize_slug_fragment


FILE_PATTERN = re.compile(r"^data_(se-\d{2}-\d{2})_(regular_season|playoffs)\.csv$")


def _phase_from_file_token(token: str) -> str:
    return "regular-season" if token == "regular_season" else token


def _player_uid(player: str) -> str:
    return normalize_slug_fragment(f"{player}-sweden-ssl")


def _build_context_rows(path: Path, season: str, phase: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    goals_df = df[df["event_type"] == "goal"].copy()
    goals_df["scorer_name"] = goals_df["scorer_name"].fillna("").astype(str).str.strip()
    goals_df["assist_name"] = goals_df["assist_name"].fillna("").astype(str).str.strip()
    goals_df = goals_df[goals_df["scorer_name"] != ""]

    penalties_df = df[df["event_type"] == "penalty"].copy()
    penalties_df["penalty_player_name"] = penalties_df["penalty_player_name"].fillna("").astype(str).str.strip()
    penalties_df = penalties_df[penalties_df["penalty_player_name"] != ""]

    goals = goals_df.groupby(["scorer_name", "event_team"]).size().reset_index(name="goals")
    goals = goals.rename(columns={"scorer_name": "player", "event_team": "team"})

    assists_raw = goals_df[goals_df["assist_name"] != ""][["assist_name", "event_team"]].copy()
    assists = assists_raw.groupby(["assist_name", "event_team"]).size().reset_index(name="assists")
    assists = assists.rename(columns={"assist_name": "player", "event_team": "team"})

    penalties = penalties_df.groupby(["penalty_player_name", "event_team"]).size().reset_index(name="penalties")
    penalties = penalties.rename(columns={"penalty_player_name": "player", "event_team": "team"})

    stats = goals.merge(assists, on=["player", "team"], how="outer")
    stats = stats.merge(penalties, on=["player", "team"], how="outer").fillna(0)

    gp_goals = goals_df[["game_id", "event_team", "scorer_name"]].rename(
        columns={"event_team": "team", "scorer_name": "player"}
    )
    gp_assists = goals_df[goals_df["assist_name"] != ""][["game_id", "event_team", "assist_name"]].rename(
        columns={"event_team": "team", "assist_name": "player"}
    )
    gp_pen = penalties_df[["game_id", "event_team", "penalty_player_name"]].rename(
        columns={"event_team": "team", "penalty_player_name": "player"}
    )
    gp = pd.concat([gp_goals, gp_assists, gp_pen], ignore_index=True).drop_duplicates()
    gp = gp.groupby(["player", "team"]).size().reset_index(name="games")

    stats = stats.merge(gp, on=["player", "team"], how="left")
    for col in ["games", "goals", "assists", "penalties"]:
        stats[col] = stats[col].fillna(0).astype(int)
    stats["points"] = stats["goals"] + stats["assists"]
    stats["pim"] = stats["penalties"] * 2

    stats = stats.sort_values(["points", "goals", "assists"], ascending=[False, False, False]).reset_index(drop=True)
    stats["rank"] = stats.index + 1
    stats["player_uid"] = stats["player"].apply(_player_uid)
    stats["league"] = "Sweden SSL"
    stats["season"] = season
    stats["phase"] = phase
    stats["category"] = f"{season}-{phase}, players"
    stats["title"] = stats["player"]
    stats["slug"] = stats.apply(
        lambda row: normalize_slug_fragment(f"{row['player']}-{row['season']}-{row['phase']}"),
        axis=1,
    )

    return stats[
        [
            "player_uid",
            "player",
            "title",
            "slug",
            "category",
            "team",
            "league",
            "season",
            "phase",
            "rank",
            "games",
            "goals",
            "assists",
            "points",
            "pim",
            "penalties",
        ]
    ]


def build_sweden_player_stats(data_dir: str, output_csv: str) -> int:
    directory = Path(data_dir)
    all_rows: list[pd.DataFrame] = []

    for candidate in sorted(directory.glob("data_se-*.csv")):
        match = FILE_PATTERN.match(candidate.name)
        if not match:
            continue
        season, phase_token = match.groups()
        phase = _phase_from_file_token(phase_token)
        context_rows = _build_context_rows(candidate, season=season, phase=phase)
        all_rows.append(context_rows)

    if not all_rows:
        raise RuntimeError(f"No Sweden files found in {directory} matching pattern {FILE_PATTERN.pattern}")

    result = pd.concat(all_rows, ignore_index=True)
    result.to_csv(output_csv, index=False)
    return len(result)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Sweden player stats CSV from season event CSV files.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-csv", default="data/player_stats.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_sweden_player_stats(data_dir=args.data_dir, output_csv=args.output_csv)
    print(f"sweden-player-stats: wrote {rows} rows to {args.output_csv}")


if __name__ == "__main__":
    main()
