"""Share images (og:image) and team calendar feeds (.ics) for the current season.

Game and team articles of ``CURRENT_SEASON`` get ``article.og_image`` (a PNG
rendered with Pillow) and team articles get ``article.calendar_path`` (an
iCalendar feed with all regular-season and playoff games of that team).
Other pages fall back to ``og/default.png``. Rendered images are cached in
``.cache/og`` by content hash, so rebuilds only draw what changed.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pelican import signals
from pelican.utils import slugify

# Bump when the drawing code changes so cached images are re-rendered.
RENDER_VERSION = "5"
CACHE_DIR = Path(".cache/og")
WIDTH, HEIGHT = 1200, 630
GAME_DURATION = timedelta(hours=2)

# Country part of the league prefix (women's leagues append "w") -> local time zone.
COUNTRY_TIMEZONES = {
    "se": "Europe/Stockholm",
    "fi": "Europe/Helsinki",
    "cz": "Europe/Prague",
    "ch": "Europe/Zurich",
    "sk": "Europe/Bratislava",
    "lv": "Europe/Riga",
    "": "Europe/Berlin",
}

BACKGROUND = (21, 31, 48)
BRAND = (77, 163, 255)
TEXT = (243, 247, 252)
MUTED = (156, 172, 191)


@dataclass
class _Game:
    game_id: str
    date: datetime
    start_time: str
    home: str
    away: str
    state: str
    result: str
    url: str
    decision: str = ""


@dataclass
class _ShareState:
    images: dict[str, tuple] = field(default_factory=dict)
    calendars: dict[str, dict] = field(default_factory=dict)


_state = _ShareState()


def _meta(article, key: str, default: str = "") -> str:
    value = getattr(article, key, default)
    if isinstance(value, list):
        value = value[0] if value else default
    text = str(value if value is not None else default).strip()
    return "" if text in {"None", "nan"} else text


def _league_for(category: str, settings: dict) -> dict | None:
    season = settings.get("CURRENT_SEASON", "")
    # Longest prefix first, so "sew-" wins over Germany's empty prefix.
    for league in sorted(settings.get("LEAGUES", []), key=lambda item: -len(item["prefix"])):
        if category.startswith(f"{league['prefix']}{season}-"):
            return league
    return None


def _timezone_for(league: dict) -> ZoneInfo:
    prefix = league["prefix"].rstrip("-")
    country = prefix[:-1] if len(prefix) == 3 and prefix.endswith("w") else prefix
    return ZoneInfo(COUNTRY_TIMEZONES.get(country, "Europe/Berlin"))


def _score_label(article) -> str:
    home = _meta(article, "home_goals")
    away = _meta(article, "away_goals")
    if _meta(article, "game_state") != "played" or not home or not away:
        return ""
    return f"{home}:{away}"


def _decision_label(article) -> str:
    def _goals(key: str) -> int:
        try:
            return int(float(_meta(article, key, "0") or 0))
        except ValueError:
            return 0

    if _goals("home_goals_in_penalty_shootout") or _goals("away_goals_in_penalty_shootout"):
        return "After penalty shots"
    if _goals("home_goals_in_overtime") or _goals("away_goals_in_overtime"):
        return "After overtime"
    return "Final"


def _decision_short(article) -> str:
    label = _decision_label(article)
    return {"After penalty shots": "PS", "After overtime": "OT"}.get(label, "")


def _form_letter(game: _Game, team: str) -> str:
    home_goals, away_goals = (int(part) for part in game.result.split(":"))
    own, other = (home_goals, away_goals) if game.home == team else (away_goals, home_goals)
    if own == other:
        return "D"
    return ("OTW" if game.decision else "W") if own > other else ("OTL" if game.decision else "L")


def _share_team_data(team_entries: list, settings: dict) -> None:
    """Form, next game and table size for the team share card (share-card.js)."""
    crest_index = settings["JINJA_FILTERS"]["crest_index"]
    initials = settings["JINJA_FILTERS"]["team_initials"]
    team_counts: dict[str, int] = {}
    rounds: dict[str, int] = {}
    for article, _team, category in team_entries:
        team_counts[category] = team_counts.get(category, 0) + 1
        try:
            rounds[category] = max(rounds.get(category, 0), int(float(_meta(article, "games", "0") or 0)))
        except ValueError:
            pass
    for article, team, category in team_entries:
        games = list(_state.calendars.get(article.calendar_path, {}).get("games", {}).values())
        played = sorted((g for g in games if g.result), key=lambda g: (g.date, g.game_id))
        upcoming = sorted((g for g in games if not g.result and g.state == "scheduled"), key=lambda g: (g.date, g.start_time))
        next_game = None
        if upcoming:
            game = upcoming[0]
            opponent = game.away if game.home == team else game.home
            next_game = {
                "date": game.date.strftime("%a %-d %b"),
                "time": game.start_time[:5] if ":" in game.start_time else "",
                "home": game.home == team,
                "opponent": opponent,
                "crest": crest_index(opponent),
                "initials": initials(opponent),
            }
        article.share_team = {
            "teams": team_counts.get(category, 0),
            "round": rounds.get(category, 0),
            "form": [_form_letter(game, team) for game in played[-5:]],
            "next": next_game,
        }


def collect(generator) -> None:
    # Autoreload runs several builds in one process.
    _state.images.clear()
    _state.calendars.clear()
    settings = generator.settings
    label_for = settings["JINJA_FILTERS"]["category2string"]
    team_entries = []
    for article in generator.articles:
        category = article.category.shortname if article.category else ""
        league = _league_for(category, settings)
        if league is None:
            continue
        article_type = _meta(article, "type")
        league_label = label_for(category)
        if article_type == "game":
            date_text = article.date.strftime("%d %b %Y")
            score = _score_label(article)
            if score:
                status = f"{_decision_label(article)} · {date_text}"
            else:
                start = _meta(article, "start_time")[:5]
                status = f"{date_text} · {start}" if start else date_text
            spec = ("game", league_label, _meta(article, "home_team"), _meta(article, "away_team"), score, status)
            _register_image(article, spec)
            _register_game(article, league, settings)
        elif article_type == "team":
            rank = _meta(article, "rank")
            points = _meta(article, "points")
            games = _meta(article, "games")
            facts = " · ".join(
                part
                for part in [f"Rank {rank}" if rank else "", f"{points} pts" if points else "", f"{games} games" if games else ""]
                if part
            )
            team = _meta(article, "team") or _meta(article, "title")
            _register_image(article, ("team", league_label, team, facts))
            article.calendar_path = _calendar_path(league, settings, team)
            team_entries.append((article, team, category))
    _share_team_data(team_entries, settings)


def _register_image(article, spec: tuple) -> None:
    path = f"og/{article.slug}.png"
    article.og_image = path
    _state.images[path] = spec


def _calendar_path(league: dict, settings: dict, team: str) -> str:
    slug = slugify(team, regex_subs=settings.get("SLUG_REGEX_SUBSTITUTIONS", []))
    return f"calendar/{league['prefix']}{settings['CURRENT_SEASON']}-{slug}.ics"


def _register_game(article, league: dict, settings: dict) -> None:
    game = _Game(
        game_id=_meta(article, "game_id") or article.slug,
        date=article.date,
        start_time=_meta(article, "start_time"),
        home=_meta(article, "home_team"),
        away=_meta(article, "away_team"),
        state=_meta(article, "game_state"),
        result=_score_label(article),
        url=f"{settings.get('SITEURL', '')}/{article.url}",
        decision=_decision_short(article),
    )
    for team in (game.home, game.away):
        if not team:
            continue
        path = _calendar_path(league, settings, team)
        calendar = _state.calendars.setdefault(path, {"team": team, "league": league, "games": {}})
        calendar["games"][game.game_id] = game


@lru_cache(maxsize=None)
def _font(size: int, bold: bool = True):
    from matplotlib import get_data_path
    from PIL import ImageFont

    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(str(Path(get_data_path()) / "fonts" / "ttf" / name), size=size)


def _fit_lines(draw, text: str, max_width: int, start: int, max_lines: int, minimum: int = 24):
    """Largest font whose wrapped lines (at most ``max_lines``) all fit ``max_width``."""
    for size in range(start, minimum - 1, -2):
        font = _font(size)
        lines = _wrap(draw, text, font, max_width, max_lines=max_lines)
        if all(draw.textlength(line, font=font) <= max_width for line in lines):
            return font, lines
    font = _font(minimum)
    return font, _wrap(draw, text, font, max_width, max_lines=max_lines)


def _wrap(draw, text: str, font, max_width: int, max_lines: int = 2) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and draw.textlength(f"{lines[-1]} {word}", font=font) <= max_width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [" ".join(lines[max_lines - 1 :])]
    return lines


def _draw_centered(draw, lines: list[str], font, center_x: int, center_y: int, fill, spacing: int = 8) -> None:
    heights = [font.getbbox(line)[3] for line in lines]
    total = sum(heights) + spacing * (len(lines) - 1)
    y = center_y - total / 2
    for line, height in zip(lines, heights):
        draw.text((center_x - draw.textlength(line, font=font) / 2, y), line, font=font, fill=fill)
        y += height + spacing


@lru_cache(maxsize=1)
def _background():
    from PIL import Image, ImageDraw

    # Flat colours only, so the 64-colour palette keeps them exact.
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    ImageDraw.Draw(image).rectangle([(0, 0), (WIDTH, 10)], fill=BRAND)
    return image


def _save(image, target: Path) -> None:
    # A 64-colour palette keeps the flat cards around 10 KB.
    target.parent.mkdir(parents=True, exist_ok=True)
    image.quantize(colors=64).save(target, "PNG")


def render(spec: tuple, target: Path) -> None:
    from PIL import Image, ImageDraw

    image = _background().copy()
    draw = ImageDraw.Draw(image)

    footer_font = _font(26, bold=False)
    footer = "stats.floorballconnect.com"
    draw.text((WIDTH - 64 - draw.textlength(footer, font=footer_font), HEIGHT - 80), footer, font=footer_font, fill=MUTED)

    if spec[0] == "default":
        _draw_centered(draw, ["Floorball Stats"], _font(96), WIDTH // 2, 270, TEXT)
        _draw_centered(draw, [spec[1]], _font(34, bold=False), WIDTH // 2, 380, MUTED)
        _save(image, target)
        return

    draw.text((64, 52), "FLOORBALL STATS", font=_font(30), fill=BRAND)
    league_font = _font(30, bold=False)
    draw.text((WIDTH - 64 - draw.textlength(spec[1], font=league_font), 54), spec[1], font=league_font, fill=MUTED)
    if spec[0] == "game":
        _, _, home, away, score, status = spec
        side_width = 380
        for name, center_x in ((home, 240), (away, WIDTH - 240)):
            font, lines = _fit_lines(draw, name, side_width, 52, max_lines=3)
            _draw_centered(draw, lines, font, center_x, 300, TEXT)
        if score:
            _draw_centered(draw, [score], _font(110), WIDTH // 2, 290, TEXT)
        else:
            _draw_centered(draw, ["vs"], _font(60, bold=False), WIDTH // 2, 300, MUTED)
        _draw_centered(draw, [status], _font(30, bold=False), WIDTH // 2, 450, MUTED)
    else:
        _, _, team, facts = spec
        font, lines = _fit_lines(draw, team, WIDTH - 160, 88, max_lines=2)
        _draw_centered(draw, lines, font, WIDTH // 2, 280, TEXT)
        if facts:
            _draw_centered(draw, [facts], _font(38, bold=False), WIDTH // 2, 450, MUTED)

    _save(image, target)


def _write_image(spec: tuple, target: Path) -> None:
    digest = hashlib.sha1(repr((RENDER_VERSION, spec)).encode("utf-8")).hexdigest()
    cached = CACHE_DIR / f"{digest}.png"
    if not cached.exists():
        render(spec, cached)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cached, target)


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """Fold content lines to 75 octets as RFC 5545 requires."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts: list[str] = []
    current = b""
    for char in line:
        encoded = char.encode("utf-8")
        if len(current) + len(encoded) > (75 if not parts else 74):
            parts.append(current.decode("utf-8"))
            current = b""
        current += encoded
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def build_calendar(team: str, league: dict, games: list[_Game], site_host: str) -> str:
    zone = _timezone_for(league)
    stamp_format = "%Y%m%dT%H%M%SZ"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Floorball Stats//Team calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_escape(team)} · {_ics_escape(league['title'])}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for game in sorted(games, key=lambda item: (item.date, item.game_id)):
        day = game.date.date()
        summary = f"{game.home} {game.result} {game.away}" if game.result else f"{game.home} vs {game.away}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:game-{game.game_id}-{league['prefix'].rstrip('-') or 'de'}@{site_host}",
            f"DTSTAMP:{datetime(day.year, day.month, day.day, tzinfo=timezone.utc).strftime(stamp_format)}",
        ]
        try:
            hour, minute = (int(part) for part in game.start_time.split(":")[:2])
        except ValueError:
            lines += [
                f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}",
            ]
        else:
            start = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone).astimezone(timezone.utc)
            lines += [
                f"DTSTART:{start.strftime(stamp_format)}",
                f"DTEND:{(start + GAME_DURATION).strftime(stamp_format)}",
            ]
        lines += [
            f"SUMMARY:{_ics_escape(summary)}",
            f"DESCRIPTION:{_ics_escape(league['title'] + ' · ' + game.url)}",
            f"URL:{game.url}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def write_outputs(pelican) -> None:
    output = Path(pelican.settings["OUTPUT_PATH"])
    site_host = (pelican.settings.get("SITEURL") or "https://stats.floorballconnect.com").split("://")[-1]
    _write_image(("default", "Standings, results and stats for top Floorball leagues"), output / "og" / "default.png")
    for path, spec in _state.images.items():
        _write_image(spec, output / path)
    for path, calendar in _state.calendars.items():
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        content = build_calendar(calendar["team"], calendar["league"], list(calendar["games"].values()), site_host)
        target.write_text(content, encoding="utf-8")


def register() -> None:
    signals.article_generator_finalized.connect(collect)
    signals.finalized.connect(write_outputs)
