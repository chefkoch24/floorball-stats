import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from src.social_media.tables import build_home_away_split_table


WIDTH = 1080
HEIGHT = 1350
PADDING = 72

BG = "#f3f5f9"
SURFACE = "#ffffff"
SURFACE_MUTED = "#f9fafc"
TEXT = "#111827"
TEXT_MUTED = "#5b6472"
LINE = "#e4e8ef"
BRAND = "#0071e2"
ACCENT = "#0f4c81"
HOME = "#0f4c81"
AWAY = "#c62828"

FONT_REGULAR = "/System/Library/Fonts/HelveticaNeue.ttc"
FONT_BOLD = "/System/Library/Fonts/HelveticaNeue.ttc"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(FONT_REGULAR, size=size)
    except OSError:
        return ImageFont.load_default()


def _font_bold(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(FONT_BOLD, size=size, index=1)
    except OSError:
        try:
            return ImageFont.truetype(FONT_BOLD, size=size)
        except OSError:
            return ImageFont.load_default()


def _draw_rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str, outline: str | None = None, width: int = 1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    if _text_size(draw, text, font)[0] <= max_width:
        return text
    candidate = text
    while len(candidate) > 3:
        candidate = candidate[:-1]
        shortened = candidate.rstrip() + "..."
        if _text_size(draw, shortened, font)[0] <= max_width:
            return shortened
    return text[:3]


def _signed(value: int) -> str:
    return str(value)


def _format_ppg(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}".replace(".", ",")


def load_table(table_path: str | None, team_stats_path: str | None, season: str | None, phase: str | None) -> dict[str, Any]:
    if table_path:
        return json.loads(Path(table_path).read_text(encoding="utf-8"))
    if not team_stats_path:
        raise ValueError("Either table_path or team_stats_path is required.")
    team_stats = json.loads(Path(team_stats_path).read_text(encoding="utf-8"))
    return build_home_away_split_table(team_stats, season=season, phase=phase)


def render_home_away_post(
    table: dict[str, Any],
    output_path: str | Path,
    *,
    league: str,
    season_label: str,
    rows_limit: int | None = None,
) -> Path:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    title_font = _font_bold(62)
    body_font = _font(25)
    body_bold = _font_bold(25)
    small_font = _font(24)
    small_bold = _font_bold(24)

    y = 70
    draw.text((PADDING, y), "Home / Away Table", font=title_font, fill=BRAND)
    y += 74
    draw.text((PADDING, y), "Regular season split by venue", font=small_font, fill=TEXT_MUTED)
    y += 52

    chip_y = y
    chips = [league, "Regular Season"]
    chip_x = PADDING
    for chip in chips:
        chip_w, chip_h = _text_size(draw, chip, small_bold)
        box = (chip_x, chip_y, chip_x + chip_w + 34, chip_y + chip_h + 20)
        _draw_rounded(draw, box, 24, fill=SURFACE, outline=LINE)
        draw.text((chip_x + 17, chip_y + 10), chip, font=small_bold, fill=ACCENT)
        chip_x = box[2] + 14
    y = chip_y + 82

    panel = (PADDING, y, WIDTH - PADDING, HEIGHT - 72)
    _draw_rounded(draw, panel, 26, fill=SURFACE, outline=LINE, width=2)
    panel_x1, panel_y1, panel_x2, panel_y2 = panel
    inner_pad = 34

    table_x1 = panel_x1 + inner_pad
    table_x2 = panel_x2 - inner_pad
    table_y1 = panel_y1 + 28
    header_h = 86

    _draw_rounded(draw, (table_x1, table_y1, table_x2, table_y1 + header_h), 18, fill=SURFACE_MUTED)

    columns = [
        ("Team", 0.00, 0.34),
        ("Points Home", 0.34, 0.45),
        ("Points Away", 0.45, 0.56),
        ("PPG Home", 0.56, 0.67),
        ("PPG Away", 0.67, 0.78),
        ("Goals Home", 0.78, 0.89),
        ("Goals Away", 0.89, 1.00),
    ]

    table_width = table_x2 - table_x1
    team_left = table_x1 + int(table_width * columns[0][1])
    points_left = table_x1 + int(table_width * columns[1][1])
    points_right = table_x1 + int(table_width * columns[2][2])
    ppg_left = table_x1 + int(table_width * columns[3][1])
    ppg_right = table_x1 + int(table_width * columns[4][2])
    goals_left = table_x1 + int(table_width * columns[5][1])
    goals_right = table_x1 + int(table_width * columns[6][2])

    draw.text((team_left + 14, table_y1 + 12), "Team", font=small_bold, fill="#334155")

    points_label = "Points"
    pw, _ = _text_size(draw, points_label, small_bold)
    draw.text((points_left + (points_right - points_left - pw) / 2, table_y1 + 12), points_label, font=small_bold, fill="#334155")

    ppg_label = "PPG"
    ppgw, _ = _text_size(draw, ppg_label, small_bold)
    draw.text((ppg_left + (ppg_right - ppg_left - ppgw) / 2, table_y1 + 12), ppg_label, font=small_bold, fill="#334155")

    goals_label = "Goals"
    gw, _ = _text_size(draw, goals_label, small_bold)
    draw.text((goals_left + (goals_right - goals_left - gw) / 2, table_y1 + 12), goals_label, font=small_bold, fill="#334155")

    for label, start, end in columns[1:]:
        col_right = table_x1 + int(table_width * end)
        sublabel = label.split()[-1]
        label_w, _ = _text_size(draw, sublabel, small_font)
        x = col_right - label_w - 14
        draw.text((x, table_y1 + 46), sublabel, font=small_font, fill=TEXT_MUTED)

    all_rows = table.get("rows", [])
    rows = all_rows[:rows_limit] if rows_limit else all_rows
    available_rows_height = panel_y2 - 24 - (table_y1 + header_h)
    row_h = max(48, available_rows_height // max(len(rows), 1))

    if len(rows) > 10:
        body_font = _font(23)
        body_bold = _font_bold(23)
        small_font = _font(20)
        small_bold = _font_bold(20)

    for idx, row in enumerate(rows):
        top = table_y1 + header_h + idx * row_h
        bottom = top + row_h
        draw.line((table_x1, bottom, table_x2, bottom), fill=LINE, width=2)

        rank_x = table_x1 + 12
        rank_y = top + max(10, (row_h - 34) // 2)
        rank_box = (rank_x, rank_y, rank_x + 42, rank_y + 34)
        _draw_rounded(draw, rank_box, 17, fill=SURFACE_MUTED)
        rank_label = str(row["rank"])
        rw, rh = _text_size(draw, rank_label, small_bold)
        draw.text((rank_x + 21 - rw / 2, rank_y + 17 - rh / 2), rank_label, font=small_bold, fill=TEXT_MUTED)

        team_x = table_x1 + 68
        team_text = _fit_text(draw, row["team"], body_bold, 238)
        team_y = top + max(10, (row_h - _text_size(draw, team_text, body_bold)[1]) // 2) - 2
        draw.text((team_x, team_y), team_text, font=body_bold, fill=TEXT)

        value_y = top + max(10, (row_h - _text_size(draw, "12", body_bold)[1]) // 2)
        home_text = str(row["home_points"])
        away_text = str(row["away_points"])
        home_ppg_text = _format_ppg(row.get("home_points_per_game"))
        away_ppg_text = _format_ppg(row.get("away_points_per_game"))
        home_w, _ = _text_size(draw, home_text, body_bold)
        away_w, _ = _text_size(draw, away_text, body_bold)
        home_ppg_w, _ = _text_size(draw, home_ppg_text, body_font)
        away_ppg_w, _ = _text_size(draw, away_ppg_text, body_font)
        home_right = table_x1 + int(table_width * 0.45) - 14
        away_right = table_x1 + int(table_width * 0.56) - 14
        home_ppg_right = table_x1 + int(table_width * 0.67) - 14
        away_ppg_right = table_x1 + int(table_width * 0.78) - 14
        draw.text((home_right - home_w, value_y), home_text, font=body_bold, fill=HOME)
        draw.text((away_right - away_w, value_y), away_text, font=body_bold, fill=AWAY)
        draw.text((home_ppg_right - home_ppg_w, value_y), home_ppg_text, font=body_font, fill=HOME)
        draw.text((away_ppg_right - away_ppg_w, value_y), away_ppg_text, font=body_font, fill=AWAY)

        home_record_text = row["home_record_label"]
        away_record_text = row["away_record_label"]
        home_diff_w, _ = _text_size(draw, home_record_text, small_font)
        away_diff_w, _ = _text_size(draw, away_record_text, small_font)
        home_diff_right = table_x1 + int(table_width * 0.89) - 14
        away_diff_right = table_x1 + int(table_width * 1.00) - 14
        draw.text((home_diff_right - home_diff_w, value_y + 2), home_record_text, font=small_font, fill=HOME)
        draw.text((away_diff_right - away_diff_w, value_y + 2), away_record_text, font=small_font, fill=AWAY)

    handle = "@foorballconnect"
    handle_w, handle_h = _text_size(draw, handle, small_bold)
    draw.text((WIDTH - PADDING - handle_w, HEIGHT - 44 - handle_h), handle, font=small_bold, fill=TEXT_MUTED)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_file)
    return output_file


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
    table = load_table(
        table_path=args.table_path,
        team_stats_path=args.team_stats_path,
        season=args.season or args.season_label,
        phase=args.phase,
    )
    render_home_away_post(
        table,
        args.output_path,
        league=args.league,
        season_label=args.season_label,
        rows_limit=args.rows_limit or None,
    )


if __name__ == "__main__":
    main()
