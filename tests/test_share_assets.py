import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins"))

import share_assets  # noqa: E402

LEAGUES = [
    {"prefix": "se-", "name": "Sweden", "title": "Sweden · SSL", "division": "men"},
    {"prefix": "", "name": "Germany", "title": "Germany · 1. FBL Herren", "division": "men"},
    {"prefix": "sew-", "name": "Sweden", "title": "Sweden · SSL Damer", "division": "women"},
]
SETTINGS = {"CURRENT_SEASON": "26-27", "LEAGUES": LEAGUES}


def _game(game_id: str, start_time: str, result: str = "") -> share_assets._Game:
    return share_assets._Game(
        game_id=game_id,
        date=datetime(2026, 10, 31),
        start_time=start_time,
        home="Malmö FBC",
        away="Karlstad IBF",
        state="played" if result else "scheduled",
        result=result,
        url="https://stats.floorballconnect.com/" + "x" * 90 + ".html",
    )


def test_league_lookup_prefers_women_prefix_and_current_season():
    assert share_assets._league_for("sew-26-27-regular-season", SETTINGS)["prefix"] == "sew-"
    assert share_assets._league_for("se-26-27-playoffs", SETTINGS)["prefix"] == "se-"
    assert share_assets._league_for("26-27-regular-season", SETTINGS)["prefix"] == ""
    assert share_assets._league_for("se-25-26-regular-season", SETTINGS) is None


def test_calendar_converts_local_kickoff_to_utc_and_folds_lines():
    ics = share_assets.build_calendar(
        "Karlstad IBF", LEAGUES[2], [_game("2", "15:30:00"), _game("1", "TBD", result="3:10")], "stats.floorballconnect.com"
    )
    lines = ics.split("\r\n")
    # 31 Oct 2026 is after the switch to CET, so 15:30 in Stockholm is 14:30 UTC.
    assert "DTSTART:20261031T143000Z" in lines
    assert "DTEND:20261031T163000Z" in lines
    # Unknown kick-off times become all-day events.
    assert "DTSTART;VALUE=DATE:20261031" in lines
    assert "SUMMARY:Malmö FBC 3:10 Karlstad IBF" in lines
    assert "UID:game-1-sew@stats.floorballconnect.com" in lines
    assert all(len(line.encode("utf-8")) <= 75 for line in lines)
    assert ics.endswith("END:VCALENDAR\r\n")


def test_long_team_names_are_wrapped_to_fit(tmp_path):
    from PIL import Image, ImageDraw

    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    font, lines = share_assets._fit_lines(draw, "FBC ČPP MPL STAVEBNINY OSTRAVA", 380, 52, max_lines=3)
    assert len(lines) <= 3
    assert all(draw.textlength(line, font=font) <= 380 for line in lines)

    target = tmp_path / "card.png"
    share_assets.render(("game", "Czech Republic Women 26/27", "FBC ČPP MPL STAVEBNINY OSTRAVA", "GMS", "4:3", "Final"), target)
    assert Image.open(target).size == (1200, 630)


def test_logo_appears_in_share_preview(tmp_path):
    from PIL import Image
    import pelicanconf
    logo = pelicanconf.team_logo('Nokian KrP', 'fi-26-27-regular-season', 'share')
    target = tmp_path / 'team.png'
    share_assets.render(('team', 'Finland', 'Nokian KrP', '17 pts', logo), target)
    with Image.open(target).convert('RGB') as image:
        assert image.getpixel((550, 100)) == (255, 255, 255)


def test_logo_change_invalidates_preview_cache(tmp_path, monkeypatch):
    from PIL import Image
    logo = tmp_path / 'logo.png'
    Image.new('RGBA', (20, 20), 'red').save(logo)
    monkeypatch.setattr(share_assets, '_local_logo', lambda path: logo)
    monkeypatch.setattr(share_assets, 'CACHE_DIR', tmp_path / 'cache')
    spec = ('team', 'Finland', 'Example', '', 'theme/team-logos/logo.png')
    output = tmp_path / 'out.png'
    share_assets._write_image(spec, output)
    first = output.read_bytes()
    Image.new('RGBA', (20, 20), 'blue').save(logo)
    share_assets._write_image(spec, output)
    assert output.read_bytes() != first


def test_category_facts_describe_the_page_type():
    assert share_assets._category_facts("se-26-27-regular-season") == "Standings, results and stats"
    assert share_assets._category_facts("se-26-27-playoffs") == "Playoff bracket and results"
    assert share_assets._category_facts("ch-26-27-cup") == "Cup results by round"
    assert share_assets._category_facts("se-26-27-players") == "Player rankings and stats"


def test_league_image_is_rendered(tmp_path):
    target = tmp_path / "og" / "category-se-26-27-regular-season.png"
    spec = ("league", "Sweden · SSL", "Sweden · SSL", "Standings, results and stats")
    share_assets._write_image(spec, target)
    from PIL import Image

    with Image.open(target) as image:
        assert image.size == (share_assets.WIDTH, share_assets.HEIGHT)
