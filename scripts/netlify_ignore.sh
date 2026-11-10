#!/usr/bin/env bash
# Netlify "ignore" command (netlify.toml): exit 0 skips the build, exit 1 builds.
#
# Netlify build minutes are limited, and a full site build takes several minutes.
#  - Deploy previews only build on request: put "[preview]" in the PR's latest
#    commit message. Every PR is still built and link-checked by the GitHub
#    workflow "SEO build checks" (.github/workflows/seo-check.yml), which costs
#    no Netlify minutes.
#  - Production and previews skip commits that change nothing the site is built
#    from (docs, tests, workflows, notebooks, social graphics, the dashboard).
set -u

# Build hooks always build: the daily main-site build (connect-daily-build.yml) has no
# new commit, it rebuilds to pick up new Notion content.
if [ -n "${INCOMING_HOOK_URL:-}${INCOMING_HOOK_TITLE:-}" ]; then
  echo "Build hook (${INCOMING_HOOK_TITLE:-unnamed}): building."
  exit 1
fi

if [ "${CONTEXT:-}" = "deploy-preview" ]; then
  if git log -1 --format=%B "${COMMIT_REF:-HEAD}" | grep -qF "[preview]"; then
    echo "Deploy preview requested with [preview]."
  else
    echo "Skipping deploy preview: add [preview] to the latest commit message to build one."
    exit 0
  fi
fi

# No earlier deploy to compare with (first build, cleared cache): build.
if [ -z "${CACHED_COMMIT_REF:-}" ] || ! git cat-file -e "${CACHED_COMMIT_REF}^{commit}" 2>/dev/null; then
  echo "No previous deploy to compare with: building."
  exit 1
fi

if git diff --quiet "$CACHED_COMMIT_REF" "${COMMIT_REF:-HEAD}" -- . \
    ':(exclude,glob)*.md' \
    ':(exclude)docs' ':(exclude)tests' ':(exclude)notebooks' ':(exclude)scripts' \
    ':(exclude)social' ':(exclude)dashboard' ':(exclude).github' ':(exclude).claude' \
    ':(exclude)Makefile' ':(exclude)tasks.py' ':(exclude)show_data.py' \
    ':(exclude)docker-compose.yml' ':(exclude)erd.plantuml'; then
  echo "Skipping build: no changes to files the site is built from since $CACHED_COMMIT_REF."
  exit 0
fi
echo "Site files changed since $CACHED_COMMIT_REF: building."
exit 1
