# README

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Canonical pipeline (single league)

```bash
make refresh-current-season
```

This runs the new unified module entrypoint:

```bash
python -m src.pipeline --league_id 1890 --season 25-26 --phase regular-season
```

German playoffs (Saisonmanager league id `1963`) via config:

```bash
make refresh-current-season-playoffs
```

## Canonical full refresh (all leagues + player stats + site build)

Use this when you want the repository fully updated end-to-end:

```bash
make refresh-all-leagues
```

This runs:
- all smart league refresh targets
- `make refresh-player-stats`
- `make refresh-player-pages`
- `make html`

During refreshes, the pipeline also maintains a derived local SQLite database at `data/stats.db`.
This database is intended for local querying and CI build steps; CSV and markdown remain the
git-tracked source artifacts.

`make refresh-everything` is an alias for the same flow.

## Sweden (StatsApp backend)

Pipeline entrypoint with Sweden backend:

```bash
python -m src.pipeline --backend sweden --competition_id 40693 --season se-25-26 --phase regular-season
```

Make target:

```bash
make refresh-sweden SWEDEN_COMPETITION_ID=40693 SWEDEN_SEASON=se-25-26 PHASE=regular-season
```

Playoffs / smart refresh:

```bash
make refresh-sweden-playoffs
make refresh-sweden-smart
```

## Slovakia (SZFB backend)

Pipeline entrypoint with Slovakia backend:

```bash
python -m src.pipeline --backend slovakia --slovakia_schedule_url "https://www.szfb.sk/sk/stats/results-date/1164/florbalova-extraliga-muzov" --season sk-25-26 --phase regular-season
```

Make target:

```bash
make refresh-slovakia SLOVAKIA_LEAGUE_CONFIG=config/leagues/slovakia-extraliga.json
```

## Latvia (floorball.lv backend)

Pipeline entrypoint with Latvia backend:

```bash
python -m src.pipeline --backend latvia --latvia_calendar_url "https://www.floorball.lv/lv/2025/chempionats/vv/kalendars" --latvia_season_start_year 2025 --season lv-25-26 --phase regular-season
```

Make target:

```bash
make refresh-latvia LATVIA_LEAGUE_CONFIG=config/leagues/latvia-elvi-vv.json
```

## Finland playoffs

Playoffs / smart refresh:

```bash
make refresh-finland-playoffs
make refresh-finland-smart
```

## Player pages from CSV

Build player stats CSV for all available leagues and generate unique player pages plus season player-stats indexes:

```bash
make refresh-player-stats
make refresh-player-pages
```

Player pages are canonical per player (`player_uid`) and include:
- current season totals
- current regular-season and playoffs splits
- previous season totals (when older season CSVs exist in `data/`)
- merged season history across leagues when the same player name appears in multiple league files

Season player-stats category pages are also generated, so season pages can show the top 10 players plus a link to the full ranking table.

Then build or serve the site as usual:

```bash
make html
pelican --autoreload --listen --port 8000
```

Nightly GitHub Actions refreshes now include these same player-stat steps before the Pelican build, so the scheduled job updates:
- `data/player_stats.csv`
- `content/players/`
- `content/player-stats/`
- rendered site output

## Derived SQLite database

Rebuild the local SQLite database from committed CSV artifacts:

```bash
make refresh-sqlite
```

The database is written to `data/stats.db` and includes:
- `events`
- `game_stats`
- `team_stats`
- `league_stats`
- `player_stats`

This file is a derived local query layer and is not intended to be committed.

## Derived PostgreSQL database (Neon)

Rebuild the same derived tables in PostgreSQL using the current CSV artifacts:

```bash
export NEON_DATABASE_URL='postgresql://...'
make refresh-postgres
```

`refresh-postgres` writes:
- `events`
- `game_stats`
- `team_stats`
- `playoff_team_stats`
- `playdown_team_stats`
- `top4_team_stats`
- `league_stats`
- `player_stats`

The command expects `NEON_DATABASE_URL` (or `DATABASE_URL`) and is designed as the Postgres equivalent of `make refresh-sqlite`.

When `NEON_DATABASE_URL` (or `DATABASE_URL`) is set, `src.pipeline` now also syncs the derived payload tables to Postgres and `generate_markdown` reads markdown inputs from Postgres first.

## Switzerland (renderengine backend)

Use a schedule page URL (the scraper extracts `game_id` links) or pass explicit IDs:

```bash
python -m src.pipeline --backend switzerland --swiss_schedule_url "https://www.swissunihockey.ch/de/game-detail?game_id=1073873" --season ch-25-26 --phase regular-season
```

```bash
python -m src.pipeline --backend switzerland --swiss_game_ids "1073873,1073807" --season ch-25-26 --phase regular-season
```

Use renderengine schedule parameters with round traversal (recommended for L-UPL/NLB pages):

```bash
python -m src.pipeline --backend switzerland --swiss_league 24 --swiss_season 2025 --swiss_game_class 11 --swiss_group "Gruppe 1" --season ch-25-26 --phase regular-season
```

## Refresh current 1. FBL Herren season data

Defaults:
- `LEAGUE_ID=1890`
- `SEASON=25-26`
- `PHASE=regular-season`

Override:

```bash
make refresh-current-season LEAGUE_ID=1890 SEASON=25-26 PHASE=regular-season
```

Playoffs:

```bash
make refresh-current-season-playoffs GERMANY_PLAYOFFS_LEAGUE_CONFIG=config/leagues/germany-1fbl-playoffs.json
```

## Run tests

```bash
pytest -q
```

## Pipeline without scraping (local/e2e workflows)

```bash
python -m src.pipeline --season 25-26 --phase regular-season --skip_scrape
```

## Start server for development

```bash
pelican --autoreload --listen
```
