import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_tracking_script_logic() -> None:
    """Runs tests/js/tracking.test.js (node:test) against themes/shared/static/js/tracking.js."""
    result = subprocess.run(
        ["node", "--test", str(ROOT / "tests" / "js" / "tracking.test.js")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_templates_load_the_shared_tracking_script() -> None:
    stats = (ROOT / "themes" / "my-theme" / "templates" / "base.html").read_text()
    connect = (ROOT / "themes" / "connect" / "templates" / "base.html").read_text()
    assert 'theme/js/tracking.js" data-site="stats"' in stats
    assert 'theme/js/tracking.js" data-site="connect"' in connect


def test_no_template_sends_raw_posthog_events() -> None:
    """New events go through fbTrack so names and properties stay uniform and free of search text."""
    allowed = {ROOT / "themes" / "shared" / "static" / "js" / "tracking.js"}
    offenders = []
    for folder in ("themes/my-theme", "themes/connect", "themes/shared"):
        for path in (ROOT / folder).rglob("*"):
            if path.suffix not in {".html", ".js"} or path in allowed or "chart.umd" in path.name:
                continue
            if "posthog.capture" in path.read_text(errors="ignore"):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
