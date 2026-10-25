#!/bin/zsh
# Daily Czech refresh for the nightly CI run (installed via `make install-czech-job`).
# ceskyflorbal.cz blocks GitHub runners, so this Mac syncs the Czech league to
# Neon and CI builds the pages from there. Log: ~/Library/Logs/floorball-czech-refresh.log
set -u
cd "$(dirname "$0")/.." || exit 1

# .env values may contain characters like "&", so read them line by line
# instead of sourcing the file.
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in ''|\#*) continue ;; esac
  export "${line%%=*}=${line#*=}"
done < .env

echo "=== $(date '+%Y-%m-%d %H:%M:%S') czech refresh ($(git rev-parse --abbrev-ref HEAD))"
/usr/bin/make refresh-czech-local PYTHON=.venv/bin/python
rc=$?
echo "=== $(date '+%Y-%m-%d %H:%M:%S') done (exit $rc)"
exit $rc
