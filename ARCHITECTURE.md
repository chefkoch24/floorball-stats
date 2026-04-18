# Architecture

## 1. System Overview

`floorball-stats` is a Python-based analytics and publishing pipeline for multi-league floorball data.

Primary responsibilities:
- Fetch raw match event data from Saisonmanager API.
- Fetch raw match event data from additional league backends (Sweden, Switzerland, Finland, Czech Republic, Slovakia, Latvia).
- Compute per-game and per-team statistics.
- Compute cross-league player statistics and generate canonical player pages.
- Generate Markdown content for a static site.
- Build and serve the site with Pelican.
- Optionally visualize stats in a Dash dashboard.

Canonical runtime pipeline:
- `src/pipeline.py` (or `make refresh-current-season`).
- Full-repository refresh: `make refresh-all-leagues`.

Target data architecture:
- Neon/Postgres is the canonical runtime data store.
- Local SQLite is the local mirror for inspection and debugging.
- CSV/JSON artifacts remain in the repo as transitional compatibility, exports, and test fixtures while the migration completes.


## 2. High-Level Data Flow

```text
League backends (Germany, Sweden, Switzerland, Finland, Czech Republic, Slovakia, Latvia)
    -> src/pipeline.py + backend-specific scrapers
    -> Postgres / Neon runtime tables
    -> local SQLite mirror
    -> optional CSV/JSON compatibility exports
    -> src/generate_markdown.py (prefer Postgres inputs)
    -> content/<season>-<phase>/games/*.md + content/<season>-<phase>/teams/*.md
    -> src/build_player_stats.py
    -> player_stats table (+ optional data/player_stats.csv export)
    -> src/generate_player_markdown.py + src/generate_player_stats_index_markdown.py
    -> content/players/*.md + content/player-stats/*.md
    -> Pelican (pelicanconf.py + themes/my-theme)
    -> output/ static website
```


## 3. Repository Structure

- `src/`
  - Core scraping and stats engine modules.
- `content/`
  - Pelican source content by season and type (`teams`, `liga`, `games`, `players`, `player-stats`).
- `generated/`
  - Intermediate generated Markdown files from JSON stats.
- `data/`
  - Transitional CSV/JSON artifacts and exports.
  - Derived local SQLite store (`stats.db`) for local query-heavy workflows.
- `themes/my-theme/`
  - Custom Pelican theme and templates.
- `tests/`
  - Pytest unit tests for calculation primitives and engine behavior.
- `dashboard/`
  - Dash app for interactive exploration (`dashboard/app.py`).
- `database/`
  - Supabase upload helper (`database/supabase_connector.py`).
- `Makefile`, `pelicanconf.py`, `publishconf.py`, `tasks.py`
  - Build/run orchestration.


## 4. Core Components

### 4.1 Ingestion: `src/scrape.py`

Purpose:
- Reads a league schedule endpoint (`leagues/<id>/schedule.json`).
- Fetches each game detail (`games/<game_id>`).
- Normalizes event rows with team names and game metadata.
- Writes normalized events into the runtime data flow, with CSV export only as a compatibility artifact where still needed.

Key output:
- Canonical event records for database ingestion.


### 4.2 Stats Core: `src/stats_engine.py` + `src/team_stats.py`

`StatsEngine`:
- Registers stat functions (`name -> callable`).
- Applies them to team-filtered events.
- Supports:
  - `aggregate_stats()` for league averages.
  - `split_by_rank()` for playoff/playdown/top4 partitions.

`TeamStats`:
- Lightweight container with dict/json serialization helpers.


### 4.3 Stat Functions + Pipeline Runner: `src/run_stats_engine.py`

Contains:
- Large set of stat functions:
  - scoring, goals against, special teams, points at periods/minutes, close-game stats, penalties, etc.
- Main runtime orchestration (`if __name__ == "__main__":`)
  - registers all stat functions,
  - computes per-game home/away stats,
  - aggregates into per-team totals,
  - computes derived ratios,
  - writes JSON outputs:
    - `data/game_stats.json`
    - `data/team_stats.json`
    - `data/team_stats_enhanced.json`
    - `data/playoff_stats.json`
    - `data/playdown_stats.json`
    - `data/top4_stats.json`
    - `data/league_averages.json`


### 4.4 Shared Utilities: `src/utils.py`

Provides reusable helpers:
- Time normalization (`transform_in_seconds`).
- Points logic (`add_points`).
- Powerplay/boxplay penalty helpers.
- Safe division and slug generation.
- Markdown conversion helpers for game/team stats.

### 4.5 Orchestration: `src/pipeline.py`

Single entrypoint that executes:
- scrape events,
- compute stats JSON artifacts,
- sync Postgres and/or SQLite derived stores,
- generate markdown directly into website content tree.

Supports `--skip_scrape` for local/e2e runs from existing CSV.


### 4.6 Player Stats Pipeline

- `src/build_player_stats.py`
  - builds canonical player stats from backend artifacts, with optional CSV export
- `src/generate_player_markdown.py`
  - generates canonical player pages in `content/players/`
- `src/generate_player_stats_index_markdown.py`
  - generates season ranking pages in `content/player-stats/`

Integration invariants for new backends:
- Every backend must emit a stable season prefix (`de`, `se`, `ch`, `fi`, `cz`, `sk`, `lv`, `wfc`, etc.) because downstream player-stat exports, markdown generation, and cleanup logic key off that prefix.
- Every backend must register a `source_system` and league label in `src/build_player_stats.py::LEAGUE_INFO`; otherwise player stat export and player page generation will silently ignore the new backend.
- Event-only feeds are not enough for canonical player `games` counts. If the source exposes rosters or lineups, the backend must provide a second participation source and merge it with event rows.
- Participation rows must dedupe per match appearance, not just per player. For tournament/roster imports this means keeping `game_id` in the intermediate identity so multi-game appearances do not collapse into one phase row.
- Tournament seasons must be modeled explicitly. If a backend represents one tournament with multiple internal stages, the player page layer must be told whether to show season-phase splits or one combined tournament season.
- Merge behavior must preserve canonical player pages. Partial exports for one backend must merge into the global player history instead of overwriting club seasons from other leagues.
- Fallbacks must degrade narrowly. A single failed lineup/roster request must not discard an entire season-phase worth of player participation data.
- New backends should provide a focused `make refresh-<backend>` target and, if player data is supported, matching `refresh-player-stats-<backend>` and `refresh-player-pages-<backend>` targets.
- New backends should be database-first. CSV compatibility is allowed, but a backend is not integrated unless the Postgres/Neon path is correct.
- New backends are only considered integrated when tests cover:
  - raw event normalization,
  - player game counting from participation data,
  - merge behavior into canonical player pages,
  - tournament aggregation rules if applicable.

### 4.7 Markdown Generation: `src/generate_markdown.py`

Reads:
- `data/game_stats.json`
- `data/team_stats_enhanced.json`

Produces:
- markdown files in configurable output directories (canonical target: `content/<season>-<phase>/...`).

### 4.7a Derived SQLite Store: `src/build_sqlite.py`

Purpose:
- Keep a local file-based relational view of the current repository state.
- Load event artifacts into an `events` table.
- Load derived game/team/league stats emitted by the pipeline into queryable SQLite tables.
- Load player stats into `player_stats`.

Important constraint:
- SQLite is a derived local mirror, not the primary runtime source of truth.
- Postgres/Neon is the intended canonical runtime store.
- CSV is a compatibility and testing layer, not the target architecture for new integrations.


### 4.8 Site Build: Pelican (`pelicanconf.py`, `themes/my-theme`)

Responsibilities:
- Categorize and render season content.
- Custom templates for:
  - articles,
  - teams,
  - games,
  - category pages.
- Build static output via Pelican CLI / Make targets.


### 4.9 Visualization + DB

- `dashboard/app.py`
  - Dash app over `data/processed_stats.csv`.
  - Charts for goals, special teams, matchup matrix, and table filtering.
- `database/supabase_connector.py`
  - Optional ETL helper pushing team/stats data into Supabase.


## 5. Runtime Interfaces and Contracts

### Input Contract (event rows)
Expected columns used by stat functions include:
- `game_id`, `event_type`, `event_team`
- `home_team_name`, `away_team_name`
- `home_goals`, `guest_goals`
- `period`, `sortkey`
- optional: `penalty_type`, `goal_type`

Additional contract for backends that feed player stats:
- Required identity columns for event-based exports:
  - `game_id`
  - `home_team_name`
  - `away_team_name`
- Strongly preferred metadata:
  - `game_date`
  - `game_start_time`
  - `game_status`
  - `venue`
  - `venue_address`
- If the source supports tournament semantics, include:
  - `tournament_stage_type`
  - `tournament_stage_label`
  - `tournament_group`
  - `tournament_round`
  - `tournament_round_order`

These fields let downstream code:
- separate scheduled vs played matches,
- count player appearances from lineup feeds,
- keep elimination rounds in source order,
- aggregate tournament player pages without custom one-off parsing.

Database-first integration contract:
- New backends should satisfy the runtime table contracts first.
- CSV should be treated as a fixture/export surface for local testing and compatibility only.

### Output Contract (team stats)
Per-team objects include base counting metrics plus derived ratios, for example:
- `points`, `goals`, `goals_against`, `goal_difference`
- period split metrics
- powerplay/boxplay efficiencies
- ranking-related splits


## 6. Build and Execution Paths

Current expected commands:
- Site build:
  - `make html`
  - `make devserver`
- Data refresh target:
  - `make refresh-current-season`
  - `make refresh-all-leagues`

Testing:
- `pytest -q`

### 6.1 Backend-Readiness Checklist

Before treating a new backend as "works out of the box", verify all of the following:
- Scrape path:
  - `src.pipeline` can run the backend directly or via `--league_config`
  - the backend populates the runtime database path correctly
- Stats path:
  - `src/run_stats_engine.py` can build game/team outputs without backend-specific post-processing in templates
- Player stats path:
  - `src/build_player_stats.py` recognizes the prefix
  - `games` counts come from lineups/rosters when available, not only scoring events
  - per-match dedupe is correct
- Player page path:
  - `src.generate_player_markdown.py` merges partial backend exports into canonical player history
  - tournament seasons are combined when the competition is structurally one tournament
- Ranking page path:
  - `src.generate_player_stats_index_markdown.py` emits the right season/phase or tournament page shape
- Site path:
  - Pelican category labels and navigation make sense without hand-edited per-backend exceptions
- DB path:
  - `make refresh-sqlite` and `make refresh-postgres` can ingest the new artifacts without schema drift
- Compatibility path:
  - if CSV export still exists for that backend, it matches the expected naming and can be used as a fallback/test fixture
- Tests:
  - a regression test exists for the backend's player appearance counting and any tournament-specific aggregation rule


## 7. Testing Strategy

Current test suite (`tests/`) validates:
- Utility correctness (`safe_div`, `add_points`, penalty expansion, time conversion).
- Engine behavior (`aggregate_stats`, `split_by_rank` ordering).
- Core points logic in modular runner (`stat_points`, minute snapshots, away points, points-against map).
- End-to-end local pipeline (stats JSON + markdown creation under `content/...`).

Current status:
- Unit tests focus on deterministic calculation kernels.
- No integration/e2e snapshot test yet for full-season outputs.


## 8. Remaining Debt

1. Some refresh paths still rely on upstream third-party sites and APIs with inconsistent latency/blocking behavior, which is operational risk rather than architectural complexity.
