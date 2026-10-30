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
    # Absolute: the build below runs in connect/, and Netlify passes a relative output path.
    output = os.path.abspath(os.path.join(settings["OUTPUT_PATH"], PREVIEW_DIR))
    env = {
        **os.environ,
        "CONNECT_SITEURL": f"{settings['SITEURL'].rstrip('/')}/{PREVIEW_DIR}",
        "CONNECT_STATS_URL": settings["SITEURL"].rstrip("/"),
    }
    command = [
        sys.executable, "-m", "pelican", os.path.join(ROOT, "connect", "content"),
        "-o", output, "-s", os.path.join(ROOT, "connect", "publishconf.py"),
    ]
    try:
        result = subprocess.run(command, env=env, cwd=os.path.join(ROOT, "connect"), capture_output=True, text=True)
        report = f"exit {result.returncode}\n{result.stdout}\n{result.stderr}"
    except OSError as error:
        result, report = None, f"could not start the build: {error!r}"
    if result is None or result.returncode:
        log.error("connect preview build failed:\n%s", report)
    else:
        log.info("connect preview built into %s", output)
    # The build log sits next to the preview, so a failed build can be read without Netlify access.
    os.makedirs(output, exist_ok=True)
    with open(os.path.join(output, "build-log.txt"), "w", encoding="utf-8") as handle:
        handle.write(f"{' '.join(command)}\n{report}")


def register():
    signals.finalized.connect(build)
