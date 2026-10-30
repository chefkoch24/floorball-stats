"""Pelican plugin: list and detail pages for the collections in connect/data.

Loads every collection once (connect_content.load), puts them into the template context
as CONNECT_COLLECTIONS / CONNECT_ITEMS for the home page and the menu, writes one list
page per collection and one page per record, and writes the redirects from the old Softr
URLs (?recordId=) to the new pages.
"""

from __future__ import annotations

import os
import sys
from xml.sax.saxutils import escape

from pelican import signals

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import connect_content as cc  # noqa: E402

_cache: dict = {}


def _load(settings) -> dict:
    data_dir = settings.get("COLLECTIONS_DATA")
    if _cache.get("dir") != data_dir:
        _cache.update(dir=data_dir, items=cc.load(data_dir))
    return _cache["items"]


def add_context(generator) -> None:
    items = _load(generator.settings)
    generator.context["CONNECT_COLLECTIONS"] = cc.COLLECTIONS
    generator.context["CONNECT_NAV_GROUPS"] = cc.NAV_GROUPS
    generator.context["CONNECT_ITEMS"] = items
    generator.context["CONNECT_RATINGS"] = cc.RATINGS
    generator.context["CONNECT_REVIEW_COUNT"] = sum(len(item.reviews) for key in ("sticks", "blades") for item in items.get(key, []))
    generator.env.globals["review_average"] = cc.review_average


def remember_pages(generator) -> None:
    _cache["pages"] = sorted(page.url for page in generator.pages)


def write_pages(generator, writer) -> None:
    items = _load(generator.settings)
    context = generator.context
    list_template = generator.get_template("collection")
    for collection in cc.COLLECTIONS:
        rows = items.get(collection.key, [])
        facets = sorted({value for row in rows for value in row.facet}, key=str.lower)
        writer.write_file(
            f"{collection.slug}/index.html", list_template, context,
            relative_urls=generator.settings["RELATIVE_URLS"], url=f"{collection.slug}/",
            collection=collection, items=rows, facets=facets, page_name=collection.slug,
        )
        if not collection.detail:
            continue
        detail_template = generator.get_template("item_review" if collection.key in ("sticks", "blades") else "item")
        for index, item in enumerate(rows):
            # Same brand or category first, then the neighbours in the list, so every page has some.
            others = [row for row in rows if row is not item]
            related = [row for row in others if set(row.facet) & set(item.facet)]
            related += [row for row in others if row not in related]
            writer.write_file(
                f"{collection.slug}/{item.slug}/index.html", detail_template, context,
                relative_urls=generator.settings["RELATIVE_URLS"], url=item.url,
                collection=collection, item=item, related=related[:3], page_name=item.url,
                previous=rows[index - 1] if index else None, next=rows[index + 1] if index + 1 < len(rows) else None,
            )


def redirects(items: dict) -> list[str]:
    """Netlify rules for the Softr detail URLs: /floorball-stick-details?recordId=<id>."""
    lines = []
    for collection in cc.COLLECTIONS:
        if not collection.legacy_detail:
            continue
        for item in items.get(collection.key, []):
            target = f"/{item.url}" if collection.detail else f"/{collection.slug}/"
            lines.append(f"/{collection.legacy_detail} recordId={item.id} {target} 301!")
        lines.append(f"/{collection.legacy_detail} /{collection.slug}/ 301!")
    return lines


def sitemap(site_url: str, items: dict, pages: list[str]) -> str:
    urls = ["", *pages]
    for collection in cc.COLLECTIONS:
        urls.append(f"{collection.slug}/")
        if collection.detail:
            urls.extend(item.url for item in items.get(collection.key, []))
    rows = "".join(f"<url><loc>{escape(site_url)}/{escape(url)}</loc></url>" for url in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>\n'


def finalize(pelican) -> None:
    """Append the Softr redirects to _redirects and write sitemap.xml."""
    items = _load(pelican.settings)
    output = pelican.settings["OUTPUT_PATH"]
    path = os.path.join(output, "_redirects")
    existing = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            existing = handle.read().rstrip() + "\n"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(existing + "\n".join(redirects(items)) + "\n")
    with open(os.path.join(output, "sitemap.xml"), "w", encoding="utf-8") as handle:
        handle.write(sitemap(pelican.settings.get("SITEURL", ""), items, _cache.get("pages", [])))


def register():
    signals.generator_init.connect(add_context)
    signals.page_generator_finalized.connect(remember_pages)
    signals.page_writer_finalized.connect(write_pages)
    signals.finalized.connect(finalize)
