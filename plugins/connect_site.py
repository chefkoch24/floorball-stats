"""Pelican plugin: build the main site (connect/) together with the stats site.

One Netlify site serves both domains. The stats build builds connect/ into a folder of
its output and, in production, writes domain rules into output/_redirects:

- https://www.floorballconnect.com/* is served from /connect-site/ (a rewrite, the
  address stays www.floorballconnect.com),
- the old Softr URLs (?recordId= detail pages, /login, ...) redirect on that domain,
- https://floorballconnect.com/* redirects to www.

Deploy previews build it into /connect-preview/ with preview links and no domain rules.
Settings (publishconf.py): CONNECT_BUILD_DIR, CONNECT_BUILD_URL, CONNECT_HOST, CONNECT_APEX.
With NOTION_TOKEN set, the Notion content is synced first (scripts/sync_connect_notion.py).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys

from pelican import signals

log = logging.getLogger(__name__)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def host_rules(connect_redirects: str, host: str, folder: str, apex: str = "") -> list[str]:
    """The main site's own _redirects rewritten for its domain, then the rewrite into its folder."""
    rules = []
    if apex:
        rules.append(f"https://{apex}/* https://{host}/:splat 301!")
    for line in connect_redirects.splitlines():
        parts = line.split()
        if not parts or parts[0].startswith("#") or not parts[0].startswith("/"):
            continue
        rules.append(" ".join([f"https://{host}{parts[0]}", *parts[1:]]))
    # Should the folder ever show up in an address, send it back to the clean URL.
    rules.append(f"https://{host}/{folder}/* https://{host}/:splat 301!")
    rules.append(f"https://{host}/* /{folder}/:splat 200!")
    return rules


def _run(command: list[str], env: dict, cwd: str) -> str:
    try:
        result = subprocess.run(command, env=env, cwd=cwd, capture_output=True, text=True)
    except OSError as error:
        log.error("could not run %s: %r", command[1:3], error)
        return f"could not start: {error!r}"
    report = f"$ {' '.join(command)}\nexit {result.returncode}\n{result.stdout}\n{result.stderr}"
    if result.returncode:
        log.error("connect build step failed:\n%s", report)
    return report


def build(pelican) -> None:
    settings = pelican.settings
    folder = settings.get("CONNECT_BUILD_DIR")
    if not folder:
        return
    # Absolute: the build below runs in connect/, and Netlify passes a relative output path.
    output_root = os.path.abspath(settings["OUTPUT_PATH"])
    output = os.path.join(output_root, folder)
    env = {
        **os.environ,
        "CONNECT_SITEURL": settings["CONNECT_BUILD_URL"].rstrip("/"),
        "CONNECT_STATS_URL": settings["SITEURL"].rstrip("/"),
    }
    reports = []
    if os.environ.get("NOTION_TOKEN"):
        reports.append(_run([sys.executable, os.path.join(ROOT, "scripts", "sync_connect_notion.py")], env, ROOT))
    reports.append(_run([
        sys.executable, "-m", "pelican", os.path.join(ROOT, "connect", "content"),
        "-o", output, "-s", os.path.join(ROOT, "connect", "publishconf.py"),
    ], env, os.path.join(ROOT, "connect")))

    host = settings.get("CONNECT_HOST")
    redirects_file = os.path.join(output, "_redirects")
    if host and os.path.exists(redirects_file):
        with open(redirects_file, encoding="utf-8") as handle:
            rules = host_rules(handle.read(), host, folder, settings.get("CONNECT_APEX", ""))
        target = os.path.join(output_root, "_redirects")
        existing = ""
        if os.path.exists(target):
            with open(target, encoding="utf-8") as handle:
                existing = handle.read().rstrip() + "\n"
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(existing + f"# Main site on {host} (plugins/connect_site.py)\n" + "\n".join(rules) + "\n")
        log.info("connect site built into %s, %d domain rules", output, len(rules))

    # The build log sits next to the site, so a failed build can be read without Netlify access.
    os.makedirs(output, exist_ok=True)
    with open(os.path.join(output, "build-log.txt"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(reports))


def register():
    signals.finalized.connect(build)
