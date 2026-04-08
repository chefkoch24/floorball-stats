import argparse
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

WIDTH = 1080
HEIGHT = 1350
PADDING = 72
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"

LIGHT_THEME = {
    "bg": "#f3f5f9",
    "surface": "#ffffff",
    "surface_muted": "#f9fafc",
    "text": "#111827",
    "text_muted": "#5b6472",
    "line": "#e4e8ef",
    "brand": "#0071e2",
    "accent": "#0f4c81",
}

COUNTRY_STYLES = {
    "DE": ("#f4efe2", "#8a6a18"),
    "SE": ("#e8f1ff", "#1f5ea8"),
    "FI": ("#ebf3ff", "#225ea8"),
    "CH": ("#fdecec", "#b42318"),
    "CZ": ("#eef4ff", "#3056a0"),
    "LV": ("#fdeff1", "#a52a4a"),
    "SK": ("#eef5ff", "#335ca8"),
}


def _font(size: int, bold: bool = False):
    try:
        return ImageFont.truetype(FONT, size=size, index=1 if bold else 0)
    except OSError:
        return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    if _text_size(draw, text, font)[0] <= max_width:
        return text
    candidate = text
    while len(candidate) > 3:
        candidate = candidate[:-1]
        fitted = candidate.rstrip() + "..."
        if _text_size(draw, fitted, font)[0] <= max_width:
            return fitted
    return text[:3]


def _rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _country_abbr(league: str, season: str) -> str:
    mapping = {
        "Germany": "DE",
        "Switzerland": "CH",
        "Czech Republic": "CZ",
        "Finland": "FI",
        "Latvia": "LV",
        "Sweden": "SE",
        "Slovakia": "SK",
    }
    if league in mapping:
        return mapping[league]
    lower = (season or "").lower()
    for prefix, abbr in {
        "ch-": "CH",
        "cz-": "CZ",
        "fi-": "FI",
        "lv-": "LV",
        "se-": "SE",
        "sk-": "SK",
    }.items():
        if lower.startswith(prefix):
            return abbr
    return "DE"


def _season_key(raw: str) -> tuple[int, int]:
    value = (raw or "").strip().lower()
    if "-" in value:
        part = value.split("-")
        if len(part) >= 2:
            try:
                return (int(part[-2]), int(part[-1]))
            except ValueError:
                pass
    return (0, 0)


def _campaign_from_season(raw: str) -> str:
    value = (raw or "").strip().lower()
    parts = value.split("-")
    if len(parts) >= 2 and parts[-2].isdigit() and parts[-1].isdigit():
        return f"{parts[-2]}-{parts[-1]}"
    return value


def load_top10(csv_path: Path, metric: str, season: str | None = None) -> tuple[pd.DataFrame, str]:
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    df = df[df["phase"].str.lower() == "playoffs"].copy()
    if df.empty:
        return df, season or ""

    selected_campaign = season
    if not selected_campaign:
        campaigns = sorted({_campaign_from_season(s) for s in df["season"].tolist() if s}, key=_season_key)
        selected_campaign = campaigns[-1] if campaigns else ""
    df = df[df["season"].map(_campaign_from_season) == selected_campaign].copy()

    df["games"] = _to_num(df["games"])
    df["goals"] = _to_num(df["goals"])
    df["assists"] = _to_num(df["assists"])
    df["points"] = _to_num(df["points"])
    df = df[df["games"] > 0].copy()

    if df.empty:
        return df, selected_campaign

    df["ppg"] = df["points"] / df["games"]
    df["gpg"] = df["goals"] / df["games"]
    df["apg"] = df["assists"] / df["games"]
    df["country"] = [
        _country_abbr(league, season_val)
        for league, season_val in zip(df["league"].tolist(), df["season"].tolist())
    ]

    sort_cols = {
        "ppg": ["ppg", "points", "goals", "assists"],
        "gpg": ["gpg", "goals", "points", "assists"],
        "apg": ["apg", "assists", "points", "goals"],
    }[metric]
    ascending = [False, False, False, False]
    top = df.sort_values(sort_cols, ascending=ascending).head(10).copy()
    return top, selected_campaign


def render_slide(rows: pd.DataFrame, metric: str, season: str, output: Path):
    metric_meta = {
        "ppg": ("Top 10 Playoff Scorers", "Sorted by Points/Game", "P/G"),
        "gpg": ("Top 10 Playoff Scorers", "Sorted by Goals/Game", "G/G"),
        "apg": ("Top 10 Playoff Scorers", "Sorted by Assists/Game", "A/G"),
    }
    title, subtitle, metric_label = metric_meta[metric]
    theme = LIGHT_THEME

    img = Image.new("RGB", (WIDTH, HEIGHT), theme["bg"])
    draw = ImageDraw.Draw(img)
    title_font = _font(60, bold=True)
    subtitle_font = _font(24, bold=False)
    chip_font = _font(23, bold=True)
    header_font = _font(22, bold=True)
    body_font = _font(25, bold=False)
    body_bold = _font(25, bold=True)
    small_font = _font(21, bold=False)
    chip_small = _font(19, bold=True)

    y = 68
    draw.text((PADDING, y), title, font=title_font, fill=theme["brand"])
    y += 72
    draw.text((PADDING, y), subtitle, font=subtitle_font, fill=theme["text_muted"])
    y += 50

    chips = ["Cross-country", f"{season} Playoffs"]
    chip_x = PADDING
    for chip in chips:
        cw, ch = _text_size(draw, chip, chip_font)
        box = (chip_x, y, chip_x + cw + 34, y + ch + 20)
        _rounded(draw, box, 24, theme["surface"], outline=theme["line"])
        draw.text((chip_x + 17, y + 10), chip, font=chip_font, fill=theme["accent"])
        chip_x = box[2] + 14

    y += 82
    header_h = 56
    row_h = 95
    panel_h = 28 + header_h + row_h * len(rows) + 18
    panel = (PADDING, y, WIDTH - PADDING, y + panel_h)
    _rounded(draw, panel, 26, theme["surface"], outline=theme["line"], width=2)

    x1, y1, x2, _ = panel
    inner = 34
    table_x1 = x1 + inner
    table_x2 = x2 - inner
    table_y1 = y1 + 28
    table_w = table_x2 - table_x1
    _rounded(draw, (table_x1, table_y1, table_x2, table_y1 + header_h), 18, theme["surface_muted"])

    cols = [
        ("#", 0.00, 0.08, "left"),
        ("Player", 0.08, 0.58, "left"),
        ("GP", 0.58, 0.66, "right"),
        ("G", 0.66, 0.74, "right"),
        ("A", 0.74, 0.82, "right"),
        ("P", 0.82, 0.90, "right"),
        (metric_label, 0.90, 1.00, "right"),
    ]
    head_color = "#334155"
    for label, start, end, align in cols:
        tw, _ = _text_size(draw, label, header_font)
        left = table_x1 + int(table_w * start)
        right = table_x1 + int(table_w * end) - 14
        if align == "left":
            draw.text((left + 14, table_y1 + 16), label, font=header_font, fill=head_color)
        else:
            draw.text((right - tw, table_y1 + 16), label, font=header_font, fill=head_color)

    for i, (_, row) in enumerate(rows.iterrows(), start=1):
        top = table_y1 + header_h + (i - 1) * row_h
        bottom = top + row_h
        draw.line((table_x1, bottom, table_x2, bottom), fill=theme["line"], width=2)

        rank_box = (table_x1 + 10, top + 28, table_x1 + 48, top + 62)
        _rounded(draw, rank_box, 17, theme["surface_muted"])
        rank_txt = str(i)
        rw, rh = _text_size(draw, rank_txt, small_font)
        draw.text((rank_box[0] + 19 - rw / 2, rank_box[1] + 17 - rh / 2), rank_txt, font=small_font, fill=theme["text_muted"])

        player_x = table_x1 + int(table_w * 0.08) + 14
        player_max_w = int(table_w * (0.58 - 0.08)) - 24
        country = str(row["country"])
        chip_text = country
        ctw, cth = _text_size(draw, chip_text, chip_small)
        chip_w = ctw + 22
        chip_h = cth + 8
        name_max_w = max(40, player_max_w - chip_w - 10)
        player_name = _fit_text(draw, str(row["player"]), body_bold, name_max_w)
        pwt, pht = _text_size(draw, player_name, body_bold)
        text_y = top + (row_h - pht) // 2 - 2
        draw.text((player_x, text_y), player_name, font=body_bold, fill=theme["text"])

        chip_x = player_x + pwt + 10
        chip_y = top + (row_h - chip_h) // 2
        chip_fill, chip_text_color = COUNTRY_STYLES.get(country, ("#eef2f7", "#334155"))
        _rounded(draw, (chip_x, chip_y, chip_x + chip_w, chip_y + chip_h), 14, chip_fill)
        draw.text((chip_x + (chip_w - ctw) / 2, chip_y + (chip_h - cth) / 2 - 1), chip_text, font=chip_small, fill=chip_text_color)

        values = [
            (0.58, 0.66, f"{int(round(row['games']))}", body_font, theme["text"]),
            (0.66, 0.74, f"{int(round(row['goals']))}", body_font, theme["text"]),
            (0.74, 0.82, f"{int(round(row['assists']))}", body_font, theme["text"]),
            (0.82, 0.90, f"{int(round(row['points']))}", body_font, theme["text"]),
            (0.90, 1.00, f"{row[metric]:.2f}", body_bold, theme["accent"]),
        ]
        for start, end, text, font, color in values:
            tw, _ = _text_size(draw, text, font)
            right = table_x1 + int(table_w * end) - 14
            draw.text((right - tw, top + 28), text, font=font, fill=color)

    handle = "@floorballconnect"
    hw, hh = _text_size(draw, handle, chip_font)
    draw.text((WIDTH - PADDING - hw, HEIGHT - 44 - hh), handle, font=chip_font, fill=theme["text_muted"])

    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output)


def main():
    parser = argparse.ArgumentParser(description="Render top10 playoff scorers carousel slides")
    parser.add_argument("--csv", default="data/player_stats.csv")
    parser.add_argument("--season", default=None)
    parser.add_argument("--output-dir", default="social/output/top10-playoff-scorers-cross-league")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    output_dir = Path(args.output_dir)
    metrics = ["ppg", "gpg", "apg"]
    for idx, metric in enumerate(metrics, start=1):
        rows, season = load_top10(csv_path, metric, args.season)
        render_slide(rows, metric, season, output_dir / f"{idx}.png")
    print(f"Created slides in {output_dir}")


if __name__ == "__main__":
    main()
