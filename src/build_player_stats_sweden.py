import argparse
from pathlib import Path
import re

import pandas as pd
import requests

from src.utils import generate_player_uid, normalize_slug_fragment


FILE_PATTERN = re.compile(r"^data_(se-\d{2}-\d{2})_(regular_season|playoffs)\.csv$")
STARTKIT_URL = "https://api.innebandy.se/StatsAppApi/api/startkit"
DEFAULT_API_ROOT = "https://api.innebandy.se/v2/api/"


def _phase_from_file_token(token: str) -> str:
    return "regular-season" if token == "regular_season" else token


def _player_uid(player: str, source_player_id: int | None = None) -> str:
    if source_player_id:
        return generate_player_uid("sweden", "player", int(source_player_id))
    return normalize_slug_fragment(f"{player}-sweden-ssl")


def _get_api_root_and_headers() -> tuple[str, dict[str, str]]:
    payload = requests.get(STARTKIT_URL, timeout=30).json()
    api_root = payload.get("apiRoot") or DEFAULT_API_ROOT
    token = payload.get("accessToken")
    if not token:
        raise RuntimeError("Startkit response did not include accessToken")
    return api_root, {"Authorization": f"Bearer {token}"}


def _fetch_player_statistics_for_competition(competition_id: int) -> list[dict]:
    api_root, headers = _get_api_root_and_headers()
    response = requests.get(f"{api_root}competitions/{competition_id}/playerstatistics", headers=headers, timeout=30)
    response.raise_for_status()
    payload = response.json()
    return payload.get("PlayerStatisticsRows") or []


def _fetch_match_lineups(match_id: int, api_root: str, headers: dict[str, str]) -> dict:
    response = requests.get(f"{api_root}matches/{match_id}/lineups", headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def _rows_from_match_lineups(
    match_ids: list[int],
    season: str,
    phase: str,
    league: str = "Sweden SSL",
) -> pd.DataFrame:
    api_root, headers = _get_api_root_and_headers()
    records: list[dict] = []
    for match_id in sorted(set(match_ids)):
        lineups = _fetch_match_lineups(match_id, api_root=api_root, headers=headers)
        team_name_by_id = {
            int(lineups.get("HomeTeamID") or 0): str(lineups.get("HomeTeam") or "").strip(),
            int(lineups.get("AwayTeamID") or 0): str(lineups.get("AwayTeam") or "").strip(),
        }
        for side in ["HomeTeamPlayers", "AwayTeamPlayers"]:
            for row in lineups.get(side, []) or []:
                player = str(row.get("Name") or "").strip()
                if not player:
                    continue
                team_id = int(row.get("TeamID") or 0)
                team_name = team_name_by_id.get(team_id) or str(row.get("LicensedAssociationName") or "").strip()
                goals = int(row.get("Goals") or 0)
                assists = int(row.get("Assists") or 0)
                points = int(row.get("Points") or goals + assists)
                pim = int(row.get("PenaltyMinutes") or 0)
                records.append(
                    {
                        "player_uid": _player_uid(player, row.get("PlayerID")),
                        "source_system": "sweden",
                        "source_player_id": int(row.get("PlayerID") or 0),
                        "player": player,
                        "title": player,
                        "slug": normalize_slug_fragment(f"{player}-{season}-{phase}"),
                        "category": f"{season}-{phase}, players",
                        "team": team_name,
                        "league": league,
                        "season": season,
                        "phase": phase,
                        "games": int(row.get("Matches") or 0) or 1,
                        "goals": goals,
                        "assists": assists,
                        "points": points,
                        "pim": pim,
                        "penalties": pim // 2,
                    }
                )

    stats = pd.DataFrame.from_records(records)
    if stats.empty:
        return stats

    stats = (
        stats.groupby(
            ["player_uid", "source_system", "source_player_id", "player", "title", "slug", "category", "team", "league", "season", "phase"],
            as_index=False,
        )[
            ["games", "goals", "assists", "points", "pim", "penalties"]
        ]
        .sum()
    )
    stats = stats.sort_values(["points", "goals", "assists"], ascending=[False, False, False]).reset_index(drop=True)
    stats["rank"] = stats.index + 1
    return stats[
        [
            "player_uid",
            "source_system",
            "source_player_id",
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
    stats["source_system"] = ""
    stats["source_player_id"] = 0
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
            "source_system",
            "source_player_id",
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
        try:
            match_ids = (
                pd.read_csv(candidate, usecols=["game_id"])["game_id"]
                .dropna()
                .astype(int)
                .drop_duplicates()
                .tolist()
            )
            context_rows = _rows_from_match_lineups(match_ids, season=season, phase=phase)
        except Exception:
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
