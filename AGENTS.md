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

## Other important docs
- ARCHITECTURE.md contains the information about the architecture of this project
- README.md contains all internal information on how to run the pipelines
