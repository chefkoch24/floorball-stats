# Scorer Names Feasibility Analysis

Date: 2026-03-16

## Executive Summary

Adding goal scorers with player names for every game is **feasible**, but **not possible with the current pipeline as-is**.

Today, game pages do not receive scorer-name fields. We need:
1. scraper-level extraction of scorer/assist names (or mapping),
2. propagation into `game_stats.json`,
3. rendering in `themes/my-theme/templates/game.html`.

## Current State (Per League)

### Germany (Saisonmanager)

Status: **Possible with extra mapping step**

Evidence:
- `data/data_25-26_regular_season.csv` contains `number` and `assist` (jersey numbers), but no scorer names.
- API `games/{id}` event payload has no `player_name` in events.
- API `games/{id}` includes `players.home[]` / `players.guest[]` with `trikot_number` + `player_name`.

Conclusion:
- We can map event jersey numbers (`number`, `assist`) to player names via the game lineup payload.
- This is implementable, but requires scraper enhancement.

### Sweden (StatsApp API)

Status: **Possible**

Evidence:
- Live API event keys include:
  - `PlayerName`
  - `PlayerAssistName`
  - `PlayerShirtNo`
  - `PlayerAssistShirtNo`
- Current scraper (`src/scrape_sweden.py`) does not persist these fields.

Conclusion:
- Straightforward: persist available name fields into CSV and downstream game stats.

### Switzerland (Swiss Unihockey)

Status: **Likely possible**

Evidence:
- `src/scrape_switzerland.py` parses event table rows as:
  - `minute_raw, event_text, team_name, _player = cells[:4]`
- `_player` is currently discarded.

Conclusion:
- Scorer name appears to be already present in parsed cells and can be stored.
- Assist availability depends on source row text format.

### Finland (F-Liiga site)

Status: **Likely possible**

Evidence:
- Parser uses `.event-home .scorer` / `.event-away .scorer` to determine scoring side.
- Current code uses scorer node presence, not scorer text.

Conclusion:
- Scorer names are likely available in DOM and can be extracted.
- Assist availability depends on match event markup.

### Czech Republic (ČEZ Extraliga)

Status: **Possible**

Evidence:
- Timeline right column includes text like:
  - `0:1 Armands SAVINS (Jēgers)`
  - `1:1 Adam BUREŠ (Karel)`
- Current scraper keeps score/team/timing but not parsed names.

Conclusion:
- Scorer and assist names can be parsed from timeline text.

### Slovakia (SZFB)

Status: **Likely possible, but unverified live in this run**

Evidence:
- Parser reads event cells from match overview tables and currently stores only structured metrics.
- Source connection timed out during direct live validation in this run.

Conclusion:
- Based on parser structure, scorer name extraction is likely possible from event cell text.
- Needs live verification due source reliability/timeouts.

### Latvia (ELVI)

Status: **Likely possible**

Evidence:
- Parser reads `details = cells[3].get_text(...)` in event rows.
- For goals, this details field is a likely location for player info.

Conclusion:
- Scorer names can likely be parsed from details text.
- Needs parser update and validation against multiple match pages.

## What Is Not Possible Right Now

With current code and data flow, it is **not possible** to show scorer names on game pages for all leagues, because:
- most scrapers do not persist scorer-name fields,
- `run_stats_engine` does not build scorer lists into `game_stats`,
- `game.html` has no scorer section.

## Required Implementation Changes

1. Add normalized scorer fields in event rows:
- `scorer_name`
- `assist_name` (nullable)
- optional: `scorer_number`, `assist_number`

2. Update each scraper:
- Germany: map `number` / `assist` via game lineup (`players.home/guest`).
- Sweden: persist `PlayerName`, `PlayerAssistName`.
- Switzerland/Finland/Czech/Slovakia/Latvia: parse text/DOM and populate normalized fields.

3. Extend `run_stats_engine`:
- build per-game scorer timeline list from goal events in chronological order,
- store as `goal_scorers_json` (or CSV fields) in each `game_stat`.

4. Extend `themes/my-theme/templates/game.html`:
- add a “Scorers” panel listing each goal:
  - minute,
  - team,
  - scorer name,
  - assist (if available).

## Risk / Data Quality Notes

- Some providers may miss assists or some scorer names for specific event types (PS/OT markers, own goals, malformed rows).
- A fallback string like `Unknown` should be supported.
- Germany mapping depends on lineup completeness and number consistency.

## Recommendation

Proceed league-by-league in this order for fastest visible impact:
1. Sweden (lowest friction, names already present in API),
2. Czech + Switzerland,
3. Finland + Latvia,
4. Germany (number->name mapping),
5. Slovakia (after reliable source verification).

