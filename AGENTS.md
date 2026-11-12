# AGENTS.md

## Project

- This is a Floorball Stats project running here: https://stats.floorballconnect.com
- It's deployed via Netlify
- Run the frontend with: `pelican --autoreload --listen --port 8000`

## Work Instructions
- BACKLOG.md is your main source for new tasks next to the commands from me.
- Do always check if you have open tasks in your BACKLOG.md
- Do not cache or save the BACKLOG.md statically in your context the content of it can change during your runtime
- Only refresh all leagues data if it's really required and new datapoints have to be added
- If a full repository refresh is required, use `make refresh-all-leagues PYTHON=.venv/bin/python PELICAN=.venv/bin/pelican` so league data, player stats, player pages, and the site build stay in sync
- Prefer the database-driven path for new work. Neon/Postgres is the target runtime source, SQLite is the local mirror, and CSV should only be treated as fallback/testing/export compatibility while the migration is still in progress.

## Branch cleanup
- One branch per feature, cut from `origin/master`, one PR each.
- After a PR is merged, always clean up: delete the local branch, delete the remote branch (`git push origin --delete <branch>`), run `git fetch --prune`, remove its worktree if there is one, and switch back to an up-to-date `master`. Do not keep merged branches around.
- Before deleting, confirm the merge (`gh pr view <n>`); squash merges do not show up in `git branch --merged`.

## Docs and backlog
- All concepts, plans and research live in `docs/` (index: `docs/README.md`). Do not add new plan or concept files to the repo root.
- A bigger feature gets a concept doc in `docs/features/<name>.md` with a `Status` line, linked from its BACKLOG.md entry.
- When you finish backlog work: tick the item, move it from **Open** to **Done** in BACKLOG.md, and update the `Status` line of its concept doc and the table in `docs/README.md`.

## Other important docs
- docs/architecture/ARCHITECTURE.md contains the information about the architecture of this project
- README.md contains all internal information on how to run the pipelines
- When adding or changing pipelines/backends, also follow the integration invariants in `docs/architecture/ARCHITECTURE.md` and the backend checklist in `README.md` so new sources work end-to-end without one-off fixes
