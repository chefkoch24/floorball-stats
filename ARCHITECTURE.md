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


## 2. High-Level Data Flow

```text
League backends (Germany, Sweden, Switzerland, Finland, Czech Republic, Slovakia, Latvia)
    -> src/pipeline.py + backend-specific scrapers
    -> data/data_<season>_<phase>.csv
    -> src/run_stats_engine.py
    -> data/*.json
    -> src/generate_markdown.py
    -> content/<season>-<phase>/games/*.md + content/<season>-<phase>/teams/*.md
    -> src/build_player_stats.py
    -> data/player_stats.csv
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
  - Intermediate and processed CSV/JSON artifacts.
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
- Writes an event table CSV.

Key output:
- Raw event CSV under `data/`.


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
- generate markdown directly into website content tree.

Supports `--skip_scrape` for local/e2e runs from existing CSV.


### 4.6 Player Stats Pipeline

- `src/build_player_stats.py`
  - builds `data/player_stats.csv` across all available league CSVs
- `src/generate_player_markdown.py`
  - generates canonical player pages in `content/players/`
- `src/generate_player_stats_index_markdown.py`
  - generates season ranking pages in `content/player-stats/`

### 4.7 Markdown Generation: `src/generate_markdown.py`

Reads:
- `data/game_stats.json`
- `data/team_stats_enhanced.json`

Produces:
- markdown files in configurable output directories (canonical target: `content/<season>-<phase>/...`).


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
