import argparse
import re
from pathlib import Path

import pandas as pd
import psycopg

from src.build_player_stats import (
    LEAGUE_INFO,
    _canonical_player_uid,
    _finalize_rows,
    _merge_finalized_rows,
    _normalize_player_name_for_identity,
    _rows_from_czech_rosters,
    _rows_from_finland_rosters,
    _rows_from_germany_lineups,
    _rows_from_latvia_rosters,
    _rows_from_slovakia_rosters,
    _rows_from_swiss_rosters,
    _rows_from_sweden_lineups,
    _rows_from_wfc_lineups,
)


def _season_prefix(season: str) -> str:
    match = re.match(r"^([a-z]{2,3})-(?:\d{2}-\d{2}|\d{4})$", str(season or "").strip().lower())
    if match:
        return match.group(1)
    return ""


def _load_events(database_url: str) -> pd.DataFrame:
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                season,
                phase,
                event_type,
                event_team,
                game_id,
                home_team_name,
                away_team_name,
                scorer_name,
                assist_name,
                penalty_player_name
            FROM events
            """
        )
        columns = [desc.name for desc in cur.description]
        rows = cur.fetchall()
    if not rows:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(rows, columns=columns)
    for column in [
        "season",
        "phase",
        "event_type",
        "event_team",
        "home_team_name",
        "away_team_name",
        "scorer_name",
        "assist_name",
        "penalty_player_name",
    ]:
        frame[column] = frame[column].fillna("").astype(str)
    return frame


def _rows_from_event_frame(df: pd.DataFrame, season: str, phase: str, league: str, source_system: str) -> pd.DataFrame:
    if df.empty:
        return _finalize_rows(pd.DataFrame(), season=season, phase=phase, league=league, source_system=source_system)

    goals_df = df[df["event_type"] == "goal"].copy()
    goals_df["scorer_name"] = goals_df["scorer_name"].map(_normalize_player_name_for_identity)
    goals_df["assist_name"] = goals_df["assist_name"].map(_normalize_player_name_for_identity)
    goals_df = goals_df[goals_df["scorer_name"] != ""]

    penalties_df = df[df["event_type"] == "penalty"].copy()
    penalties_df["penalty_player_name"] = penalties_df["penalty_player_name"].map(_normalize_player_name_for_identity)
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


def _played_matches_from_events(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"game_id", "home_team_name", "away_team_name", "event_type"}
    if df.empty or not required_columns.issubset(df.columns):
        return pd.DataFrame(columns=["game_id", "home_team_name", "away_team_name"])

    played = df[df["event_type"].isin(["goal", "penalty", "result"])].copy()
    if played.empty:
        return pd.DataFrame(columns=["game_id", "home_team_name", "away_team_name"])

    played["game_id"] = pd.to_numeric(played["game_id"], errors="coerce")
    played = played.dropna(subset=["game_id"])
    played = played[played["home_team_name"].astype(str).str.strip() != ""]
    played = played[played["away_team_name"].astype(str).str.strip() != ""]

    matches = played.sort_values(["game_id"]).drop_duplicates(subset=["game_id"])[["game_id", "home_team_name", "away_team_name"]].copy()
    matches["game_id"] = matches["game_id"].astype(int)
    return matches


def _lineup_rows_for_prefix(prefix: str, matches: pd.DataFrame, season: str, phase: str) -> pd.DataFrame:
    if matches.empty:
        return pd.DataFrame()
    if prefix == "se":
        match_ids = matches["game_id"].dropna().astype(int).drop_duplicates().tolist()
        return _rows_from_sweden_lineups(match_ids, season=season, phase=phase)
    if prefix == "":
        match_ids = matches["game_id"].dropna().astype(int).drop_duplicates().tolist()
        return _rows_from_germany_lineups(match_ids=match_ids, season=season, phase=phase)
    if prefix == "cz":
        return _rows_from_czech_rosters(
            matches=matches,
            season=season,
            phase=phase,
            league=LEAGUE_INFO[prefix]["league"],
            source_system=LEAGUE_INFO[prefix]["source_system"],
        )
    if prefix == "ch":
        return _rows_from_swiss_rosters(matches=matches, season=season, phase=phase)
    if prefix == "fi":
        return _rows_from_finland_rosters(matches=matches, season=season, phase=phase)
    if prefix == "sk":
        return _rows_from_slovakia_rosters(matches=matches, season=season, phase=phase)
    if prefix == "lv":
        return _rows_from_latvia_rosters(matches=matches, season=season, phase=phase)
    if prefix == "wfc":
        return _rows_from_wfc_lineups(matches=matches, season=season, phase=phase)
    return pd.DataFrame()


def _replace_player_stats_table(database_url: str, frame: pd.DataFrame) -> int:
    with psycopg.connect(database_url, autocommit=False) as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS player_stats")
        cur.execute(
            """
            CREATE TABLE player_stats (
                player_uid TEXT,
                source_system TEXT,
                source_player_id TEXT,
                source_person_id TEXT,
                player TEXT,
                title TEXT,
                slug TEXT,
                category TEXT,
                team TEXT,
                league TEXT,
                season TEXT,
                phase TEXT,
                rank INTEGER,
                games INTEGER,
                goals INTEGER,
                assists INTEGER,
                points INTEGER,
                pim INTEGER,
                penalties INTEGER
            )
            """
        )
        if frame.empty:
            conn.commit()
            return 0

        ordered_columns = [
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
        rows = [tuple(row) for row in frame[ordered_columns].itertuples(index=False, name=None)]
        cur.executemany(
            """
            INSERT INTO player_stats (
                player_uid, source_system, source_player_id, source_person_id, player, title, slug, category, team,
                league, season, phase, rank, games, goals, assists, points, pim, penalties
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            rows,
        )
        conn.commit()
        return len(rows)


def build_player_stats_from_postgres(*, database_url: str, output_csv: str = "") -> int:
    events = _load_events(database_url)
    all_rows: list[pd.DataFrame] = []

    if not events.empty:
        grouped = events.groupby(["season", "phase"], dropna=False)
        for (season, phase), subset in grouped:
            season_key = str(season or "").strip()
            phase_key = str(phase or "").strip()
            if not season_key or not phase_key:
                continue
            prefix = _season_prefix(season_key)
            info = LEAGUE_INFO.get(prefix)
            if not info:
                continue
            event_rows = _rows_from_event_frame(
                subset,
                season=season_key,
                phase=phase_key,
                league=info["league"],
                source_system=info["source_system"],
            )
            try:
                matches = _played_matches_from_events(subset)
                lineup_rows = _lineup_rows_for_prefix(prefix, matches, season=season_key, phase=phase_key)
            except Exception:
                lineup_rows = pd.DataFrame()
            all_rows.append(
                _merge_finalized_rows(
                    [event_rows, lineup_rows],
                    season=season_key,
                    phase=phase_key,
                    league=info["league"],
                    source_system=info["source_system"],
                )
            )

    if all_rows:
        result = pd.concat(all_rows, ignore_index=True)
        result = result.sort_values(
            ["season", "phase", "league", "points", "goals", "assists", "player"],
            ascending=[True, True, True, False, False, False, True],
        ).reset_index(drop=True)
    else:
        result = pd.DataFrame(
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

    rows = _replace_player_stats_table(database_url, result)
    if output_csv:
        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_path, index=False)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build player_stats directly from Postgres events table.")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--output-csv", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_player_stats_from_postgres(database_url=args.database_url, output_csv=args.output_csv)
    target = args.output_csv or "database only"
    print(f"player-stats-db: wrote {rows} rows to player_stats ({target})")


if __name__ == "__main__":
    main()
