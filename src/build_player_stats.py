import argparse
from pathlib import Path
import re

import pandas as pd
import requests

from src.utils import generate_player_uid, normalize_slug_fragment


FILE_PATTERN = re.compile(r"^data_((?P<prefix>[a-z]{2})-)?(?P<years>\d{2}-\d{2})_(?P<phase>regular_season|playoffs)\.csv$")
STARTKIT_URL = "https://api.innebandy.se/StatsAppApi/api/startkit"
DEFAULT_API_ROOT = "https://api.innebandy.se/v2/api/"
LEAGUE_INFO = {
    "": {"source_system": "germany", "league": "Germany"},
    "ch": {"source_system": "switzerland", "league": "Switzerland"},
    "cz": {"source_system": "czech-republic", "league": "Czech Republic"},
    "fi": {"source_system": "finland", "league": "Finland"},
    "lv": {"source_system": "latvia", "league": "Latvia"},
    "se": {"source_system": "sweden", "league": "Sweden"},
    "sk": {"source_system": "slovakia", "league": "Slovakia"},
}


def _phase_from_file_token(token: str) -> str:
    return "regular-season" if token == "regular_season" else token


def _season_token(prefix: str, years: str) -> str:
    return f"{prefix}-{years}" if prefix else years


def _canonical_player_uid(player: str) -> str:
    cleaned_player = str(player or "").strip()
    normalized_player = normalize_slug_fragment(cleaned_player)
    return generate_player_uid("player", normalized_player or cleaned_player.lower())


def _row_slug(player: str, season: str, phase: str) -> str:
    return normalize_slug_fragment(f"{player}-{season}-{phase}")


def _aggregate_team_names(values: pd.Series) -> str:
    seen = []
    for value in values.astype(str):
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.append(cleaned)
    return " / ".join(seen)


def _aggregate_source_ids(values: pd.Series) -> str:
    seen = []
    for value in values.astype(str):
        cleaned = value.strip()
        if not cleaned or cleaned == "0" or cleaned in seen:
            continue
        seen.append(cleaned)
    return seen[0] if len(seen) == 1 else ",".join(seen)


def _finalize_rows(stats: pd.DataFrame, season: str, phase: str, league: str, source_system: str) -> pd.DataFrame:
    if stats.empty:
        return pd.DataFrame(
            columns=[
                "player_uid",
                "source_system",
                "source_player_id",
                "source_person_id",
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
        )

    grouped = (
        stats.groupby(["player_uid", "player"], as_index=False)
        .agg(
            {
                "team": _aggregate_team_names,
                "games": "sum",
                "goals": "sum",
                "assists": "sum",
                "points": "sum",
                "pim": "sum",
                "penalties": "sum",
                "source_player_id": _aggregate_source_ids,
                "source_person_id": _aggregate_source_ids,
            }
        )
        .sort_values(["points", "goals", "assists", "player"], ascending=[False, False, False, True])
        .reset_index(drop=True)
    )
    grouped["source_system"] = source_system
    grouped["title"] = grouped["player"]
    grouped["slug"] = grouped["player"].apply(lambda player: _row_slug(player, season, phase))
    grouped["category"] = f"{season}-{phase}, players"
    grouped["league"] = league
    grouped["season"] = season
    grouped["phase"] = phase
    grouped["rank"] = grouped.index + 1
    return grouped[
        [
            "player_uid",
            "source_system",
            "source_player_id",
            "source_person_id",
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


def _rows_from_event_csv(path: Path, season: str, phase: str, league: str, source_system: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required_columns = {"event_type", "event_team", "game_id", "scorer_name", "assist_name", "penalty_player_name"}
    if not required_columns.issubset(df.columns):
        return _finalize_rows(pd.DataFrame(), season=season, phase=phase, league=league, source_system=source_system)

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
    stats["player"] = stats["player"].fillna("").astype(str).str.strip()
    stats["team"] = stats["team"].fillna("").astype(str).str.strip()
    stats = stats[stats["player"] != ""].copy()
    for col in ["games", "goals", "assists", "penalties"]:
        stats[col] = stats[col].fillna(0).astype(int)
    stats["points"] = stats["goals"] + stats["assists"]
    stats["pim"] = stats["penalties"] * 2
    stats["player_uid"] = stats["player"].apply(_canonical_player_uid)
    stats["source_player_id"] = ""
    stats["source_person_id"] = ""

    return _finalize_rows(stats, season=season, phase=phase, league=league, source_system=source_system)


def _get_api_root_and_headers() -> tuple[str, dict[str, str]]:
    payload = requests.get(STARTKIT_URL, timeout=30).json()
    api_root = payload.get("apiRoot") or DEFAULT_API_ROOT
    token = payload.get("accessToken")
    if not token:
        raise RuntimeError("Startkit response did not include accessToken")
    return api_root, {"Authorization": f"Bearer {token}"}


def _fetch_match_lineups(match_id: int, api_root: str, headers: dict[str, str]) -> dict:
    response = requests.get(f"{api_root}matches/{match_id}/lineups", headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def _rows_from_sweden_lineups(match_ids: list[int], season: str, phase: str) -> pd.DataFrame:
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
                        "player_uid": _canonical_player_uid(player),
                        "source_player_id": str(int(row.get("PlayerID") or 0) or ""),
                        "source_person_id": str(int(row.get("PersonID") or 0) or ""),
                        "player": player,
                        "team": team_name,
                        "games": int(row.get("Matches") or 0) or 1,
                        "goals": goals,
                        "assists": assists,
                        "points": points,
                        "pim": pim,
                        "penalties": pim // 2,
                    }
                )

    stats = pd.DataFrame.from_records(records)
    return _finalize_rows(stats, season=season, phase=phase, league="Sweden", source_system="sweden")


def build_player_stats(data_dir: str, output_csv: str) -> int:
    directory = Path(data_dir)
    all_rows: list[pd.DataFrame] = []

    for candidate in sorted(directory.glob("data_*.csv")):
        match = FILE_PATTERN.match(candidate.name)
        if not match:
            continue
        prefix = (match.group("prefix") or "").lower()
        years = match.group("years")
        phase_token = match.group("phase")
        info = LEAGUE_INFO.get(prefix)
        if not info:
            continue
        season = _season_token(prefix, years)
        phase = _phase_from_file_token(phase_token)

        if prefix == "se":
            try:
                match_ids = (
                    pd.read_csv(candidate, usecols=["game_id"])["game_id"]
                    .dropna()
                    .astype(int)
                    .drop_duplicates()
                    .tolist()
                )
                context_rows = _rows_from_sweden_lineups(match_ids, season=season, phase=phase)
            except Exception:
                context_rows = _rows_from_event_csv(
                    candidate,
                    season=season,
                    phase=phase,
                    league=info["league"],
                    source_system=info["source_system"],
                )
        else:
            context_rows = _rows_from_event_csv(
                candidate,
                season=season,
                phase=phase,
                league=info["league"],
                source_system=info["source_system"],
            )

        all_rows.append(context_rows)

    if not all_rows:
        raise RuntimeError(f"No league files found in {directory} matching pattern {FILE_PATTERN.pattern}")

    result = pd.concat(all_rows, ignore_index=True)
    result.to_csv(output_csv, index=False)
    return len(result)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build player stats CSV from all available season event files.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-csv", default="data/player_stats.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_player_stats(data_dir=args.data_dir, output_csv=args.output_csv)
    print(f"player-stats: wrote {rows} rows to {args.output_csv}")


if __name__ == "__main__":
    main()
