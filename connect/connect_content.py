"""Collections of floorballconnect.com and how their records become pages.

Records are stored per collection in connect/data/<key>.json as
``{"items": [{"id", "fields", "reviews"?}]}``. ``fields`` keep the Notion property names
with simple values: text and numbers as they are, a select as its label, a multi-select
as a list of labels, files as a list of image paths (relative to connect/content). The
Softr import (scripts/import_connect_softr.py) and the Notion sync
(scripts/sync_connect_notion.py) both write this shape, so the site does not care where
the content came from.

``normalize`` turns one record into what the templates use: title, subtitle, image,
body HTML, tags, facts, ratings, an outbound link and, for sticks and blades, reviews.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Collection:
    key: str
    slug: str  # URL path, kept from the Softr site
    title: str
    nav: str  # menu group
    intro: str
    legacy_detail: str = ""  # Softr detail page, redirected with ?recordId=
    detail: bool = True  # own page per record
    facet: str = ""  # field the list can be filtered by
    card: str = "media"  # media (image cards), text (no images), row (compact list)
    link_label: str = ""
    sort: tuple[str, ...] = ()


COLLECTIONS = [
    Collection(
        "sticks", "floorball-sticks", "Stick reviews", "Gear",
        "Real stick reviews from the Floorball community for the Floorball community.",
        legacy_detail="floorball-stick-details", facet="Brand",
    ),
    Collection(
        "blades", "floorball-blades", "Blade reviews", "Gear",
        "Real blade reviews from the Floorball community for the Floorball community.",
        legacy_detail="floorball-blade-details", facet="Brand",
    ),
    Collection(
        "equipment", "floorball-equipment", "Equipment", "Gear",
        "Training tools and gear that help you practise on your own.",
        facet="Categories", link_label="View product",
    ),
    Collection(
        "deals", "black-friday-deals", "Black Friday deals", "Gear",
        "The best Floorball Black Friday deals in one place, collected by the community.",
        detail=False, card="text", link_label="Go to the deal",
    ),
    Collection(
        "drills", "floorball-drills", "Drills", "Learn",
        "Floorball drills with setup, sequence and coaching points.",
        legacy_detail="floorball-drill", facet="Categories",
    ),
    Collection(
        "guides", "floorball-guides", "Guides", "Learn",
        "Longer reads on player development and equipment.",
        legacy_detail="guide-details", facet="Category",
    ),
    Collection(
        "lexicon", "floorball-lexicon", "Floorball lexicon", "Learn",
        "The most common Floorball terms explained in plain language, so anyone can understand the game faster.",
        card="row",
    ),
    Collection(
        "books", "floorball-books", "Books", "Learn",
        "Books about Floorball: tactics, training and the history of the game.",
        detail=False, facet="Language", card="text", link_label="Get the book",
        sort=("Year",),
    ),
    Collection(
        "watch", "watch-floorball", "Where to watch", "Watch",
        "Verified links to every major competition, from the World Championships to national leagues, so you always know where and how to watch.",
        legacy_detail="watch-floorball-details", facet="Category",
    ),
    Collection(
        "documentaries", "floorball-documentaries", "Documentaries", "Watch",
        "Floorball documentaries from clubs, national teams and creators, with the language and subtitles.",
        legacy_detail="documentary-details", facet="Language", link_label="Watch",
    ),
    Collection(
        "podcasts", "floorball-podcasts", "Podcasts", "Watch",
        "Floorball podcasts from around the world, by language.",
        detail=False, facet="Language", link_label="Listen",
    ),
]
BY_KEY = {collection.key: collection for collection in COLLECTIONS}
NAV_GROUPS = ["Gear", "Learn", "Watch"]
RATINGS = ("Overall", "Shooting", "Passing", "Dribbling")


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "item"


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item not in (None, ""))
    return str(value).strip()


def _list(value) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]


def _number(value) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _rating(fields: dict, name: str) -> float | None:
    # Review forms wrote "Shooting Rating " with a trailing space; accept both.
    return _number(fields.get(f"{name} Rating", fields.get(f"{name} Rating ")))


# "Floorball" is always capitalised in the copy. Words inside URLs, handles and file names
# (floorball-planet.de, @floorballshow, watch-floorball) are left alone.
_FLOORBALL = re.compile(r"(?<![/\-.@\w])floorball(?![\-\w/@]|\.\w)")


def brand_case(text: str) -> str:
    return _FLOORBALL.sub("Floorball", text) if text else text


def web_url(text: str) -> str:
    """A link as people type it ("www.shop.com", " https://…") as a full https URL."""
    text = (text or "").strip()
    if not text:
        return ""
    return text if re.match(r"^https?://", text) else f"https://{text.lstrip('/')}"


def youtube_id(url: str) -> str:
    """The video id in a YouTube watch, share or thumbnail link."""
    match = re.search(r"(?:youtu\.be/|[?&]v=|ytimg\.com/vi/|youtube\.com/(?:embed|shorts)/)([A-Za-z0-9_-]{11})", url or "")
    return match.group(1) if match else ""


def _ratings(fields: dict) -> dict[str, float]:
    return {name: value for name in RATINGS if (value := _rating(fields, name)) is not None}


@dataclass
class Item:
    id: str
    collection: str
    title: str
    slug: str = ""
    subtitle: str = ""
    image: str = ""
    images: list[str] = field(default_factory=list)
    body: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    facet: list[str] = field(default_factory=list)
    facts: list[tuple[str, str]] = field(default_factory=list)
    ratings: dict[str, float] = field(default_factory=dict)
    link: str = ""
    date: str = ""
    reviews: list[dict] = field(default_factory=list)
    video: str = ""  # YouTube id, embedded on the page
    url: str = ""


def review(fields: dict) -> dict:
    """One community review. Reviewers who chose to stay anonymous get no name and no handle."""
    anonymous = _text(fields.get("Anonymous")).lower().startswith("anonym")
    name = "" if anonymous else _text(fields.get("Display Name"))
    handle = "" if anonymous else _text(fields.get("Instagram Handle")).lstrip("@")
    facts = [(label, _text(fields.get(key))) for label, key in (("Color / edition", "Color/ Edition"), ("Blade", "Blade"), ("Blade", "Blade Text"), ("Flex", "Flex"), ("Shaft", "Shaft"), ("Playing since", "Playing Since"), ("Using it for", "Years This Stick"))]
    return {
        "headline": brand_case(_text(fields.get("Headline"))),
        "text": brand_case(_text(fields.get("Review"))),
        "ratings": _ratings(fields),
        "name": name or "Anonymous",
        "instagram": handle,
        "images": _list(fields.get("Images")),
        "facts": [(label, value) for label, value in facts if value],
    }


def normalize(collection: Collection, record: dict) -> Item:
    fields = record.get("fields", {})
    key = collection.key
    item = Item(id=record["id"], collection=key, title="")
    images = _list(fields.get("Images") or fields.get("Thumbnail"))
    item.images = images
    item.image = images[0] if images else ""
    item.body = _text(fields.get("Page Content") or fields.get("Description"))

    if key in ("sticks", "blades"):
        item.title = _text(fields.get("Name"))
        item.subtitle = _text(fields.get("Brand"))
        item.facet = _list(fields.get("Brand"))
        item.ratings = _ratings(fields)
        item.facts = [(label, _text(fields.get(name))) for label, name in (("Flex", "Flex"), ("Shaft", "Shaft"), ("Blade", "Blade"))]
        item.reviews = [review(entry.get("fields", entry)) for entry in record.get("reviews", [])]
    elif key == "equipment":
        item.title = _text(fields.get("Name"))
        item.summary = _text(fields.get("Short Description"))
        item.tags = item.facet = _list(fields.get("Categories"))
        item.link = _text(fields.get("URL"))
    elif key == "deals":
        item.title = _text(fields.get("Name"))
        item.summary = _text(fields.get("Description"))
        item.tags = _list(fields.get("Discount"))
        item.link = web_url(_text(fields.get("URL") or fields.get("Website")))
    elif key == "drills":
        item.title = _text(fields.get("Name"))
        item.tags = item.facet = _list(fields.get("Categories"))
    elif key == "guides":
        item.title = _text(fields.get("Headline") or fields.get("Name"))
        item.tags = item.facet = _list(fields.get("Category"))
        item.date = _text(fields.get("Date"))
    elif key == "lexicon":
        item.title = _text(fields.get("Name"))
        item.subtitle = _text(fields.get("Headline"))
    elif key == "books":
        item.title = _text(fields.get("EN Title") or fields.get("Title"))
        original = _text(fields.get("Title"))
        item.subtitle = original if original and original != item.title else ""
        item.facet = _list(fields.get("Language"))
        item.facts = [("Author", _text(fields.get("Author"))), ("Year", _text(fields.get("Year"))), ("Language", _text(fields.get("Language"))), ("Format", _text(fields.get("Format")))]
        item.link = _text(fields.get("Link"))
    elif key == "watch":
        item.title = _text(fields.get("Name"))
        item.tags = item.facet = _list(fields.get("Category"))
    elif key == "documentaries":
        english = _text(fields.get("English Titel") or fields.get("English Title"))
        original = _text(fields.get("Name"))
        item.title = english or original
        item.subtitle = original if original and original != item.title else ""
        item.facet = _list(fields.get("Language"))
        subtitles = _text(fields.get("EN Subtitles")).lower()
        item.facts = [("Year", _text(fields.get("Year"))), ("Language", _text(fields.get("Language"))), ("English subtitles", "Yes" if subtitles == "yes" else ("No" if subtitles == "no" else ""))]
        item.link = _text(fields.get("Link") or fields.get("URL") or fields.get("YouTube Link"))
        item.video = youtube_id(item.link) or youtube_id(item.image)
        if item.video and not item.link:
            item.link = f"https://www.youtube.com/watch?v={item.video}"
    elif key == "podcasts":
        item.title = _text(fields.get("Title"))
        item.subtitle = _text(fields.get("Host(s)"))
        item.facet = _list(fields.get("Language"))
        active = _text(fields.get("Active")).lower()
        item.facts = [("Language", _text(fields.get("Language"))), ("Hosts", item.subtitle), ("Status", "Active" if active == "yes" else ("Inactive" if active == "no" else ""))]
        item.link = _text(fields.get("Spotify Link") or fields.get("Link"))

    item.facts = [(label, value) for label, value in item.facts if value]
    for name in ("title", "subtitle", "summary", "body"):
        setattr(item, name, brand_case(getattr(item, name)))
    item.slug = slugify(" ".join(part for part in (item.subtitle if key in ("sticks", "blades") else "", item.title) if part))
    return item


def load(data_dir: Path | str) -> dict[str, list[Item]]:
    """Every collection's items, in the order the data files list them, with unique slugs."""
    items: dict[str, list[Item]] = {}
    for collection in COLLECTIONS:
        path = Path(data_dir) / f"{collection.key}.json"
        records = json.loads(path.read_text(encoding="utf-8"))["items"] if path.exists() else []
        seen: dict[str, int] = {}
        rows = []
        for record in records:
            item = normalize(collection, record)
            if not item.title:
                continue
            count = seen.get(item.slug, 0)
            seen[item.slug] = count + 1
            if count:
                item.slug = f"{item.slug}-{count + 1}"
            item.url = f"{collection.slug}/{item.slug}/" if collection.detail else f"{collection.slug}/#{item.slug}"
            rows.append(item)
        if collection.sort:
            rows.sort(key=lambda row: [-(_number(dict(row.facts).get(name)) or 0) for name in collection.sort])
        items[collection.key] = rows
    return items


def review_average(item: Item) -> dict[str, float]:
    """The record's ratings (kept up to date in Notion), else the average of its reviews."""
    if item.ratings or not item.reviews:
        return item.ratings
    out = {}
    for name in RATINGS:
        values = [entry["ratings"][name] for entry in item.reviews if name in entry["ratings"]]
        if values:
            out[name] = round(sum(values) / len(values), 1)
    return out or item.ratings
