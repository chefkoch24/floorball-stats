import argparse

from src.social_media.pipelines.home_away import run_home_away_export


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table-path", default=None)
    parser.add_argument("--team-stats-path", default="data/team_stats_enhanced.json")
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--league", required=True)
    parser.add_argument("--season-label", default="25-26")
    parser.add_argument("--season", default=None)
    parser.add_argument("--phase", default="regular-season")
    parser.add_argument("--rows-limit", type=int, default=0)
    return parser.parse_args()


def main():
    args = parse_args()
    run_home_away_export(
        output_path=args.output_path,
        league=args.league,
        season_label=args.season_label,
        table_path=args.table_path,
        team_stats_path=args.team_stats_path,
        season=args.season,
        phase=args.phase,
        rows_limit=args.rows_limit or None,
    )


if __name__ == "__main__":
    main()
