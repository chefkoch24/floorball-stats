import argparse

from src.social_media.pipelines.cross_country_rankings import run_cross_country_ranking_export


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--metric", choices=["pp", "pk", "penalties"], default="pp")
    parser.add_argument("--theme", choices=["light", "dark"], default="light")
    parser.add_argument("--animated", action="store_true")
    parser.add_argument("--animation-style", choices=["standard", "fixed-slots"], default="standard")
    return parser.parse_args()


def main():
    args = parse_args()
    run_cross_country_ranking_export(
        output_path=args.output_path,
        metric=args.metric,
        theme=args.theme,
        animated=args.animated,
        animation_style=args.animation_style,
    )


if __name__ == "__main__":
    main()
