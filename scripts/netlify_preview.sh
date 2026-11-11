#!/usr/bin/env bash
# Preview of the checked-out branch on Netlify, built locally (no Netlify build minutes).
#
#   make preview PELICAN=.venv/bin/pelican            # alias from the branch name
#   make preview PELICAN=.venv/bin/pelican ALIAS=my-feature
#
# Netlify's own builds are stopped (production is deployed by GitHub Actions,
# .github/workflows/deploy.yml), so previews only exist on request. The preview is
# served at https://<alias>--floorball-stats.netlify.app; the build links to that URL
# and shows the main site under /connect-preview/ (publishconf.py), like a deploy preview.
set -euo pipefail

SITE_NAME="${NETLIFY_SITE:-floorball-stats}"
PELICAN="${PELICAN:-pelican}"
NETLIFY="${NETLIFY:-netlify}"

alias="${1:-${ALIAS:-}}"
if [ -z "$alias" ]; then
  alias="preview-$(git rev-parse --abbrev-ref HEAD)"
fi
# Netlify aliases: lowercase letters, digits and hyphens, short enough for a subdomain.
alias="$(printf '%s' "$alias" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-' | sed 's/--*/-/g; s/^-//; s/-$//' | cut -c1-40)"
alias="${alias%-}"
url="https://${alias}--${SITE_NAME}.netlify.app"

out="$(mktemp -d "${TMPDIR:-/tmp}/floorball-preview.XXXXXX")"
trap 'rm -rf "$out"' EXIT

echo "Building preview for $url"
CONTEXT=deploy-preview DEPLOY_PRIME_URL="$url" "$PELICAN" content -o "$out" -s publishconf.py

"$NETLIFY" deploy --no-build --dir "$out" --site "$SITE_NAME" --alias "$alias" \
  --message "Preview $(git rev-parse --abbrev-ref HEAD) $(git rev-parse --short HEAD)"
echo "Preview: $url"
