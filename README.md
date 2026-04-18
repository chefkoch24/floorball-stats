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

Target architecture:
- Neon/Postgres is the canonical runtime data layer.
- Local SQLite is the local mirror for querying and debugging.
- CSV exists as a compatibility/testing/export layer while the migration is still in progress.

During refreshes, the pipeline also maintains a derived local SQLite database at `data/stats.db`.

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

## Player pages

Preferred mode: generate player pages from the database-backed pipeline outputs.

Current commands still materialize `data/player_stats.csv` as a compatibility artifact, then generate unique player pages plus season player-stats indexes:

```bash
make refresh-player-stats
make refresh-player-pages
```

Player pages are canonical per player (`player_uid`) and include:
- current season totals
- current regular-season and playoffs splits
- previous season totals
- merged season history across leagues when the same player identity appears across multiple backends

Important direction:
- do not design new backends around CSV as the primary integration surface
- design them so the database tables are correct first
- keep CSV support only as a transitional export/test path until the migration is complete

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

Rebuild the local SQLite database as a local mirror of the current repository artifacts:

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

Rebuild the canonical runtime tables in PostgreSQL:

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

Preferred operating mode:
- set `NEON_DATABASE_URL` (or `DATABASE_URL`)
- let `src.pipeline` sync derived payload tables to Postgres
- let markdown generation and player-page generation read from Postgres first

Operational rule:
- treat Postgres/Neon as the canonical source for runtime generation
- use SQLite for local inspection
- use CSV only for fallback, testing, and transitional compatibility

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

## WFC / IFF competitions

Public league-organizer results can be pulled from the Sportswik app host:

```bash
python -m src.pipeline --backend wfc --wfc_league_organizer_id 187 --season wfc-2024 --phase playoffs
```

For a classical world championship structure, use:

```bash
python -m src.pipeline --backend wfc --wfc_league_organizer_id 187 --season wfc-2024 --phase regular-season
python -m src.pipeline --backend wfc --wfc_league_organizer_id 187 --season wfc-2024 --phase playoffs
```

Example config:

```bash
python -m src.pipeline --league_config config/leagues/iff-mens-wfc-2024.json
```

The bundled make target runs both tournament phases:

```bash
make refresh-wfc
make refresh-wfc-full
```

Current limitation:
- the public `leagueorganizerapi` feed gives schedule/result-level game data,
- authenticated game-overview/event enrichment is enabled when you provide both `IFF_API_ACCESS_TOKEN` and `IFF_API_REFRESH_TOKEN`,
- the scraper auto-refreshes the access token through `https://iff-api.azurewebsites.net/api/jwtapi/refreshtoken`,
- without those env vars, the WFC backend still falls back to result-only pages and standings.

To enable full WFC event timelines:

```bash
export IFF_API_ACCESS_TOKEN='...'
export IFF_API_REFRESH_TOKEN='...'
make refresh-wfc-full
```

## Adding a new backend or pipeline

If we add another league, tournament, or external backend later, it should satisfy this checklist before we consider it integrated.

### Required plumbing

- Add a dedicated `make refresh-<backend>` target.
- Prefer a config file under `config/leagues/` so the backend can run through `src.pipeline --league_config ...`.
- Make the database write path work first.
- Raw CSV export is optional/transitional and should not be treated as the primary contract for new work.
- If CSV export exists, keep the canonical naming shape:

```text
data/data_<prefix>-<season>_<phase>.csv
```

Examples:
- `data/data_se-25-26_regular_season.csv`
- `data/data_wfc-2024_playoffs.csv`

- Use a stable backend prefix. That prefix is not cosmetic. It drives:
  - player-stats export selection,
  - markdown generation,
  - cleanup behavior,
  - tournament handling.

### Database-first rule

For every new backend, the primary definition of success is:
- `events`
- `game_stats`
- `team_stats`
- `league_stats`
- `player_stats`

are correct in Postgres/Neon.

Only after that should we care about CSV compatibility exports.

### Player stats rules

For a backend to work outside the box with player pages, these rules must hold:

- Register the prefix in `src/build_player_stats.py::LEAGUE_INFO`.
- If the source has lineups/rosters, use them for `games` counting.
- Do not count appearances from goals/assists/penalties only.
- Deduplicate participation by match, not just by player identity.
- If the backend is a tournament, decide explicitly whether:
  - the player page should show regular/playoff-style splits, or
  - the season should be combined as one `tournament` row.

Current rule:
- `wfc-*` seasons are treated as one tournament season on player pages.

- Partial backend exports must merge into canonical player history instead of overwriting club seasons from other leagues.

### Failure behavior

- Narrow fallbacks only. One failed lineup/roster request must not wipe an entire backend season back to event-only player counts.
- Keep failures visible in logs. Silent broad fallback makes backends look integrated when they are not.

### Minimum test coverage for a new backend

Add regression tests for:
- event normalization
- player appearance counting from lineup/roster data
- merge into canonical player pages
- tournament aggregation, if the competition is structurally one tournament

### Definition of done

A new backend is only "plugged in" when all of these work without manual template fixes:
- `make refresh-<backend>`
- `make refresh-player-stats-<backend>` if the backend supports player data
- `make refresh-player-pages-<backend>`
- `make refresh-sqlite`
- `make refresh-postgres`
- `make html`

If any of those require one-off local edits, the backend is not integrated yet.

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
