import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "themes" / "my-theme"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_share_links_logic() -> None:
    """Runs tests/js/share-links.test.js (node:test) against the share-links helper."""
    result = subprocess.run(
        ["node", "--test", str(ROOT / "tests" / "js" / "share-links.test.js")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_helper_loads_before_the_share_studio() -> None:
    base = (THEME / "templates" / "base.html").read_text()
    assert base.index("theme/js/share-links.js") < base.index("theme/js/share-card.js")


def test_studio_events_use_the_documented_names() -> None:
    studio = (THEME / "static" / "js" / "share-card.js").read_text()
    docs = (ROOT / "docs" / "operations" / "analytics-events.md").read_text()
    assert "const LINK_CTA = 'share_link'" in studio
    for event in ("share_link_clicked", "share_link_completed", "share_link_failed"):
        assert event in docs
