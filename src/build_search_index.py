import argparse
import json
from pathlib import Path


def _parse_metadata(path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if not line.strip():
                break
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key_clean = key.strip().lower()
            if not key_clean:
                continue
            metadata[key_clean] = value.strip()
    return metadata


def _build_entry(path: Path, entity_type: str) -> dict[str, str] | None:
    meta = _parse_metadata(path)
    slug = meta.get("slug", "")
    if not slug:
        return None

    if entity_type == "player":
        name = meta.get("player", "") or meta.get("title", "")
        league = meta.get("league", "")
        subtitle = league
    else:
        name = meta.get("team", "") or meta.get("title", "")
        league = meta.get("category", "")
        subtitle = league.replace(",", " · ").strip()

    if not name:
        return None

    return {
        "type": entity_type,
        "name": name,
        "subtitle": subtitle,
        "league": league,
        "slug": slug,
        "url": f"/{slug}.html",
    }


def build_search_index(content_dir: str, output_path: str) -> int:
    content_path = Path(content_dir)
    player_paths = sorted((content_path / "players").glob("*.md"))
    team_paths = sorted(content_path.glob("**/teams/*.md"))

    items: list[dict[str, str]] = []
    for path in player_paths:
        entry = _build_entry(path, "player")
        if entry:
            items.append(entry)
    for path in team_paths:
        entry = _build_entry(path, "team")
        if entry:
            items.append(entry)

    payload = {
        "version": 1,
        "item_count": len(items),
        "items": items,
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(items)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build global player/team search index.")
    parser.add_argument("--content-dir", default="content")
    parser.add_argument("--output-path", default="themes/my-theme/static/search/search-index.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = build_search_index(content_dir=args.content_dir, output_path=args.output_path)
    print(f"search-index: wrote {count} records to {args.output_path}")


if __name__ == "__main__":
    main()
