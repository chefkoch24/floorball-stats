from pathlib import Path

from PIL import Image

from src.social_media.render_home_away import render_home_away_post


def test_render_home_away_post_creates_1080x1350_image(tmp_path: Path):
    table = {
        "table_type": "home_away_split",
        "season": "25-26",
        "phase": "regular-season",
        "rows": [
            {
                "rank": 1,
                "team": "Team A",
                "points": 9,
                "home_points": 6,
                "away_points": 3,
                "goals_home": 10,
                "goals_against_home": 4,
                "goals_away": 6,
                "goals_against_away": 5,
                "home_diff": 6,
                "away_diff": 1,
                "split_points": 3,
                "split_diff": 5,
                "home_record_label": "10:4",
                "away_record_label": "6:5",
            }
        ],
    }
    output_path = tmp_path / "home-away.png"

    render_home_away_post(
        table,
        output_path,
        league="Test League",
        season_label="25-26",
    )

    assert output_path.exists()
    with Image.open(output_path) as image:
        assert image.size == (1080, 1350)
