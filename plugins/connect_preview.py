"""Pelican plugin: build the main site (connect/) into the stats deploy preview.

The main site has its own Netlify site in production. Until that exists, and to review
both sites together in one pull request, deploy previews of the stats site also build
connect/ into <output>/connect-preview/ when CONNECT_PREVIEW is set (publishconf.py does
that for Netlify deploy previews and branch deploys). Production builds skip it.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys

from pelican import signals

log = logging.getLogger(__name__)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREVIEW_DIR = "connect-preview"


def build(pelican) -> None:
    settings = pelican.settings
    if not settings.get("CONNECT_PREVIEW"):
        return
    output = os.path.join(settings["OUTPUT_PATH"], PREVIEW_DIR)
    env = {
        **os.environ,
        "CONNECT_SITEURL": f"{settings['SITEURL'].rstrip('/')}/{PREVIEW_DIR}",
        "CONNECT_STATS_URL": settings["SITEURL"].rstrip("/"),
    }
    command = [
        sys.executable, "-m", "pelican", os.path.join(ROOT, "connect", "content"),
        "-o", output, "-s", os.path.join(ROOT, "connect", "publishconf.py"),
    ]
    result = subprocess.run(command, env=env, cwd=os.path.join(ROOT, "connect"), capture_output=True, text=True)
    if result.returncode:
        log.error("connect preview build failed:\n%s%s", result.stdout, result.stderr)
    else:
        log.info("connect preview built into %s", output)


def register():
    signals.finalized.connect(build)
