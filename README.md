# README

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Seasons and league configs

Every league reads its season-specific IDs and URLs from one config file per phase:

```text
config/leagues/<league>-<season>.json           # regular season
config/leagues/<league>-<season>-playoffs.json  # playoffs
```

The Makefile only knows `CURRENT_SEASON` (currently `26-27`) and derives all config paths from it.
Any league target can be re-run for an older season, e.g. `make refresh-sweden CURRENT_SEASON=25-26`.

### Season rollover checklist

1. Copy the previous season's configs to `config/leagues/<league>-<new season>[-playoffs].json` and update IDs/URLs/years:
   - Germany: Saisonmanager league id (link "1. FBL Herren" on saisonmanager.de, e.g. `/fd/2447-1-fbl-herren`); the playoffs league id is published later, keep `"league_id": null` until then.
   - Sweden: SSL Herrar `competition_id` of the new season (the playoffs config points at the same id, playoff series are resolved automatically).
   - Switzerland: `swiss.season` (start year).
   - Finland: `playoff_start_date` (day after the last regular-season round).
   - Czech Republic: `competitionFisId` of the season in the schedule URL plus `season_start_year`.
   - Slovakia: tournament id in the schedule URL plus `regular_season_end_date`.
   - Latvia: year in the calendar URL plus `season_start_year`.
2. Bump `CURRENT_SEASON` in the `Makefile`.
3. Prepend the season to `SEASONS` in `pelicanconf.py` (navigation, home page and article paths follow automatically).
4. Run `make refresh-all-leagues`.

Keep the old configs: player-stat roster lookups for past seasons still read them.
Before rolling over, pin Sweden's finished playoffs config to the explicit series ids
(`competition_ids`, see `sweden-ssl-25-26-playoffs.json`): the API only lists current-season competitions.

## Germany: Saisonmanager API key

Since summer 2026 the Saisonmanager API requires a personal key (request it on saisonmanager.de, "API-Zugang").
Export it as `SAISONMANAGER_API_KEY` (sent as `X-Api-Key`); the GitHub workflow reads the repository secret of the same name.

Without the key, `src/scrape_saisonmanager_web.py` reads the public saisonmanager.de pages instead
(headless Chrome via Playwright; locally `pip install -r requirements.txt` plus an installed Google Chrome,
or `playwright install chromium`). It returns the same JSON shape as the API, so the pipeline is unchanged.
To keep the load low it renders one page per finished game, waits between renders, skips images/fonts,
takes unplayed games from the schedule page and caches finished games in `.cache/saisonmanager/`
(re-read only within 3 days after the game). Player-stat lineups use that cache only.

## Czech Republic: local job instead of CI scraping

ceskyflorbal.cz (Cloudflare) answers datacenter IPs such as GitHub runners with 403, while a regular
connection works (its robots.txt only disallows `/admin`). So the work is split:

- `make refresh-czech-local` (needs `NEON_DATABASE_URL`) scrapes the Czech league into Neon using a temp dir
  (the working copy stays untouched) and rebuilds only the Czech player stats (`--prefixes cz`).
- The nightly workflow runs `make refresh-all-leagues CZECH_PIPELINE_ARGS="--events_source db"`, i.e. it builds
  the Czech pages from the events in Neon instead of scraping.
- `make install-czech-job` installs a macOS launchd agent that runs `scripts/czech_refresh_job.sh` daily at 22:00
  (a missed run starts when the Mac wakes up). Log: `~/Library/Logs/floorball-czech-refresh.log`.
  Remove it with `make uninstall-czech-job`.

If the Mac does not run, the site keeps the last synced Czech data.

## Canonical pipeline (single league)

```bash
make refresh-current-season
```

This runs the new unified module entrypoint:

```bash
python -m src.pipeline --league_config config/leagues/germany-1fbl-26-27.json
```

German playoffs via config:

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
- `make refresh-search-index`
- `make html`

A failing step is reported as `[WARN] step failed: <target>` and never blocks the remaining leagues.
Smart targets try the playoffs first; until a league's playoffs are published that step fails with
"No playoffs games found" (or similar) and the regular season is refreshed instead.

Target architecture:
- Neon/Postgres is the canonical runtime data layer.
- Local SQLite is the local mirror for querying and debugging.
- CSV exists as a compatibility/testing/export layer while the migration is still in progress.

During refreshes, the pipeline also maintains a derived local SQLite database at `data/stats.db`.

`make refresh-everything` is an alias for the same flow.

## Sweden (StatsApp backend)

Pipeline entrypoint with Sweden backend:

```bash
python -m src.pipeline --backend sweden --competition_id 44033 --season se-26-27 --phase regular-season
```

Make target:

```bash
make refresh-sweden
```

Playoffs / smart refresh:

```bash
make refresh-sweden-playoffs
make refresh-sweden-smart
```

## Slovakia (SZFB backend)

Pipeline entrypoint with Slovakia backend:

```bash
python -m src.pipeline --league_config config/leagues/slovakia-extraliga-26-27.json
```

Make target:

```bash
make refresh-slovakia
```

## Latvia (floorball.lv backend)

Pipeline entrypoint with Latvia backend:

```bash
python -m src.pipeline --league_config config/leagues/latvia-elvi-vv-26-27.json
```

Make target:

```bash
make refresh-latvia
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
python -m src.pipeline --backend switzerland --swiss_league 24 --swiss_season 2026 --swiss_game_class 11 --swiss_group "Gruppe 1" --season ch-26-27 --phase regular-season
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

Uses `config/leagues/germany-1fbl-$(CURRENT_SEASON).json` (needs `SAISONMANAGER_API_KEY`):

```bash
make refresh-current-season
make refresh-current-season CURRENT_SEASON=25-26
```

Playoffs:

```bash
make refresh-current-season-playoffs
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
