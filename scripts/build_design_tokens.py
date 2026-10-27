"""Write the theme's token stylesheet from the design system's tokens.json.

themes/my-theme/design-system/tokens.json is the one source for colours, spacing,
radii and shadows (the same file as the published design system). This script
turns it into themes/my-theme/static/css/src/tokens.css, which the Tailwind entry
file imports. Run it through `make css`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS = ROOT / "themes/my-theme/design-system/tokens.json"
TARGET = ROOT / "themes/my-theme/static/css/src/tokens.css"
ALIAS = re.compile(r"^\{([A-Za-z0-9_.-]+)\}$")


def _css_value(value: str) -> str:
    match = ALIAS.match(value)
    return f"var(--{match.group(1)})" if match else value


def _per_theme(tokens: list[dict], theme_ids: list[str]) -> dict[str, list[str]]:
    first = theme_ids[0]
    blocks: dict[str, list[str]] = {theme: [] for theme in theme_ids}
    for token in tokens:
        value = token["value"]
        values = value if isinstance(value, dict) else {first: value}
        for theme in theme_ids:
            if theme in values and (theme == first or values[theme] != values.get(first)):
                blocks[theme].append(f"  --{token['name']}: {_css_value(values[theme])};")
    return blocks


def build() -> str:
    data = json.loads(TOKENS.read_text(encoding="utf-8"))
    theme_ids = [theme["id"] for theme in data["color"]["themes"]]
    themed = data["color"]["tokens"] + data.get("shadow", {}).get("tokens", [])
    blocks = _per_theme(themed, theme_ids)

    lines = [f"/* {data['name']} — generated from tokens.json by scripts/build_design_tokens.py */", ""]
    lines.append(f":root,\n[data-theme=\"{theme_ids[0]}\"] {{")
    lines += blocks[theme_ids[0]]
    lines.append(f"  color-scheme: {theme_ids[0]};")
    lines.append("}")
    for theme in theme_ids[1:]:
        lines += ["", f"[data-theme=\"{theme}\"] {{", *blocks[theme], f"  color-scheme: {theme};", "}"]

    # Spacing stays a plain custom property: components use var(--space-4) while
    # Tailwind's own 4px spacing scale (p-4 = 16px) lines up with it.
    lines += ["", ":root {"]
    lines += [f"  --{token['name']}: {token['value']};" for token in data["spacing"]["tokens"]]
    lines.append("}")

    # Tailwind theme: only the design system's colours exist as utilities
    # (bg-surface-raised, text-ink-muted, border-line, ...), and they follow data-theme.
    lines += ["", "@theme inline {", "  --color-*: initial;"]
    lines += [f"  --color-{token['name']}: var(--{token['name']});" for token in data["color"]["tokens"]]
    lines.append("}")
    lines += ["", "@theme {"]
    lines += [f"  --font-{key}: {stack};" for key, stack in data["type"]["families"].items()]
    lines += [f"  --{token['name']}: {token['value']};" for token in data["radius"]["tokens"]]
    lines.append("}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(build(), encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)}")
