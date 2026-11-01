"""Validate the published two-domain site before submitting its sitemaps.

Usage: python scripts/check_seo.py output [--report /tmp/seo-check.json]
No network requests, league refreshes or Google submissions are performed.
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.canonical = self.description = self.robots = self.lang = ""
        self.title = ""
        self.h1 = 0
        self.links = set()
        self.schemas = []
        self.schema_errors = []
        self._title = self._schema = False
        self._head = False
        self._json = ""
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "head":
            self._head = True
        if tag == "html":
            self.lang = attrs.get("lang", "")
        if tag == "title" and self._head:
            self._title = True
        if tag == "h1":
            self.h1 += 1
        if tag == "a" and attrs.get("href"):
            self.links.add(attrs["href"])
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href", "")
        if tag == "meta":
            name = attrs.get("name", "").lower()
            if name in ("robots", "description"):
                setattr(self, name, attrs.get("content", ""))
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self._schema = True
            self._json = ""

    def handle_data(self, text):
        if self._title:
            self.title += text
        if self._schema:
            self._json += text

    def handle_endtag(self, tag):
        if tag == "head":
            self._head = False
        if tag == "title":
            self._title = False
        if tag == "script" and self._schema:
            self._schema = False
            try:
                self.schemas.append(json.loads(self._json))
            except ValueError as error:
                self.schema_errors.append(str(error))


def local_path(root, path):
    path = unquote(path).lstrip("/")
    candidate = root / (path or "index.html")
    if candidate.is_dir() or path.endswith("/"):
        candidate /= "index.html"
    elif not candidate.exists() and not candidate.suffix:
        candidate = candidate.with_suffix(".html")
    return candidate


def check(output):
    errors, summaries = [], []
    sites = [(output, "stats"), (output / "connect-site", "connect")]
    roots = {}
    maps = []
    for root, name in sites:
        sitemap = root / "sitemap.xml"
        if not sitemap.exists():
            errors.append(f"Missing {name} sitemap: {sitemap}")
            continue
        doc = ET.parse(sitemap)
        urls = [node.text for node in doc.findall(".//{*}loc")]
        if not urls:
            errors.append(f"Empty {name} sitemap")
            continue
        first = urlsplit(urls[0])
        roots[first.netloc] = root
        maps.append((root, name, doc, urls))

    cache = {}

    def page(path):
        if path not in cache:
            cache[path] = Page(path.read_text(encoding="utf-8"))
        return cache[path]

    for root, name, doc, urls in maps:
        if len(urls) != len(set(urls)):
            errors.append(f"Duplicate URLs in {name} sitemap")
        for node in doc.findall(".//{*}lastmod"):
            try:
                if date.fromisoformat(node.text[:10]) > date.today():
                    errors.append(f"Future lastmod in {name}: {node.text}")
            except (TypeError, ValueError):
                errors.append(f"Invalid lastmod in {name}: {node.text}")
        for url in urls:
            parsed = urlsplit(url)
            path = local_path(root, parsed.path)
            if not path.is_file():
                errors.append(f"Sitemap target missing: {url}")
                continue
            value = page(path)
            if value.canonical != url:
                errors.append(f"Sitemap/canonical mismatch: {url} -> {value.canonical}")
            if "noindex" in value.robots:
                errors.append(f"Noindex URL in sitemap: {url}")
            if not value.title.strip() or not value.description.strip() or value.h1 != 1:
                errors.append(f"Missing title/description or non-unique H1: {url}")
            if value.lang != "en":
                errors.append(f"Unexpected language: {url}: {value.lang}")
            if value.schema_errors:
                errors.append(f"Invalid JSON-LD: {url}: {value.schema_errors}")
            if name == "connect" and not value.schemas:
                errors.append(f"No structured data: {url}")
            for link in value.links:
                target = urlsplit(urljoin(url, link))
                if target.netloc in roots and not local_path(roots[target.netloc], target.path).is_file():
                    errors.append(f"Broken internal link: {url} -> {link}")
        summaries.append({"site": name, "sitemap_urls": len(urls)})

    # The glossary previously existed only in a disconnected set of detail pages.
    if (output / "connect-site" / "index.html").exists():
        root = output / "connect-site"
        reachable, pending = {root / "index.html"}, deque([root / "index.html"])
        while pending:
            current = pending.popleft()
            for link in page(current).links:
                parsed = urlsplit(link)
                if parsed.netloc not in roots or roots[parsed.netloc] != root:
                    continue
                target = local_path(root, parsed.path)
                if target.suffix == ".html" and target.is_file() and target not in reachable:
                    reachable.add(target)
                    pending.append(target)
        lexicon = list((root / "floorball-lexicon").glob("*/index.html"))
        for target in lexicon:
            if target not in reachable:
                errors.append(f"Unreachable lexicon detail: {target.relative_to(root)}")
        summaries.append({"reachable_lexicon_details": len(lexicon)})
    return {"sites": summaries, "errors": sorted(set(errors))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = check(args.output)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sites": report["sites"], "error_count": len(report["errors"]),
                      "errors": report["errors"][:25]}, indent=2))
    raise SystemExit(bool(report["errors"]))


if __name__ == "__main__":
    main()
