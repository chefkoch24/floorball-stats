import argparse
import re
from pathlib import Path
from collections import defaultdict

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
from src.utils import normalize_slug_fragment


def _season_prefix(season: str) -> str:
    match = re.match(r"^([a-z]{2,3})-(?:\d{2}-\d{2}|\d{4})$", str(season or "").strip().lower())
    if match:
        return match.group(1)
    return ""


def _name_initial_surname_key(name: str) -> tuple[str, str] | None:
    parts = [token for token in str(name or "").strip().split() if token]
    if len(parts) < 2:
        return None
    first = normalize_slug_fragment(parts[0]).replace("-", "")
    surname = normalize_slug_fragment(parts[-1]).replace("-", "")
    if not first or not surname:
        return None
    return (first[:1], surname)


def _is_abbreviated_name(name: str) -> bool:
    parts = [token for token in str(name or "").strip().split() if token]
    if len(parts) < 2:
        return False
    return bool(re.match(r"^[A-Za-z]\.?$", parts[0]))


def _refresh_player_identity_aliases(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS player_identity_aliases (
                alias_uid TEXT PRIMARY KEY,
                canonical_uid TEXT NOT NULL,
                reason TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            SELECT player_uid, player, source_system, goals, assists, points, penalties
            FROM player_stats
            WHERE source_system = 'switzerland'
            """
        )
        rows = cur.fetchall()

    if not rows:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM player_identity_aliases WHERE reason = 'auto_swiss_zero_stat_merge'")
        return 0

    by_key: dict[tuple[str, str], dict[str, dict[str, object]]] = defaultdict(dict)
    for player_uid, player, source_system, goals, assists, points, penalties in rows:
        uid = str(player_uid or "").strip()
        player_name = str(player or "").strip()
        if not uid or not player_name:
            continue
        key = _name_initial_surname_key(player_name)
        if not key:
            continue
        stat_total = int(goals or 0) + int(assists or 0) + int(points or 0) + int(penalties or 0)
        uid_bucket = by_key[key].setdefault(
            uid,
            {
                "uid": uid,
                "player": player_name,
                "stats": 0,
                "abbrev": _is_abbreviated_name(player_name),
            },
        )
        uid_bucket["stats"] = int(uid_bucket["stats"]) + stat_total
        if not uid_bucket["player"] and player_name:
            uid_bucket["player"] = player_name

    alias_pairs: list[tuple[str, str]] = []
    for _, uid_map in by_key.items():
        candidates = list(uid_map.values())
        if len(candidates) < 2:
            continue
        scored = [entry for entry in candidates if int(entry["stats"]) > 0]
        if len(scored) != 1:
            continue
        canonical_uid = str(scored[0]["uid"])
        for candidate in candidates:
            alias_uid = str(candidate["uid"])
            if alias_uid == canonical_uid:
                continue
            if int(candidate["stats"]) > 0:
                continue
            alias_pairs.append((alias_uid, canonical_uid))

    with conn.cursor() as cur:
        cur.execute("DELETE FROM player_identity_aliases WHERE reason = 'auto_swiss_zero_stat_merge'")
        if alias_pairs:
            cur.executemany(
                """
                INSERT INTO player_identity_aliases (alias_uid, canonical_uid, reason, updated_at)
                VALUES (%s, %s, 'auto_swiss_zero_stat_merge', NOW())
                ON CONFLICT (alias_uid) DO UPDATE
                SET canonical_uid = EXCLUDED.canonical_uid,
                    reason = EXCLUDED.reason,
                    updated_at = NOW()
                """,
                alias_pairs,
            )
    return len(alias_pairs)


def _refresh_cross_league_abbreviated_aliases(conn: psycopg.Connection) -> int:
    """Alias abbreviated player names (e.g. 'A. Sjögren') to the single unambiguous
    full-name UID (e.g. 'Albin Sjögren') found across any league/source.

    Only creates an alias when exactly one full-name UID shares the same
    initial+surname key as the abbreviated UID — any ambiguity is skipped.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT player_uid, player, goals, assists, points, penalties
            FROM player_stats
            """
        )
        rows = cur.fetchall()

    if not rows:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM player_identity_aliases WHERE reason = 'auto_cross_league_abbrev_merge'")
        return 0

    by_key: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for player_uid, player, goals, assists, points, penalties in rows:
        uid = str(player_uid or "").strip()
        player_name = str(player or "").strip()
        if not uid or not player_name:
            continue
        key = _name_initial_surname_key(player_name)
        if not key:
            continue
        stat_total = int(goals or 0) + int(assists or 0) + int(points or 0) + int(penalties or 0)
        bucket = by_key[key].setdefault(
            uid,
            {
                "uid": uid,
                "player": player_name,
                "stats": 0,
                "abbrev": _is_abbreviated_name(player_name),
            },
        )
        bucket["stats"] = int(bucket["stats"]) + stat_total
        # Prefer non-abbreviated name variant when updating the same UID bucket
        if bucket["abbrev"] and not _is_abbreviated_name(player_name):
            bucket["player"] = player_name
            bucket["abbrev"] = False

    alias_pairs: list[tuple[str, str]] = []
    for key, uid_map in by_key.items():
        if len(uid_map) < 2:
            continue
        full_uids = [entry for entry in uid_map.values() if not entry["abbrev"] and int(entry["stats"]) > 0]
        abbrev_uids = [entry for entry in uid_map.values() if entry["abbrev"]]
        if not abbrev_uids or len(full_uids) != 1:
            # Skip if no abbreviated UIDs, or ambiguous (multiple full-name UIDs)
            continue
        canonical = full_uids[0]["uid"]
        for entry in abbrev_uids:
            if entry["uid"] != canonical:
                alias_pairs.append((entry["uid"], canonical))

    with conn.cursor() as cur:
        cur.execute("DELETE FROM player_identity_aliases WHERE reason = 'auto_cross_league_abbrev_merge'")
        if alias_pairs:
            cur.executemany(
                """
                INSERT INTO player_identity_aliases (alias_uid, canonical_uid, reason, updated_at)
                VALUES (%s, %s, 'auto_cross_league_abbrev_merge', NOW())
                ON CONFLICT (alias_uid) DO UPDATE
                SET canonical_uid = EXCLUDED.canonical_uid,
                    reason = EXCLUDED.reason,
                    updated_at = NOW()
                """,
                alias_pairs,
            )
    return len(alias_pairs)


def _load_all_game_rosters(database_url: str) -> pd.DataFrame:
    """Load all rows from game_rosters into memory (short-lived connection)."""
    try:
        with psycopg.connect(database_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT game_id, season, phase, team_name, player_name, source_player_id, source_person_id FROM game_rosters"
            )
            rows = cur.fetchall()
    except Exception:
        return pd.DataFrame()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(
        rows, columns=["game_id", "season", "phase", "team", "player", "source_player_id", "source_person_id"]
    )


def _wfc_roster_rows_from_frame(rosters: pd.DataFrame, season: str, phase: str) -> pd.DataFrame:
    subset = rosters[(rosters["season"] == season) & (rosters["phase"] == phase)].copy()
    if subset.empty:
        return pd.DataFrame()
    subset["player"] = subset["player"].fillna("").astype(str).str.strip()
    subset["team"] = subset["team"].fillna("").astype(str).str.strip()
    subset = subset[subset["player"] != ""]
    gp = subset.groupby(["player", "team"]).agg(
        games=("game_id", "nunique"),
        source_player_id=("source_player_id", "first"),
        source_person_id=("source_person_id", "first"),
    ).reset_index()
    gp["goals"] = 0
    gp["assists"] = 0
    gp["points"] = 0
    gp["penalties"] = 0
    gp["pim"] = 0
    gp["player_uid"] = gp["player"].apply(_canonical_player_uid)
    return _finalize_rows(gp, season=season, phase=phase, league="IFF WFC", source_system="wfc")


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


def _lineup_rows_for_prefix(
    prefix: str, matches: pd.DataFrame, season: str, phase: str, game_rosters: pd.DataFrame | None = None
) -> pd.DataFrame:
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
        if game_rosters is not None and not game_rosters.empty:
            db_rows = _wfc_roster_rows_from_frame(game_rosters, season=season, phase=phase)
            if not db_rows.empty:
                return db_rows
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
        swiss_alias_count = _refresh_player_identity_aliases(conn)
        cross_alias_count = _refresh_cross_league_abbreviated_aliases(conn)
        conn.commit()
        if swiss_alias_count:
            print(f"player-identity-aliases (swiss zero-stat): upserted {swiss_alias_count} rows")
        if cross_alias_count:
            print(f"player-identity-aliases (cross-league abbrev): upserted {cross_alias_count} rows")
        return len(rows)


def build_player_stats_from_postgres(*, database_url: str, output_csv: str = "") -> int:
    events = _load_events(database_url)
    game_rosters = _load_all_game_rosters(database_url)
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
                lineup_rows = _lineup_rows_for_prefix(prefix, matches, season=season_key, phase=phase_key, game_rosters=game_rosters)
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
