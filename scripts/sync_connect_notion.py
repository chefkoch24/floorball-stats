"""Sync floorballconnect.com content from the Notion databases into connect/data.

Notion stays the editing tool: records are edited there and reviews arrive there from the
Tally forms. This script reads each collection's database through the Notion API and
writes connect/data/<collection>.json in the same format as the Softr import, page body
included as HTML. Notion file links expire after an hour, so images are downloaded into
connect/content/images like the import does.

Configuration:
- NOTION_TOKEN: an internal integration token; share the databases with the integration.
- connect/notion.json: the database id per collection, and for sticks and blades the
  review database and the relation property that links a review to its stick or blade:
  {"sticks": {"database": "<id>", "reviews": {"database": "<id>", "relation": "Stick"}}, ...}

Collections missing from notion.json keep their current data file. Without NOTION_TOKEN
the script exits without changes, so builds without the secret use the committed data.

Usage: python scripts/sync_connect_notion.py [--only sticks,blades]
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "connect"))
sys.path.append(str(ROOT / "scripts"))
import connect_content as cc  # noqa: E402
from import_connect_softr import DATA_DIR, review_fields, save_image  # noqa: E402

API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
CONFIG = ROOT / "connect" / "notion.json"


class Notion:
    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION, "Content-Type": "application/json"})

    def _request(self, method: str, path: str, **kwargs) -> dict:
        for attempt in range(5):
            response = self.session.request(method, f"{API}{path}", timeout=60, **kwargs)
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(float(response.headers.get("Retry-After", 2 ** attempt)))
                continue
            response.raise_for_status()
            return response.json()
        response.raise_for_status()
        return {}

    def query(self, database: str) -> list[dict]:
        rows, cursor = [], None
        while True:
            body = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
            data = self._request("POST", f"/databases/{database}/query", json=body)
            rows.extend(data["results"])
            if not data.get("has_more"):
                return rows
            cursor = data["next_cursor"]

    def children(self, block: str) -> list[dict]:
        rows, cursor = [], None
        while True:
            data = self._request("GET", f"/blocks/{block}/children", params={"page_size": 100, **({"start_cursor": cursor} if cursor else {})})
            rows.extend(data["results"])
            if not data.get("has_more"):
                return rows
            cursor = data["next_cursor"]


def rich_text(parts: list[dict]) -> str:
    out = []
    for part in parts:
        text = html.escape(part.get("plain_text", "")).replace("\n", "<br>")
        notes = part.get("annotations", {})
        if notes.get("code"):
            text = f"<code>{text}</code>"
        if notes.get("bold"):
            text = f"<strong>{text}</strong>"
        if notes.get("italic"):
            text = f"<em>{text}</em>"
        if notes.get("strikethrough"):
            text = f"<s>{text}</s>"
        link = part.get("href")
        if link:
            text = f'<a href="{html.escape(link)}">{text}</a>'
        out.append(text)
    return "".join(out)


def plain(parts: list[dict]) -> str:
    return "".join(part.get("plain_text", "") for part in parts).strip()


def file_urls(files: list[dict]) -> list[str]:
    return [entry.get("file", entry.get("external", {})).get("url", "") for entry in files if entry]


def property_value(prop: dict):
    """A Notion property as the simple value connect_content reads."""
    kind = prop.get("type")
    value = prop.get(kind)
    if kind in ("title", "rich_text"):
        return plain(value)
    if kind == "number":
        return value
    if kind in ("select", "status"):
        return value["name"] if value else None
    if kind == "multi_select":
        return [entry["name"] for entry in value]
    if kind in ("url", "email", "phone_number"):
        return value
    if kind == "checkbox":
        return "yes" if value else "no"
    if kind == "date":
        return value["start"] if value else None
    if kind == "files":
        return file_urls(value)
    if kind == "formula":
        return value.get(value.get("type"))
    if kind == "rollup":
        inner = value.get(value.get("type"))
        return inner if not isinstance(inner, list) else [property_value(entry) for entry in inner]
    if kind == "relation":
        return [entry["id"] for entry in value]
    return None


def blocks_html(notion: Notion, block_id: str, session: requests.Session, image_prefix: str) -> str:
    """The page body as HTML: headings, paragraphs, lists, quotes, dividers, images, toggles."""
    out, open_list = [], None
    for block in notion.children(block_id):
        kind = block["type"]
        data = block.get(kind, {})
        list_kind = "ul" if kind == "bulleted_list_item" else ("ol" if kind == "numbered_list_item" else None)
        if open_list and list_kind != open_list:
            out.append(f"</{open_list}>")
            open_list = None
        if list_kind and not open_list:
            out.append(f"<{list_kind}>")
            open_list = list_kind
        text = rich_text(data.get("rich_text", []))
        nested = blocks_html(notion, block["id"], session, image_prefix) if block.get("has_children") and kind not in ("child_page", "child_database") else ""
        if list_kind:
            out.append(f"<li>{text}{nested}</li>")
        elif kind == "paragraph":
            out.append(f"<p>{text}</p>" if text else "")
        elif kind in ("heading_1", "heading_2", "heading_3"):
            level = min(int(kind[-1]) + 1, 4)  # the page title is the h1
            out.append(f"<h{level}>{text}</h{level}>")
        elif kind == "quote":
            out.append(f"<blockquote>{text}{nested}</blockquote>")
        elif kind == "callout":
            out.append(f"<aside>{text}{nested}</aside>")
        elif kind == "toggle":
            out.append(f"<details><summary>{text}</summary>{nested}</details>")
        elif kind == "divider":
            out.append("<hr/>")
        elif kind == "code":
            out.append(f"<pre><code>{html.escape(plain(data.get('rich_text', [])))}</code></pre>")
        elif kind == "image":
            url = file_urls([data])[0]
            src = save_image(url, f"{image_prefix}-{block['id'][:8]}", session)
            caption = plain(data.get("caption", []))
            out.append(f'<figure><img src="/{src}" alt="{html.escape(caption)}" loading="lazy">{f"<figcaption>{html.escape(caption)}</figcaption>" if caption else ""}</figure>')
        elif kind in ("video", "embed", "bookmark"):
            url = data.get("url") or file_urls([data])[0]
            out.append(f'<p><a href="{html.escape(url)}">{html.escape(url)}</a></p>')
    if open_list:
        out.append(f"</{open_list}>")
    return "".join(out)


def record_fields(page: dict, notion: Notion, session: requests.Session, prefix: str, with_body: bool) -> dict:
    fields = {name: property_value(prop) for name, prop in page["properties"].items()}
    for key in ("Images", "Thumbnail"):
        if isinstance(fields.get(key), list):
            fields[key] = [save_image(url, f"{prefix}-{index}", session) for index, url in enumerate(fields[key]) if url]
    if with_body:
        fields["Page Content"] = blocks_html(notion, page["id"], session, prefix) or None
    return fields


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", default="", help="comma-separated collection keys")
    args = parser.parse_args()
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("NOTION_TOKEN is not set: keeping the committed connect/data.")
        return
    if not CONFIG.exists():
        print(f"{CONFIG.relative_to(ROOT)} is missing: keeping the committed connect/data.")
        return
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    only = {key for key in args.only.split(",") if key}
    notion = Notion(token)
    session = requests.Session()

    for collection in cc.COLLECTIONS:
        settings = config.get(collection.key)
        if not settings or (only and collection.key not in only):
            continue
        pages = [page for page in notion.query(settings["database"]) if not page.get("archived") and not page.get("in_trash")]
        with_body = collection.key not in ("books", "podcasts", "equipment")
        reviews_by_parent: dict[str, list[dict]] = {}
        review_settings = settings.get("reviews")
        if review_settings:
            for page in notion.query(review_settings["database"]):
                if page.get("archived") or page.get("in_trash"):
                    continue
                fields = record_fields(page, notion, session, f"reviews/{page['id'][:8]}", with_body=False)
                for parent in fields.get(review_settings["relation"]) or []:
                    reviews_by_parent.setdefault(parent, []).append({"id": page["id"], "fields": review_fields(fields)})
        records = []
        for page in sorted(pages, key=lambda page: page.get("created_time", "")):
            prefix = f"{collection.key}/{page['id'][:8]}"
            record = {"id": page["id"], "fields": record_fields(page, notion, session, prefix, with_body)}
            if review_settings:
                record["reviews"] = reviews_by_parent.get(page["id"], [])
            records.append(record)
        path = DATA_DIR / f"{collection.key}.json"
        path.write_text(json.dumps({"items": records}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{collection.key}: {len(records)} records" + (f", {sum(len(r.get('reviews', [])) for r in records)} reviews" if review_settings else ""))


if __name__ == "__main__":
    main()
