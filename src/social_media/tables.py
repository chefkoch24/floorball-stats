import json
from pathlib import Path
from typing import Any


def _build_home_away_games_map(game_stats: list[dict[str, Any]] | None) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for game in game_stats or []:
        home_team = game.get("home_team")
        away_team = game.get("away_team")
        if home_team:
            counts.setdefault(str(home_team), {"home_games": 0, "away_games": 0})
            counts[str(home_team)]["home_games"] += 1
        if away_team:
            counts.setdefault(str(away_team), {"home_games": 0, "away_games": 0})
            counts[str(away_team)]["away_games"] += 1
    return counts


def build_home_away_split_table(
    team_stats: dict[str, dict[str, Any]],
    game_stats: list[dict[str, Any]] | None = None,
    *,
    season: str | None = None,
    phase: str | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    game_counts = _build_home_away_games_map(game_stats)

    for team, stats in team_stats.items():
        goals_home = int(stats.get("goals_home", 0))
        goals_against_home = int(stats.get("goals_against_home", 0))
        goals_away = int(stats.get("goals_away", 0))
        goals_against_away = int(stats.get("goals_against_away", 0))
        home_points = int(stats.get("home_points", 0))
        away_points = int(stats.get("away_points", 0))

        home_diff = goals_home - goals_against_home
        away_diff = goals_away - goals_against_away
        split_points = home_points - away_points
        split_diff = home_diff - away_diff
        home_games = int(game_counts.get(team, {}).get("home_games", 0))
        away_games = int(game_counts.get(team, {}).get("away_games", 0))
        home_ppg = round(home_points / home_games, 2) if home_games else None
        away_ppg = round(away_points / away_games, 2) if away_games else None

        rows.append(
            {
                "rank": int(stats.get("rank", 0)),
                "team": team,
                "points": int(stats.get("points", 0)),
                "home_points": home_points,
                "away_points": away_points,
                "home_games": home_games,
                "away_games": away_games,
                "home_points_per_game": home_ppg,
                "away_points_per_game": away_ppg,
                "goals_home": goals_home,
                "goals_against_home": goals_against_home,
                "goals_away": goals_away,
                "goals_against_away": goals_against_away,
                "home_diff": home_diff,
                "away_diff": away_diff,
                "split_points": split_points,
                "split_diff": split_diff,
                "home_record_label": f"{goals_home}:{goals_against_home}",
                "away_record_label": f"{goals_away}:{goals_against_away}",
            }
        )

    rows.sort(
        key=lambda row: (
            -row["points"],
            -int(team_stats[row["team"]].get("goal_difference", 0)),
            -int(team_stats[row["team"]].get("goals", 0)),
            row["team"].lower(),
        )
    )

    return {
        "table_type": "home_away_split",
        "season": season,
        "phase": phase,
        "rows": rows,
    }


def write_home_away_split_table(
    team_stats: dict[str, dict[str, Any]],
    output_path: str | Path,
    game_stats: list[dict[str, Any]] | None = None,
    *,
    season: str | None = None,
    phase: str | None = None,
) -> dict[str, Any]:
    table = build_home_away_split_table(team_stats, game_stats, season=season, phase=phase)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(table, indent=4), encoding="utf-8")
    return table
