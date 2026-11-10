import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "plugins"))

import llms_txt  # noqa: E402

SITE = "https://stats.example.com"
SETTINGS = {
    "SITEURL": SITE,
    "SEASONS": ["26-27", "25-26"],
    "CURRENT_SEASON": "26-27",
    "LEAGUES": [
        {"prefix": "se-", "name": "Sweden", "title": "Sweden · SSL", "division": "men"},
        {"prefix": "sew-", "name": "Sweden", "title": "Sweden · SSL Damer", "division": "women"},
    ],
    "COMPETITIONS": [
        {"prefix": "cc-", "name": "Champions Cup", "title": "IFF Champions Cup", "division": "men",
         "phase": "playoffs", "competition": True},
    ],
    "LLMS_TEAMS": {"se-26-27-regular-season": [("IBF Falun", "ibf-falun.html")]},
}


def test_lists_only_generated_pages_with_the_root_as_home() -> None:
    built = {"index.html", "leaders.html", "category/se-26-27-regular-season.html",
             "category/se-26-27-regular-season-players.html", "category/cc-26-27-playoffs.html",
             "category/se-25-26-playoffs.html", "ibf-falun.html"}
    text = llms_txt.build(SETTINGS, built.__contains__)

    assert text.startswith("# Floorball Stats\n\n> ")
    assert f"- [Home]({SITE}/):" in text
    assert f"{SITE}/category/se-26-27-regular-season.html" in text
    assert f"{SITE}/category/cc-26-27-playoffs.html" in text
    assert f"{SITE}/ibf-falun.html" in text
    # Not generated, so not listed: the women's league, the cup, crowds.
    assert "sew-26-27" not in text
    assert "se-26-27-cup" not in text
    assert "crowds.html" not in text
    assert "## Women's leagues" not in text
    # Teams and older seasons are optional context.
    optional = text.index("## Optional")
    assert text.index("ibf-falun.html") > optional
    assert text.index("se-25-26-playoffs") > optional
