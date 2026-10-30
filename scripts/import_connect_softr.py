"""Import the Softr snapshot of floorballconnect.com into connect/data.

The old site ran on Softr on top of Notion databases. The snapshot is the JSON that the
Softr data API returned for every list (and, for sticks and blades, the reviews on each
detail page), saved as {softr_slug: {"list": [{"items": [...]}], "details": {record_id:
[{"items": [...]}]}}}. This script turns it into connect/data/<collection>.json in the
format connect_content.py reads, and downloads the images whose links expire (Notion
file links last one hour, Tally upload links carry a token) into connect/content/images.

Usage: python scripts/import_connect_softr.py --snapshot path/to/full.json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "connect"))
import connect_content as cc  # noqa: E402

DATA_DIR = ROOT / "connect" / "data"
IMAGE_DIR = ROOT / "connect" / "content" / "images"
EXPIRING_HOSTS = ("amazonaws.com", "storage.tally.so", "notion-static.com", "notion.so")
MAX_SIDE = 1400
# Only what a review page shows. Reviewers who chose to stay anonymous lose name and handle
# here already, so they never reach the repository.
REVIEW_FIELDS = (
    "Headline", "Review", "Anonymous", "Display Name", "Instagram Handle", "Images",
    "Overall Rating", "Shooting Rating", "Shooting Rating ", "Passing Rating", "Dribbling Rating",
    "Color/ Edition", "Blade", "Blade Text", "Flex", "Shaft", "Playing Since", "Years This Stick",
)


EMAIL = re.compile(r"[\w.%+-]+@[\w-]+(?:\.[\w-]+)+")


def review_fields(fields: dict) -> dict:
    kept = {key: value for key, value in fields.items() if key in REVIEW_FIELDS}
    # Some reviewers typed their email address into a text field; it is never published.
    for key, value in kept.items():
        if isinstance(value, str) and EMAIL.search(value):
            kept[key] = EMAIL.sub("", value).strip() or None
    if str(simplify(kept.get("Anonymous")) or "").lower().startswith("anonym"):
        kept.pop("Display Name", None)
        kept.pop("Instagram Handle", None)
    return kept


def simplify(value):
    """Softr's field values in the shape connect_content expects: labels and URLs as plain strings."""
    if isinstance(value, dict):
        return value.get("label") if "label" in value else (value.get("url") or value)
    if isinstance(value, list):
        out = []
        for entry in value:
            if isinstance(entry, dict):
                out.append(entry.get("label") or entry.get("url"))
            else:
                out.append(entry)
        return [entry for entry in out if entry not in (None, "")]
    return value


def save_image(url: str, name: str, session: requests.Session) -> str:
    """Store an expiring (or inline data:) image as a shrunk WebP; return its path under content/."""
    inline = url.startswith("data:")
    if not inline and not any(host in urlparse(url).netloc for host in EXPIRING_HOSTS):
        return url
    from PIL import Image, ImageOps  # noqa: PLC0415 - only needed when importing

    target = IMAGE_DIR / f"{name}.webp"
    if not target.exists():
        if inline:
            content = base64.b64decode(url.split(",", 1)[1])
        else:
            response = session.get(url, timeout=60)
            response.raise_for_status()
            content = response.content
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(content)))
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "transparency" in image.info else "RGB")
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, "WEBP", quality=82, method=6)
    return target.relative_to(ROOT / "connect" / "content").as_posix()


def localize(fields: dict, prefix: str, session: requests.Session) -> dict:
    out = {}
    for key, value in fields.items():
        value = simplify(value)
        if key in ("Images", "Thumbnail") and isinstance(value, list):
            value = [
                save_image(url, f"{prefix}-{hashlib.sha1(url.split('?')[0].encode()).hexdigest()[:8]}", session)
                for url in value if isinstance(url, str)
            ]
        out[key] = value
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", required=True, type=Path)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    session = requests.Session()
    session.headers["User-Agent"] = "FloorballConnect/1.0 (+https://www.floorballconnect.com)"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for collection in cc.COLLECTIONS:
        source = snapshot.get(collection.slug)
        if not source:
            print(f"{collection.key}: not in the snapshot, kept as it is")
            continue
        records, seen = [], set()
        for block in source["list"]:
            for item in block["items"]:
                if item["id"] in seen:
                    continue
                seen.add(item["id"])
                record = {"id": item["id"], "fields": localize(item["fields"], f"{collection.key}/{item['id'][:8]}", session)}
                if collection.key in ("sticks", "blades"):
                    reviews, review_ids = [], set()
                    for detail_block in source.get("details", {}).get(item["id"], []):
                        for entry in detail_block["items"]:
                            fields = entry.get("fields", {})
                            if entry["id"] in review_ids or not ({"Review", "Headline", "Display Name"} & set(fields)):
                                continue
                            review_ids.add(entry["id"])
                            reviews.append({"id": entry["id"], "fields": localize(review_fields(fields), f"reviews/{entry['id'][:8]}", session)})
                    record["reviews"] = reviews
                records.append(record)
        path = DATA_DIR / f"{collection.key}.json"
        path.write_text(json.dumps({"items": records}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        reviews = sum(len(record.get("reviews", [])) for record in records)
        print(f"{collection.key}: {len(records)} records" + (f", {reviews} reviews" if reviews else ""))


if __name__ == "__main__":
    main()
