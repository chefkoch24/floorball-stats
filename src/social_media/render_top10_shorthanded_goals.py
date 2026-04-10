import argparse
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1080
HEIGHT = 1920
PADDING = 72
VIDEO_FPS = 12
VIDEO_STEP_REPEATS = 12
VIDEO_FINAL_REPEATS = 24

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

DARK_THEME = {
    "bg": "#0b1220",
    "surface": "#121b2d",
    "surface_muted": "#1a2436",
    "text": "#e6edf7",
    "text_muted": "#9fb0c7",
    "line": "#2a3950",
    "brand": "#0071e2",
    "accent": "#7fc2ff",
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

FONT = "/System/Library/Fonts/HelveticaNeue.ttc"


def _font(size: int, bold: bool = False):
    try:
        return ImageFont.truetype(FONT, size=size, index=1 if bold else 0)
    except OSError:
        return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def _rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    text = text.strip()
    if _text_size(draw, text, font)[0] <= max_width:
        return text
    candidate = text
    while len(candidate) > 3:
        candidate = candidate[:-1]
        clipped = candidate.rstrip() + "..."
        if _text_size(draw, clipped, font)[0] <= max_width:
            return clipped
    return text[:3]


def _country_from_category(category: str) -> str:
    if category.startswith("se-"):
        return "SE"
    if category.startswith("fi-"):
        return "FI"
    if category.startswith("ch-"):
        return "CH"
    if category.startswith("cz-"):
        return "CZ"
    if category.startswith("lv-"):
        return "LV"
    if category.startswith("sk-"):
        return "SK"
    return "DE"


def _extract_value(text: str, key: str):
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.M)
    return match.group(1).strip() if match else None


def _to_float(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    value = value.strip()
    if value == "n.a.":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _parse_date(value: str | None) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return datetime.min


def load_entries() -> list[dict]:
    raw_entries = []
    for path in sorted(Path("content").glob("*25-26-regular-season/teams/*.md")):
        text = path.read_text(encoding="utf-8")
        category = _extract_value(text, "Category")
        team = _extract_value(text, "team")
        date = _extract_value(text, "Date")
        shg = _to_float(_extract_value(text, "goals_in_boxplay"), 0.0)
        boxplay = _to_float(_extract_value(text, "boxplay"), 0.0)
        if not category or not team or boxplay <= 0:
            continue
        raw_entries.append(
            {
                "country": _country_from_category(category.split(",")[0].strip()),
                "team": team.strip(),
                "date": _parse_date(date),
                "shg": int(round(shg)),
                "pk": int(round(boxplay)),
                "g_per_pk": shg / boxplay if boxplay else 0.0,
            }
        )

    deduped: dict[tuple[str, str], dict] = {}
    for row in raw_entries:
        key = (row["country"], row["team"].lower())
        existing = deduped.get(key)
        if existing is None or row["date"] >= existing["date"]:
            deduped[key] = row

    entries = list(deduped.values())
    entries.sort(key=lambda row: (-row["shg"], -row["g_per_pk"], -row["pk"], row["team"].lower()))
    top = entries[:10]
    for idx, row in enumerate(top, start=1):
        row["rank"] = idx
        row.pop("date", None)
    return top


def render_frame(
    entries: list[dict],
    visible_ranks: set[int],
    theme: dict[str, str],
    headline: str,
    subheadline: str,
) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), theme["bg"])
    draw = ImageDraw.Draw(image)

    title_font = _font(56, bold=True)
    sub_font = _font(24)
    chip_font = _font(22, bold=True)
    head_font = _font(22, bold=True)
    body_font = _font(24)
    body_bold = _font(24, bold=True)
    small_font = _font(21)

    header_block_h = 72 + 50 + 74
    header_h = 54
    row_h = 90
    panel_h = 24 + header_h + row_h * len(entries) + 16
    total_block_h = header_block_h + panel_h
    y = max(64, int((HEIGHT - total_block_h) / 2))

    draw.text((PADDING, y), headline, font=title_font, fill=theme["brand"])
    y += 72
    draw.text((PADDING, y), subheadline, font=sub_font, fill=theme["text_muted"])
    y += 50

    chips = ["Cross-country", "Regular Season", "Top 10"]
    chip_x = PADDING
    for chip in chips:
        w, h = _text_size(draw, chip, chip_font)
        box = (chip_x, y, chip_x + w + 30, y + h + 16)
        _rounded(draw, box, 22, theme["surface"], outline=theme["line"])
        draw.text((chip_x + 15, y + 8), chip, font=chip_font, fill=theme["accent"])
        chip_x = box[2] + 12

    y += 74
    panel = (PADDING, y, WIDTH - PADDING, y + panel_h)
    _rounded(draw, panel, 24, theme["surface"], outline=theme["line"], width=2)
    x1, y1, x2, _ = panel
    table_x1 = x1 + 28
    table_x2 = x2 - 28
    table_y1 = y1 + 24
    table_w = table_x2 - table_x1
    _rounded(draw, (table_x1, table_y1, table_x2, table_y1 + header_h), 16, theme["surface_muted"])

    cols = {
        "team": (0.00, 0.58),
        "shg": (0.58, 0.73),
        "pk": (0.73, 0.86),
        "g_per_pk": (0.86, 1.00),
    }
    labels = [("shg", "SHG"), ("pk", "PK"), ("g_per_pk", "G/PK")]

    head_color = "#a8bbd1" if theme is DARK_THEME else "#334155"
    draw.text((table_x1 + 14, table_y1 + 14), "Team", font=head_font, fill=head_color)
    for key, label in labels:
        _, end = cols[key]
        right = table_x1 + int(table_w * end) - 12
        lw, _ = _text_size(draw, label, head_font)
        draw.text((right - lw, table_y1 + 14), label, font=head_font, fill=head_color)

    rank_sorted = sorted(entries, key=lambda r: r["rank"])
    for idx, row in enumerate(rank_sorted, start=1):
        top = table_y1 + header_h + (idx - 1) * row_h
        bottom = top + row_h
        draw.line((table_x1, bottom, table_x2, bottom), fill=theme["line"], width=2)

        rank_box = (table_x1 + 8, top + 28, table_x1 + 44, top + 62)
        _rounded(draw, rank_box, 17, theme["surface_muted"])
        rank_text = str(row["rank"])
        rw, rh = _text_size(draw, rank_text, small_font)
        draw.text((rank_box[0] + 18 - rw / 2, rank_box[1] + 16 - rh / 2), rank_text, font=small_font, fill=theme["text_muted"])

        if row["rank"] not in visible_ranks:
            continue

        badge_x = table_x1 + 56
        badge_y = top + 30
        badge_fill, badge_text = COUNTRY_STYLES.get(row["country"], ("#eef2f7", "#334155"))
        badge_box = (badge_x, badge_y, badge_x + 52, badge_y + 32)
        _rounded(draw, badge_box, 16, badge_fill)
        cw, ch = _text_size(draw, row["country"], small_font)
        draw.text((badge_x + 26 - cw / 2, badge_y + 16 - ch / 2), row["country"], font=small_font, fill=badge_text)

        team_x = badge_box[2] + 12
        team_text = _fit_text(draw, row["team"], body_bold, max_width=330)
        tw, th = _text_size(draw, team_text, body_bold)
        team_y = badge_y + (32 - th) / 2
        draw.text((team_x, team_y), team_text, font=body_bold, fill=theme["text"])

        values = {
            "shg": str(row["shg"]),
            "pk": str(row["pk"]),
            "g_per_pk": f"{row['g_per_pk']:.2f}",
        }
        for key, value in values.items():
            _, end = cols[key]
            right = table_x1 + int(table_w * end) - 12
            vw, _ = _text_size(draw, value, body_font)
            color = theme["accent"] if key in {"shg", "g_per_pk"} else theme["text"]
            draw.text((right - vw, top + 30), value, font=body_font, fill=color)

    handle = "@floorballconnect"
    hw, hh = _text_size(draw, handle, chip_font)
    draw.text((WIDTH - PADDING - hw, HEIGHT - 44 - hh), handle, font=chip_font, fill=theme["text_muted"])
    return image


def _encode_frames_to_mp4(frame_dir: Path, output_path: Path) -> None:
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg not found on PATH")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_path,
        "-y",
        "-framerate",
        str(VIDEO_FPS),
        "-i",
        str(frame_dir / "frame-%03d.png"),
        "-movflags",
        "+faststart",
        "-pix_fmt",
        "yuv420p",
        "-vf",
        "scale=1080:1920:flags=lanczos",
        str(output_path),
    ]
    subprocess.run(command, check=True)


def render_video(output_path: Path, theme_name: str, headline: str) -> None:
    entries = load_entries()
    if not entries:
        raise RuntimeError("No team entries found")
    top10_avg = sum(row["g_per_pk"] for row in entries) / len(entries)
    subheadline = f"SHG ranking + avg goals per PK | Top10 avg G/PK: {top10_avg:.2f}"
    theme = DARK_THEME if theme_name == "dark" else LIGHT_THEME
    max_rank = max(row["rank"] for row in entries)
    with tempfile.TemporaryDirectory(prefix="social-topshg-video-") as tmp_dir:
        frame_dir = Path(tmp_dir)
        frame_idx = 1
        for start_rank in range(max_rank, 0, -1):
            visible = set(range(start_rank, max_rank + 1))
            frame = render_frame(entries, visible, theme, headline, subheadline)
            repeats = VIDEO_STEP_REPEATS if start_rank > 1 else VIDEO_FINAL_REPEATS
            for _ in range(repeats):
                frame.save(frame_dir / f"frame-{frame_idx:03d}.png")
                frame_idx += 1
        final_frame = render_frame(entries, set(range(1, max_rank + 1)), theme, headline, subheadline)
        for _ in range(VIDEO_FINAL_REPEATS):
            final_frame.save(frame_dir / f"frame-{frame_idx:03d}.png")
            frame_idx += 1
        _encode_frames_to_mp4(frame_dir, output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-path",
        default="social/output/top10-shorthanded-goals-cross-league-regular-season-1080x1920.mp4",
    )
    parser.add_argument("--theme", choices=["light", "dark"], default="dark")
    parser.add_argument("--headline", default="Top 10 Shorthanded Goals")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    render_video(Path(args.output_path), args.theme, args.headline)
    print(f"Created: {args.output_path}")


if __name__ == "__main__":
    main()
