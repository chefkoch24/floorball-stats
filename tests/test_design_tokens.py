import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_design_tokens", ROOT / "scripts/build_design_tokens.py")
build_design_tokens = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_design_tokens)


def test_tokens_css_has_both_themes_and_tailwind_theme():
    css = build_design_tokens.build()
    assert ':root,\n[data-theme="light"] {' in css
    assert '[data-theme="dark"] {' in css
    assert "--surface: #f3f5f8;" in css and "--surface: #0d131d;" in css
    # Colours that are equal in both themes are not repeated in the dark block.
    dark_block = css.split('[data-theme="dark"] {', 1)[1].split("}", 1)[0]
    assert "--crest-1" not in dark_block
    assert "--color-*: initial;" in css
    assert "--color-ink-muted: var(--ink-muted);" in css
    assert "--radius-lg: 16px;" in css


def test_committed_tokens_css_is_up_to_date():
    committed = (ROOT / "themes/my-theme/static/css/src/tokens.css").read_text(encoding="utf-8")
    assert committed == build_design_tokens.build(), "run `make css` after changing tokens.json"
