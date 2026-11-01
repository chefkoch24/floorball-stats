"""Files for the player comparison page: one slim search index and one small file per player.

Runs at build time on the published player pages, like ``team_versus``. The page
(``templates/player_compare.html``) is a single static page; it searches
``compare-players/index.json`` and loads ``compare-players/<player uid>.json`` for each
chosen player, so the 4,600 players are not in the page and a comparison costs two
requests of about 1 KB. The shapes are built in ``src/player_compare.py``.

The files are written when Pelican writes the articles, after every
``article_generator_finalized`` handler ran, so the clutch and goal-share facts that
``insights`` attaches to the player pages are already there whatever the plugin order.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from pelican import signals

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import player_compare as pc  # noqa: E402

OUTPUT_DIR = "compare-players"
META_KEYS = (
    "player", "title", "player_uid", "slug", "team", "league", "season_count", "current_season",
    *(f"{scope}_{key}" for scope in ("current", "career") for key in pc.COUNT_KEYS),
)


def _value(article, key: str, default=None):
    value = getattr(article, key, default)
    if isinstance(value, list):
        value = value[0] if value else default
    return value


def player_files(articles) -> dict[str, dict]:
    """File name -> JSON payload for the index and every player page in ``articles``."""
    rows, files = [], {}
    for article in articles:
        if _value(article, "type") != "player":
            continue
        meta = {key: _value(article, key) for key in META_KEYS}
        payload = pc.player_payload(
            meta,
            clutch=_value(article, "clutch"),
            trends=_value(article, "player_trends"),
            team_url=_value(article, "team_page_url") or "",
        )
        if not payload["uid"] or not payload["name"]:
            continue
        rows.append(pc.index_row(meta))
        files[f"{payload['uid']}.json"] = payload
    files["index.json"] = pc.index_payload(rows)
    return files


def write(generator, writer) -> None:
    articles = getattr(generator, "articles", None)
    if not articles:
        return
    files = player_files(articles)
    folder = os.path.join(generator.output_path, OUTPUT_DIR)
    os.makedirs(folder, exist_ok=True)
    for name, payload in files.items():
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))


def register() -> None:
    signals.article_writer_finalized.connect(write)
