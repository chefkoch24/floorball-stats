import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


WIDTH = 1080
HEIGHT = 1920
PADDING = 72
VIDEO_FPS = 12
VIDEO_STEP_REPEATS = 12
VIDEO_FINAL_REPEATS = 24

THEME = {
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
    "GER": ("#f4efe2", "#8a6a18"),
    "SWE": ("#e8f1ff", "#1f5ea8"),
    "FIN": ("#ebf3ff", "#225ea8"),
    "SUI": ("#fdecec", "#b42318"),
    "CZE": ("#eef4ff", "#3056a0"),
    "LAT": ("#fdeff1", "#a52a4a"),
    "SVK": ("#eef5ff", "#335ca8"),
}

LEAGUE_FILES = [
    ("GER", Path("data/data_25-26_regular_season.csv")),
    ("SWE", Path("data/data_se-25-26_regular_season.csv")),
    ("FIN", Path("data/data_fi-25-26_regular_season.csv")),
    ("CZE", Path("data/data_cz-25-26_regular_season.csv")),
    ("SUI", Path("data/data_ch-25-26_regular_season.csv")),
    ("SVK", Path("data/data_sk-25-26_regular_season.csv")),
    ("LAT", Path("data/data_lv-25-26_regular_season.csv")),
]

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


def _parse_sortkey(value: str):
    try:
        period_str, clock = str(value).split("-", 1)
        mm_str, ss_str = clock.split(":", 1)
        return int(period_str), int(mm_str), int(ss_str)
    except Exception:
        return 0, 0, 0


def _league_entries() -> list[dict]:
    rows = []
    for league, csv_path in LEAGUE_FILES:
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        goals = df[df["event_type"] == "goal"].copy()
        goals["period"] = pd.to_numeric(goals.get("period"), errors="coerce").fillna(0).astype(int)
        p1 = int((goals["period"] == 1).sum())
        p2 = int((goals["period"] == 2).sum())
        p3 = int((goals["period"] == 3).sum())
        p4 = int((goals["period"] == 4).sum())
        total_goal_events = p1 + p2 + p3 + p4
        if total_goal_events == 0:
            continue

        total_goals = 0
        games = 0
        for _, game_df in df.groupby("game_id"):
            games += 1
            game_goals = game_df[game_df["event_type"] == "goal"].copy()
            if {"home_goals", "guest_goals"}.issubset(game_goals.columns):
                game_goals = game_goals.dropna(subset=["home_goals", "guest_goals"], how="any")
            if game_goals.empty:
                continue
            game_goals = game_goals.assign(_sort=game_goals["sortkey"].map(_parse_sortkey)).sort_values("_sort")
            last = game_goals.iloc[-1]
            total_goals += int(last["home_goals"]) + int(last["guest_goals"])

        if games == 0:
            continue

        rows.append(
            {
                "country": league,
                "team": league,
                "gpg": round(total_goals / games, 2),
                "p1": round(100 * p1 / total_goal_events, 1),
                "p2": round(100 * p2 / total_goal_events, 1),
                "p3": round(100 * p3 / total_goal_events, 1),
                "ot": round(100 * p4 / total_goal_events, 1),
            }
        )

    rows.sort(key=lambda x: (-x["gpg"], -x["p3"], x["team"]))
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows


def _render_frame(entries: list[dict], visible_ranks: set[int]) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), THEME["bg"])
    draw = ImageDraw.Draw(image)

    title_font = _font(58, bold=True)
    sub_font = _font(24)
    head_font = _font(22, bold=True)
    body_font = _font(26)
    body_bold = _font(26, bold=True)
    small_font = _font(21)

    y = 72
    draw.text((PADDING, y), "Regular Season Goal Trends", font=title_font, fill=THEME["brand"])
    y += 72
    draw.text((PADDING, y), "Goals per game + period distribution by league", font=sub_font, fill=THEME["text_muted"])
    y += 58

    chips = ["Cross-country", "Regular Season", "All leagues"]
    chip_x = PADDING
    chip_font = _font(22, bold=True)
    for chip in chips:
        w, h = _text_size(draw, chip, chip_font)
        box = (chip_x, y, chip_x + w + 30, y + h + 16)
        _rounded(draw, box, 22, THEME["surface"], outline=THEME["line"])
        draw.text((chip_x + 15, y + 8), chip, font=chip_font, fill=THEME["accent"])
        chip_x = box[2] + 12

    y += 74
    header_h = 54
    row_h = 104
    panel_h = 24 + header_h + row_h * len(entries) + 16
    panel = (PADDING, y, WIDTH - PADDING, y + panel_h)
    _rounded(draw, panel, 24, THEME["surface"], outline=THEME["line"], width=2)
    x1, y1, x2, _ = panel
    table_x1 = x1 + 28
    table_x2 = x2 - 28
    table_y1 = y1 + 24
    table_w = table_x2 - table_x1
    _rounded(draw, (table_x1, table_y1, table_x2, table_y1 + header_h), 16, THEME["surface_muted"])

    cols = {
        "team": (0.00, 0.26),
        "gpg": (0.26, 0.42),
        "p1": (0.42, 0.56),
        "p2": (0.56, 0.70),
        "p3": (0.70, 0.84),
        "ot": (0.84, 1.00),
    }
    labels = [("gpg", "GPG"), ("p1", "P1%"), ("p2", "P2%"), ("p3", "P3%"), ("ot", "OT%")]
    draw.text((table_x1 + 14, table_y1 + 14), "League", font=head_font, fill="#a8bbd1")
    for key, label in labels:
        _, end = cols[key]
        right = table_x1 + int(table_w * end) - 12
        lw, _ = _text_size(draw, label, head_font)
        draw.text((right - lw, table_y1 + 14), label, font=head_font, fill="#a8bbd1")

    rank_sorted = sorted(entries, key=lambda r: r["rank"])
    for idx, row in enumerate(rank_sorted, start=1):
        top = table_y1 + header_h + (idx - 1) * row_h
        bottom = top + row_h
        draw.line((table_x1, bottom, table_x2, bottom), fill=THEME["line"], width=2)

        rank_box = (table_x1 + 8, top + 34, table_x1 + 44, top + 68)
        _rounded(draw, rank_box, 17, THEME["surface_muted"])
        rank_txt = str(row["rank"])
        rw, rh = _text_size(draw, rank_txt, small_font)
        draw.text((rank_box[0] + 18 - rw / 2, rank_box[1] + 16 - rh / 2), rank_txt, font=small_font, fill=THEME["text_muted"])

        if row["rank"] not in visible_ranks:
            continue

        badge_x = table_x1 + 56
        badge_y = top + 36
        badge_fill, badge_text = COUNTRY_STYLES.get(row["country"], ("#eef2f7", "#334155"))
        badge_box = (badge_x, badge_y, badge_x + 56, badge_y + 32)
        _rounded(draw, badge_box, 16, badge_fill)
        cw, ch = _text_size(draw, row["country"], small_font)
        draw.text((badge_x + 28 - cw / 2, badge_y + 16 - ch / 2), row["country"], font=small_font, fill=badge_text)

        draw.text((badge_box[2] + 12, top + 34), row["team"], font=body_bold, fill=THEME["text"])

        for key in ["gpg", "p1", "p2", "p3", "ot"]:
            _, end = cols[key]
            right = table_x1 + int(table_w * end) - 12
            value = f"{row[key]:.2f}" if key == "gpg" else f"{row[key]:.1f}"
            tw, _ = _text_size(draw, value, body_font)
            draw.text((right - tw, top + 34), value, font=body_font, fill=THEME["accent"] if key in {"gpg", "p3"} else THEME["text"])

    handle = "@floorballconnect"
    hw, hh = _text_size(draw, handle, _font(22, bold=True))
    draw.text((WIDTH - PADDING - hw, HEIGHT - 44 - hh), handle, font=_font(22, bold=True), fill=THEME["text_muted"])
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


def render_goals_table_video(output_path: Path) -> None:
    entries = _league_entries()
    if not entries:
        raise RuntimeError("No league data found")
    max_rank = max(e["rank"] for e in entries)
    with tempfile.TemporaryDirectory(prefix="social-goals-video-") as tmp_dir:
        frame_dir = Path(tmp_dir)
        frame_index = 1
        for start_rank in range(max_rank, 0, -1):
            visible = set(range(start_rank, max_rank + 1))
            frame = _render_frame(entries, visible)
            repeats = VIDEO_STEP_REPEATS if start_rank > 1 else VIDEO_FINAL_REPEATS
            for _ in range(repeats):
                frame.save(frame_dir / f"frame-{frame_index:03d}.png")
                frame_index += 1
        final_frame = _render_frame(entries, set(range(1, max_rank + 1)))
        for _ in range(VIDEO_FINAL_REPEATS):
            final_frame.save(frame_dir / f"frame-{frame_index:03d}.png")
            frame_index += 1
        _encode_frames_to_mp4(frame_dir, output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-path",
        default="output/social/top7-goals-regular-season-cross-country-1080x1920.mp4",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    render_goals_table_video(Path(args.output_path))
    print(f"Created: {args.output_path}")


if __name__ == "__main__":
    main()
