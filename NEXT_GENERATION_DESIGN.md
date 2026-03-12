# Next Generation Design: Multi-Country Floorball Analytics Platform

## 1. Objective
Build the next generation of the platform from a single-league (Germany-focused) system to a multi-country, multi-league analytics product that supports:

- Germany (existing)
- Sweden
- Finland
- Switzerland
- Czech Republic

while keeping one coherent user experience, comparable metrics, and country-specific rule handling.

---

## 2. Design Principles

1. **Provider-agnostic ingestion**
   Data collection must be decoupled from any single website/API.
2. **Canonical domain model**
   Normalize all leagues/countries into one internal schema.
3. **Rule-driven stats engine**
  Rule variations (e.g., points for OT/PS wins) are configuration, not hardcoded branching everywhere.
4. **Separation of storage layers**
   Keep raw payloads, normalized events, and aggregated stats separate for traceability.
5. **Incremental onboarding**
   Add one country/league at a time with adapter contracts and validation gates.

---

## 3. Target Architecture

## 3.1 High-Level Components

1. **League Registry**
   - Metadata table/config for country, league, season, phase, data provider, and rule profile.

2. **Provider Adapters**
   - One adapter per source system (e.g., Saisonmanager-like API, federation APIs, scraping fallback).
   - Standard interface:
     - `fetch_schedule(league, season, phase)`
     - `fetch_game(game_id)`
     - `fetch_standings(...)` (optional)

3. **Raw Ingestion Store**
   - Persist original API responses (JSON blobs + timestamp + source hash).
   - Enables replay and debugging when mappings break.

4. **Normalization Layer**
   - Maps source payloads to a canonical schema (`Game`, `Event`, `Team`, `StandingSnapshot`).
   - Includes identity mapping and de-duplication.

5. **Rules Engine**
   - Applies league-specific points and result semantics.
   - Example configurable behaviors:
     - regulation win points
     - overtime win/loss points
     - shootout win/loss points
     - whether draw is legal

6. **Stats Engine**
   - Computes game/team/league KPIs on canonical events.
   - Reuses current metric set where possible.

7. **Content Generator**
   - Generates markdown/data artifacts by country/league/season.
   - Pelican templates remain a rendering layer, not business logic.

8. **QA & Observability Layer**
   - Data quality checks, anomaly alerts, and per-league validation scorecards.

---

## 4. Canonical Data Model (Core)

## 4.1 Dimensions
- `country`
- `federation`
- `league`
- `season`
- `phase` (regular season, playoffs, playdowns)
- `team`
- `arena` (optional)

## 4.2 Fact Entities

### `Game`
- `game_uid` (global internal id)
- `provider_game_id`
- `country_code`
- `league_code`
- `season_code`
- `phase_code`
- `game_datetime_utc`
- `status` (scheduled/live/ended)
- `home_team_uid`
- `away_team_uid`
- `home_goals_final`
- `away_goals_final`
- `result_type` (regulation, overtime, shootout, forfeit)

### `Event`
- `event_uid`
- `game_uid`
- `event_type` (goal, penalty, timeout, etc.)
- `event_team_uid`
- `period`
- `clock_time`
- `sort_key`
- `goal_type`
- `penalty_type`
- `home_goals_after`
- `away_goals_after`

### `RuleProfile`
- `rule_profile_id`
- `regulation_win_points`
- `overtime_win_points`
- `overtime_loss_points`
- `shootout_win_points`
- `shootout_loss_points`
- `draw_points`
- `supports_shootout`
- `supports_overtime`

---

## 5. Rule Abstraction Strategy

Introduce a `RuleProfile` per league-season and make all points/result calculations depend on it.

Example profiles:

- **Profile A (current-like)**
  - Win reg: 3
  - Win OT/PS: 2
  - Loss OT/PS: 1
  - Loss reg: 0

- **Profile B (if league differs)**
  - Alternative points distribution loaded from registry.

Implementation detail:
- Current `run_stats_engine.py` scoring functions should accept `rule_profile` context.
- No country-specific if/else in templates.

---

## 6. Multi-Country Ingestion Strategy

## 6.1 Adapter Contract
Each adapter must return canonical intermediate objects (or directly normalized DataFrames) with complete date, game status, and period/event semantics.

## 6.2 Onboarding Steps per Country
1. Identify primary authoritative source (official federation/provider).
2. Build adapter with contract tests.
3. Map teams and leagues into global IDs.
4. Validate 1 full season replay.
5. Enable incremental daily updates.

## 6.3 Fallback Strategy
- Primary API unavailable -> cached latest raw payloads + retry queue.
- Provider schema change -> adapter versioning + canary validation before full run.

---

## 7. Scaling Approach

## 7.1 Compute
- Shift from single monolithic run to per-league jobs.
- Parallel execution by `(country, league, season, phase)` key.
- Queue-based orchestration (e.g., Celery/RQ/Prefect/Airflow).

## 7.2 Storage
Use layered storage:
- `raw/` for provider payloads
- `normalized/` canonical parquet/csv
- `aggregates/` team/game/league stats
- `content/` markdown output

For long-term scale, move from flat files to database-backed warehouse:
- PostgreSQL for operational metadata + IDs
- object storage for raw payloads
- optional DuckDB/Parquet for analytics speed

## 7.3 Caching & Incremental Updates
- Only recalculate affected league-season when new games arrive.
- Recompute full season only on demand.
- Keep deterministic snapshot version (timestamp/hash).

---

## 8. UI / Product Design for Multi-Country

## 8.1 Navigation
- Country -> League -> Season -> Phase
- Keep current season grouping (Regular/Playoffs) but nested under country and league.

## 8.2 Comparability Layer
- Define a "Core KPI Set" available everywhere:
  - Points, PpS, Goals/Game, Against/Game, Goal Diff/Game, PP%, BP%, W/L/OT/PS
- Show additional local metrics only when available.

## 8.3 Locale
- Country flag, language preference, and local naming support.
- Internal keys remain English/canonical.

---

## 9. Data Quality & Testing

## 9.1 Data Quality Checks
Per run:
- final score consistency with last goal event
- points consistency with rule profile
- powerplay opportunities <= eligible penalty opportunities (with adjusted logic)
- no missing game dates for ended games
- no duplicated game IDs in league-season

## 9.2 Test Pyramid
1. Unit tests for scoring and rule handling
2. Adapter contract tests (mock provider payloads)
3. E2E pipeline tests for each onboarded provider
4. Snapshot tests for generated markdown fields/templates

## 9.3 Monitoring
- job success/failure dashboard
- anomaly alerts (sudden drop in game count, all-null fields, etc.)

---

## 10. Rollout Plan

## Phase 1: Foundation (2-4 weeks)
- Introduce `League Registry` + `RuleProfile`
- Refactor scoring logic to rule-driven model
- Keep Germany as baseline compatibility target

## Phase 2: Provider Framework (2-4 weeks)
- Build adapter interface + raw store
- Migrate existing Germany ingestion into adapter pattern

## Phase 3: First International Pilot (3-5 weeks)
- Add one country (recommended: Switzerland or Finland, depending on API quality)
- Deliver full season rendering and validation

## Phase 4: Additional Countries (rolling)
- Add Sweden + Czech Republic adapters
- Improve normalization dictionaries and entity mapping

## Phase 5: Platform Hardening
- orchestration, retries, metrics, quality gates
- optional database backend and API layer for frontend

---

## 11. Recommended Repo Refactoring

1. `src/providers/`
   - `base.py` (adapter interface)
   - `de_saisonmanager.py`
   - `se_*.py`, `fi_*.py`, `ch_*.py`, `cz_*.py`

2. `src/rules/`
   - `profiles.py`
   - `engine.py`

3. `src/normalization/`
   - canonical mappers and ID resolvers

4. `src/pipelines/`
   - per-league orchestration jobs

5. `config/leagues.yaml`
   - country/league/season/phase + provider + rule profile

---

## 12. Risks and Mitigations

1. **Provider schema volatility**
   - Mitigation: adapter versioning + payload snapshots + contract tests
2. **Team identity collisions across countries**
   - Mitigation: global team UID + alias table
3. **Rule drift across seasons**
   - Mitigation: `rule_profile` attached to league-season, not just league
4. **Template breakage due to missing fields**
   - Mitigation: fallback-safe template rendering + per-field existence checks

---

## 13. Immediate Next Actions

1. Implement `League Registry` + `RuleProfile` config and wire current Germany league through it.
2. Extract current Germany ingestion into a formal adapter class.
3. Refactor scoring functions to consume rule profile object.
4. Add one pilot non-Germany league end-to-end with validation report.
5. Introduce country/league routing in navigation and content tree.

---

## 14. Success Criteria

The next generation is successful when:
- at least 3 countries are fully supported end-to-end,
- all supported leagues produce consistent game/team/league outputs,
- core KPI comparability works across countries,
- onboarding a new league requires only adapter + config + tests (no core rewrites).
