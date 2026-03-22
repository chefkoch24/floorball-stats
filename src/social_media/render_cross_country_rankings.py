import argparse
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1080
HEIGHT = 1350
STORY_HEIGHT = 1920
PADDING = 72
STORY_SAFE_BOTTOM = 140
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

FONT = "/System/Library/Fonts/HelveticaNeue.ttc"

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
        value = candidate.rstrip() + "..."
        if _text_size(draw, value, font)[0] <= max_width:
            return value
    return text[:3]


def _column_center_x(table_x1: int, table_w: int, start: float, end: float) -> float:
    left = table_x1 + int(table_w * start)
    right = table_x1 + int(table_w * end)
    return (left + right) / 2


def _rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _format_decimal(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


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


def _parse_metadata_date(raw: str | None) -> datetime:
    if not raw:
        return datetime.min
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d")
    except ValueError:
        return datetime.min


def _metric_config(metric: str) -> dict:
    if metric == "pp":
        return {
            "title": "Top 10 Powerplay",
            "columns": {
                "team": (0.00, 0.59),
                "efficiency": (0.59, 0.75),
                "opportunities": (0.75, 0.88),
                "goals": (0.88, 1.00),
            },
            "labels": [("efficiency", "PP%"), ("opportunities", "PP"), ("goals", "PP G")],
        }
    if metric == "pk":
        return {
            "title": "Top 10 Penalty Kill",
            "columns": {
                "team": (0.00, 0.59),
                "efficiency": (0.59, 0.75),
                "opportunities": (0.75, 0.88),
                "goals": (0.88, 1.00),
            },
            "labels": [("efficiency", "PK%"), ("opportunities", "BP"), ("goals", "GA BP")],
        }
    return {
        "title": "Top 10 Penalty Minutes",
        "columns": {
            "team": (0.00, 0.43),
            "penalty_2": (0.43, 0.52),
            "penalty_2and2": (0.52, 0.61),
            "penalty_10_ms": (0.61, 0.75),
            "penalties": (0.75, 0.86),
            "penalties_per_game": (0.86, 0.97),
        },
        "labels": [
            ("penalty_2", "2'"),
            ("penalty_2and2", "2+2'"),
            ("penalty_10_ms", "10'+MS"),
            ("penalties", "Tot"),
            ("penalties_per_game", "P/G"),
        ],
    }


def load_entries(metric: str) -> list[dict]:
    entries = []
    for path in sorted(Path("content").glob("*25-26-regular-season/teams/*.md")):
        text = path.read_text(encoding="utf-8")
        category_match = re.search(r"^Category:\s*([^,]+)", text, re.M)
        team_match = re.search(r"^team:(.+)$", text, re.M)
        date_match = re.search(r"^Date:\s*(.+)$", text, re.M)
        if metric == "pp":
            eff_match = re.search(r"^powerplay_efficiency:\s*(.+)$", text, re.M)
            opp_match = re.search(r"^powerplay:\s*(.+)$", text, re.M)
            goals_match = re.search(r"^goals_in_powerplay:\s*(.+)$", text, re.M)
        elif metric == "pk":
            eff_match = re.search(r"^boxplay_efficiency:\s*(.+)$", text, re.M)
            opp_match = re.search(r"^boxplay:\s*(.+)$", text, re.M)
            goals_match = re.search(r"^goals_against_in_boxplay:\s*(.+)$", text, re.M)
        else:
            p2 = re.search(r"^penalty_2:\s*(.+)$", text, re.M)
            p22 = re.search(r"^penalty_2and2:\s*(.+)$", text, re.M)
            p10 = re.search(r"^penalty_10:\s*(.+)$", text, re.M)
            pms = re.search(r"^penalty_ms:\s*(.+)$", text, re.M)
            total = re.search(r"^penalties:\s*(.+)$", text, re.M)
            games = re.search(r"^games:\s*(.+)$", text, re.M)
            if not (category_match and team_match and p2 and p22 and p10 and pms and total and games):
                continue
            total_penalties = int(float(total.group(1).strip()))
            games_count = float(games.group(1).strip())
            entries.append(
                {
                    "country": _country_from_category(category_match.group(1).strip()),
                    "team": team_match.group(1).strip(),
                    "metadata_date": _parse_metadata_date(date_match.group(1).strip() if date_match else None),
                    "penalty_2": int(float(p2.group(1).strip())),
                    "penalty_2and2": int(float(p22.group(1).strip())),
                    "penalty_10": int(float(p10.group(1).strip())),
                    "penalty_ms": int(float(pms.group(1).strip())),
                    "penalties": total_penalties,
                    "penalties_per_game": (total_penalties / games_count) if games_count else 0.0,
                }
            )
            continue
        if not (category_match and team_match and eff_match and opp_match and goals_match):
            continue
        raw_eff = eff_match.group(1).strip()
        if raw_eff == "n.a.":
            continue
        entries.append(
            {
                "country": _country_from_category(category_match.group(1).strip()),
                "team": team_match.group(1).strip(),
                "metadata_date": _parse_metadata_date(date_match.group(1).strip() if date_match else None),
                "efficiency": float(raw_eff),
                "opportunities": int(float(opp_match.group(1).strip())),
                "goals": int(float(goals_match.group(1).strip())),
            }
        )
    deduped_entries: dict[tuple[str, str], dict] = {}
    for row in entries:
        key = (row["country"], row["team"].strip().lower())
        existing = deduped_entries.get(key)
        if existing is None or row["metadata_date"] >= existing["metadata_date"]:
            deduped_entries[key] = row
    entries = list(deduped_entries.values())
    if metric in {"pp", "pk"}:
        entries.sort(key=lambda row: (-row["efficiency"], -row["opportunities"], row["team"].lower()))
    else:
        entries.sort(
            key=lambda row: (
                -row["penalty_2"],
                -row["penalty_2and2"],
                -row["penalty_10"],
                -row["penalty_ms"],
                row["team"].lower(),
            )
        )
    top_entries = entries[:10]
    for idx, row in enumerate(top_entries, start=1):
        row["rank"] = idx
        row.pop("metadata_date", None)
    return top_entries


def render(entries: list[dict], output_path: str, metric: str, theme_name: str):
    image = render_image(entries, metric, theme_name)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def render_image(entries: list[dict], metric: str, theme_name: str, *, width: int = WIDTH, height: int = HEIGHT) -> Image.Image:
    theme = DARK_THEME if theme_name == "dark" else LIGHT_THEME
    config = _metric_config(metric)
    image = Image.new("RGB", (width, height), theme["bg"])
    draw = ImageDraw.Draw(image)

    title_font = _font(60, bold=True)
    sub_font = _font(24, bold=False)
    chip_font = _font(23, bold=True)
    head_font = _font(22, bold=True)
    body_font = _font(25, bold=False)
    body_bold = _font(25, bold=True)
    small_font = _font(21, bold=False)

    header_block_height = 72 + 50 + 82
    header_h = 56
    row_h = 95
    panel_height = 28 + header_h + row_h * len(entries) + 18
    total_block_height = header_block_height + panel_height
    available_height = height - STORY_SAFE_BOTTOM
    y = 68 if height <= HEIGHT else max(68, int((available_height - total_block_height) / 2))
    metric_title = config["title"]
    draw.text((PADDING, y), metric_title, font=title_font, fill=theme["brand"])
    y += 72
    draw.text((PADDING, y), "Regular season across countries", font=sub_font, fill=theme["text_muted"])
    y += 50

    chips = ["Cross-country", "Regular Season"]
    chip_x = PADDING
    for chip in chips:
        w, h = _text_size(draw, chip, chip_font)
        box = (chip_x, y, chip_x + w + 34, y + h + 20)
        _rounded(draw, box, 24, theme["surface"], outline=theme["line"])
        draw.text((chip_x + 17, y + 10), chip, font=chip_font, fill=theme["accent"])
        chip_x = box[2] + 14

    y += 82
    panel = (PADDING, y, width - PADDING, y + panel_height)
    _rounded(draw, panel, 26, theme["surface"], outline=theme["line"], width=2)
    x1, y1, x2, y2 = panel
    inner = 34
    table_x1 = x1 + inner
    table_x2 = x2 - inner
    table_y1 = y1 + 28
    table_w = table_x2 - table_x1

    _rounded(draw, (table_x1, table_y1, table_x2, table_y1 + header_h), 18, theme["surface_muted"])

    columns = config["columns"]

    head_color = "#a8bbd1" if theme_name == "dark" else "#334155"
    draw.text((table_x1 + 14, table_y1 + 16), "Team", font=head_font, fill=head_color)
    for key, label in config["labels"]:
        lw, _ = _text_size(draw, label, head_font)
        start, end = columns[key]
        if metric == "penalties":
            center_x = _column_center_x(table_x1, table_w, start, end)
            draw.text((center_x - lw / 2, table_y1 + 16), label, font=head_font, fill=head_color)
        else:
            right = table_x1 + int(table_w * end) - 14
            draw.text((right - lw, table_y1 + 16), label, font=head_font, fill=head_color)

    for idx, row in enumerate(entries, start=1):
        top = table_y1 + header_h + (idx - 1) * row_h
        bottom = top + row_h
        draw.line((table_x1, bottom, table_x2, bottom), fill=theme["line"], width=2)

        rank_box = (table_x1 + 10, top + 28, table_x1 + 48, top + 62)
        _rounded(draw, rank_box, 17, theme["surface_muted"])
        rank = str(row["rank"])
        rw, rh = _text_size(draw, rank, small_font)
        draw.text((rank_box[0] + 19 - rw / 2, rank_box[1] + 17 - rh / 2), rank, font=small_font, fill=theme["text_muted"])

        badge_x = table_x1 + 64
        badge_y = top + (row_h - 32) // 2
        badge_fill, badge_text = COUNTRY_STYLES.get(row["country"], ("#eef2f7", "#334155"))
        badge_box = (badge_x, badge_y, badge_x + 52, badge_y + 32)
        _rounded(draw, badge_box, 16, badge_fill)
        cw, ch = _text_size(draw, row["country"], small_font)
        draw.text((badge_x + 26 - cw / 2, badge_y + 16 - ch / 2), row["country"], font=small_font, fill=badge_text)

        team_x = badge_box[2] + 14
        team_max_width = 220 if metric == "penalties" else 390
        team_text = _fit_text(draw, row["team"], body_bold, team_max_width)
        team_h = _text_size(draw, team_text, body_bold)[1]
        team_y = top + (row_h - team_h) // 2 - 2
        draw.text((team_x, team_y), team_text, font=body_bold, fill=theme["text"])

        if metric in {"pp", "pk"}:
            value_specs = [
                ("efficiency", _format_decimal(row["efficiency"]), theme["accent"], body_bold),
                ("opportunities", str(row["opportunities"]), theme["text"], body_font),
                ("goals", str(row["goals"]), theme["text"], body_font),
            ]
        else:
            value_specs = [
                ("penalty_2", str(row["penalty_2"]), theme["accent"], body_bold),
                ("penalty_2and2", str(row["penalty_2and2"]), theme["text"], body_font),
                ("penalty_10_ms", f"{row['penalty_10']}+{row['penalty_ms']}", theme["text"], body_font),
                ("penalties", str(row["penalties"]), theme["text"], body_font),
                ("penalties_per_game", _format_decimal(row["penalties_per_game"]), theme["text"], body_font),
            ]

        for key, text_value, color, font in value_specs:
            tw, _ = _text_size(draw, text_value, font)
            start, end = columns[key]
            if metric == "penalties":
                center_x = _column_center_x(table_x1, table_w, start, end)
                draw.text((center_x - tw / 2, top + 28), text_value, font=font, fill=color)
            else:
                right = table_x1 + int(table_w * end) - 14
                draw.text((right - tw, top + 28), text_value, font=font, fill=color)

    handle = "@foorballconnect"
    hw, hh = _text_size(draw, handle, chip_font)
    draw.text((width - PADDING - hw, height - 44 - hh), handle, font=chip_font, fill=theme["text_muted"])
    return image


def render_image_rank_slots(
    entries: list[dict],
    metric: str,
    theme_name: str,
    *,
    visible_ranks: set[int],
    width: int = WIDTH,
    height: int = HEIGHT,
) -> Image.Image:
    theme = DARK_THEME if theme_name == "dark" else LIGHT_THEME
    config = _metric_config(metric)
    image = Image.new("RGB", (width, height), theme["bg"])
    draw = ImageDraw.Draw(image)

    title_font = _font(60, bold=True)
    sub_font = _font(24, bold=False)
    chip_font = _font(23, bold=True)
    head_font = _font(22, bold=True)
    body_font = _font(25, bold=False)
    body_bold = _font(25, bold=True)
    small_font = _font(21, bold=False)

    header_block_height = 72 + 50 + 82
    header_h = 56
    row_h = 95
    panel_height = 28 + header_h + row_h * len(entries) + 18
    total_block_height = header_block_height + panel_height
    available_height = height - STORY_SAFE_BOTTOM
    y = 68 if height <= HEIGHT else max(68, int((available_height - total_block_height) / 2))
    metric_title = config["title"]
    draw.text((PADDING, y), metric_title, font=title_font, fill=theme["brand"])
    y += 72
    draw.text((PADDING, y), "Regular season across countries", font=sub_font, fill=theme["text_muted"])
    y += 50

    chips = ["Cross-country", "Regular Season"]
    chip_x = PADDING
    for chip in chips:
        w, h = _text_size(draw, chip, chip_font)
        box = (chip_x, y, chip_x + w + 34, y + h + 20)
        _rounded(draw, box, 24, theme["surface"], outline=theme["line"])
        draw.text((chip_x + 17, y + 10), chip, font=chip_font, fill=theme["accent"])
        chip_x = box[2] + 14

    y += 82
    panel = (PADDING, y, width - PADDING, y + panel_height)
    _rounded(draw, panel, 26, theme["surface"], outline=theme["line"], width=2)
    x1, y1, x2, y2 = panel
    inner = 34
    table_x1 = x1 + inner
    table_x2 = x2 - inner
    table_y1 = y1 + 28
    table_w = table_x2 - table_x1

    _rounded(draw, (table_x1, table_y1, table_x2, table_y1 + header_h), 18, theme["surface_muted"])

    columns = config["columns"]

    head_color = "#a8bbd1" if theme_name == "dark" else "#334155"
    draw.text((table_x1 + 14, table_y1 + 16), "Team", font=head_font, fill=head_color)
    for key, label in config["labels"]:
        lw, _ = _text_size(draw, label, head_font)
        start, end = columns[key]
        if metric == "penalties":
            center_x = _column_center_x(table_x1, table_w, start, end)
            draw.text((center_x - lw / 2, table_y1 + 16), label, font=head_font, fill=head_color)
        else:
            right = table_x1 + int(table_w * end) - 14
            draw.text((right - lw, table_y1 + 16), label, font=head_font, fill=head_color)

    rank_sorted = sorted(entries, key=lambda row: row["rank"])
    for idx, row in enumerate(rank_sorted, start=1):
        top = table_y1 + header_h + (idx - 1) * row_h
        bottom = top + row_h
        draw.line((table_x1, bottom, table_x2, bottom), fill=theme["line"], width=2)

        rank_box = (table_x1 + 10, top + 28, table_x1 + 48, top + 62)
        _rounded(draw, rank_box, 17, theme["surface_muted"])
        rank = str(row["rank"])
        rw, rh = _text_size(draw, rank, small_font)
        draw.text((rank_box[0] + 19 - rw / 2, rank_box[1] + 17 - rh / 2), rank, font=small_font, fill=theme["text_muted"])

        if row["rank"] not in visible_ranks:
            continue

        badge_x = table_x1 + 64
        badge_y = top + (row_h - 32) // 2
        badge_fill, badge_text = COUNTRY_STYLES.get(row["country"], ("#eef2f7", "#334155"))
        badge_box = (badge_x, badge_y, badge_x + 52, badge_y + 32)
        _rounded(draw, badge_box, 16, badge_fill)
        cw, ch = _text_size(draw, row["country"], small_font)
        draw.text((badge_x + 26 - cw / 2, badge_y + 16 - ch / 2), row["country"], font=small_font, fill=badge_text)

        team_x = badge_box[2] + 14
        team_max_width = 220 if metric == "penalties" else 390
        team_text = _fit_text(draw, row["team"], body_bold, team_max_width)
        team_h = _text_size(draw, team_text, body_bold)[1]
        team_y = top + (row_h - team_h) // 2 - 2
        draw.text((team_x, team_y), team_text, font=body_bold, fill=theme["text"])

        if metric in {"pp", "pk"}:
            value_specs = [
                ("efficiency", _format_decimal(row["efficiency"]), theme["accent"], body_bold),
                ("opportunities", str(row["opportunities"]), theme["text"], body_font),
                ("goals", str(row["goals"]), theme["text"], body_font),
            ]
        else:
            value_specs = [
                ("penalty_2", str(row["penalty_2"]), theme["accent"], body_bold),
                ("penalty_2and2", str(row["penalty_2and2"]), theme["text"], body_font),
                ("penalty_10_ms", f"{row['penalty_10']}+{row['penalty_ms']}", theme["text"], body_font),
                ("penalties", str(row["penalties"]), theme["text"], body_font),
                ("penalties_per_game", _format_decimal(row["penalties_per_game"]), theme["text"], body_font),
            ]

        for key, text_value, color, font in value_specs:
            tw, _ = _text_size(draw, text_value, font)
            start, end = columns[key]
            if metric == "penalties":
                center_x = _column_center_x(table_x1, table_w, start, end)
                draw.text((center_x - tw / 2, top + 28), text_value, font=font, fill=color)
            else:
                right = table_x1 + int(table_w * end) - 14
                draw.text((right - tw, top + 28), text_value, font=font, fill=color)

    handle = "@foorballconnect"
    hw, hh = _text_size(draw, handle, chip_font)
    draw.text((width - PADDING - hw, height - 44 - hh), handle, font=chip_font, fill=theme["text_muted"])
    return image


def render_gif(entries: list[dict], output_path: str, metric: str, theme_name: str) -> None:
    frames = []
    countdown_entries = list(reversed(entries))
    for count in range(1, len(countdown_entries) + 1):
        frames.append(
            render_image(
                countdown_entries[:count],
                metric,
                theme_name,
                width=WIDTH,
                height=STORY_HEIGHT,
            ).convert("P", palette=Image.ADAPTIVE)
        )
    if frames:
        final_frame = render_image(
            entries,
            metric,
            theme_name,
            width=WIDTH,
            height=STORY_HEIGHT,
        ).convert("P", palette=Image.ADAPTIVE)
        frames.append(final_frame)
        frames.append(final_frame.copy())
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=[350] * max(len(frames) - 2, 0) + [900, 900] if len(frames) >= 3 else 700,
        loop=0,
        optimize=False,
    )


def render_gif_fixed_slots(entries: list[dict], output_path: str, metric: str, theme_name: str) -> None:
    frames = []
    max_rank = max(row["rank"] for row in entries)
    for start_rank in range(max_rank, 0, -1):
        visible = set(range(start_rank, max_rank + 1))
        frames.append(
            render_image_rank_slots(
                entries,
                metric,
                theme_name,
                visible_ranks=visible,
                width=WIDTH,
                height=STORY_HEIGHT,
            ).convert("P", palette=Image.ADAPTIVE)
        )
    if frames:
        final_frame = render_image(
            entries,
            metric,
            theme_name,
            width=WIDTH,
            height=STORY_HEIGHT,
        ).convert("P", palette=Image.ADAPTIVE)
        frames.append(final_frame)
        frames.append(final_frame.copy())
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=[350] * max(len(frames) - 2, 0) + [900, 900] if len(frames) >= 3 else 700,
        loop=0,
        optimize=False,
    )


def _require_ffmpeg() -> str:
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg is required for MP4 export but was not found on PATH.")
    return ffmpeg_path


def _encode_frames_to_mp4(frame_dir: Path, output_path: str) -> None:
    ffmpeg_path = _require_ffmpeg()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
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
        str(output),
    ]
    subprocess.run(command, check=True)


def render_mp4(entries: list[dict], output_path: str, metric: str, theme_name: str) -> None:
    countdown_entries = list(reversed(entries))
    with tempfile.TemporaryDirectory(prefix="social-video-") as tmp_dir:
        frame_dir = Path(tmp_dir)
        frame_index = 1
        for count in range(1, len(countdown_entries) + 1):
            frame = render_image(
                countdown_entries[:count],
                metric,
                theme_name,
                width=WIDTH,
                height=STORY_HEIGHT,
            )
            repeats = VIDEO_STEP_REPEATS if count < len(countdown_entries) else VIDEO_FINAL_REPEATS
            for _ in range(repeats):
                frame.save(frame_dir / f"frame-{frame_index:03d}.png")
                frame_index += 1

        final_frame = render_image(
            entries,
            metric,
            theme_name,
            width=WIDTH,
            height=STORY_HEIGHT,
        )
        for _ in range(VIDEO_FINAL_REPEATS):
            final_frame.save(frame_dir / f"frame-{frame_index:03d}.png")
            frame_index += 1

        _encode_frames_to_mp4(frame_dir, output_path)


def render_mp4_fixed_slots(entries: list[dict], output_path: str, metric: str, theme_name: str) -> None:
    max_rank = max(row["rank"] for row in entries)
    with tempfile.TemporaryDirectory(prefix="social-video-") as tmp_dir:
        frame_dir = Path(tmp_dir)
        frame_index = 1
        for start_rank in range(max_rank, 0, -1):
            visible = set(range(start_rank, max_rank + 1))
            frame = render_image_rank_slots(
                entries,
                metric,
                theme_name,
                visible_ranks=visible,
                width=WIDTH,
                height=STORY_HEIGHT,
            )
            repeats = VIDEO_STEP_REPEATS if start_rank > 1 else VIDEO_FINAL_REPEATS
            for _ in range(repeats):
                frame.save(frame_dir / f"frame-{frame_index:03d}.png")
                frame_index += 1

        final_frame = render_image(
            entries,
            metric,
            theme_name,
            width=WIDTH,
            height=STORY_HEIGHT,
        )
        for _ in range(VIDEO_FINAL_REPEATS):
            final_frame.save(frame_dir / f"frame-{frame_index:03d}.png")
            frame_index += 1

        _encode_frames_to_mp4(frame_dir, output_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--metric", choices=["pp", "pk", "penalties"], default="pp")
    parser.add_argument("--theme", choices=["light", "dark"], default="light")
    args = parser.parse_args()
    render(load_entries(args.metric), args.output_path, args.metric, args.theme)


if __name__ == "__main__":
    main()
