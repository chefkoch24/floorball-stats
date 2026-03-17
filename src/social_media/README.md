# Social Media Approach

## Objective

Keep all social-media-specific logic separate from scraping, stats calculation, and website generation.

This folder is the home for:

- social-only derived tables
- social export pipelines
- image and GIF renderers
- social CLI entrypoints

If a module exists only to create Instagram or other social assets, it should live under `src/social_media/`.

## Design Rule

Core product logic stays in the main application:

- scraping
- canonical stats calculation
- markdown generation
- website rendering

Social logic stays here:

- ranking selection
- social-specific table transforms
- image layout
- animation behavior
- output naming and export flows

This keeps the social layer maintainable and prevents it from leaking into the stats engine.

## Current Structure

```text
src/social_media/
  tables.py
  render_home_away.py
  render_cross_country_rankings.py
  pipelines/
    home_away.py
    cross_country_rankings.py
  cli/
    render_home_away.py
    render_cross_country_rankings.py
```

### Responsibilities

- `tables.py`
  - builds social-specific derived artifacts from existing stats
- `render_home_away.py`
  - renders the home/away split post
- `render_cross_country_rankings.py`
  - renders cross-country ranking posts and GIFs
- `pipelines/`
  - orchestrates social export flows
- `cli/`
  - user-facing runnable entrypoints

## Data Flow

### Home / Away Posts

Canonical flow:

```text
team_stats_enhanced.json + game_stats.json
  -> social_media.tables.build_home_away_split_table()
  -> home_away_split_table.json
  -> social_media.pipelines.home_away
  -> social_media.render_home_away
  -> PNG export
```

Important:

- home/away `PPG` is derived from actual home/away game counts in `game_stats.json`
- do not infer home/away game counts from total games

### Cross-Country Rankings

Current flow:

```text
content/*-25-26-regular-season/teams/*.md
  -> social_media.render_cross_country_rankings.load_entries()
  -> sorted top 10 entries
  -> static PNG or animated GIF
```

Reason:

- the per-team markdown files already expose the current regular-season metrics across countries
- this is sufficient for the current cross-country ranking posts

Longer-term preferred direction:

- move cross-country ranking inputs to dedicated structured data artifacts instead of parsing markdown

## Rendering Rules

### Static Feed Posts

Current default:

- `1080x1350`

Used for:

- home/away tables
- cross-country ranking posts

### Animated Posts

Current default:

- `1080x1920`

Rule:

- animated exports should use story dimensions

## Ranking Animation Logic

For ranking countdown GIFs:

1. keep all rows in their final ranking positions
2. reveal entries from the lowest visible rank upward
3. for top 10 countdowns:
   - show `10` first in the bottom slot
   - then reveal `9`
   - then `8`
   - continue until `1` appears last at the top
4. do not reorder rows mid-animation

This preserves suspense without causing layout jumps.

## Ordering Rule

For social ranking reveals:

- reveal in reverse rank order for suspense

For final static ranking tables:

- render in standard rank order unless the format explicitly requires a countdown view

Implementation note:

- countdown animations may still end on a final frame with the standard ranking order if that is the editorial goal

## Formatting Rule

Decimal formatting for social outputs:

- always show two decimal places
- use comma as decimal separator

Examples:

- `70,00`
- `79,49`
- `2,46`

## Current Output Conventions

Examples:

- `output/social/home-away-se-25-26-regular-season-1080x1350.png`
- `output/social/top10-powerplay-25-26-cross-country-1080x1350.png`
- `output/social/top10-penalty-kill-25-26-cross-country-1080x1920.gif`

Keep filenames descriptive and include:

- format/topic
- season scope
- cross-country or league scope
- image dimensions when relevant

## Compatibility

Top-level wrappers currently still exist:

- `src/render_social.py`
- `src/render_penalty_kill_ranking.py`
- `src/social_tables.py`

They should remain thin wrappers only.

New implementation work should go into `src/social_media/`, not back into the top-level `src/` namespace.

## Future Guidance

When adding a new social format:

1. add any social-specific transform under `tables.py` or a new social data module
2. add renderer logic under `src/social_media/`
3. add a pipeline under `src/social_media/pipelines/`
4. add a CLI under `src/social_media/cli/`
5. keep canonical application code untouched unless a truly shared data artifact is required

## Recommended Next Cleanup

1. add `common.py` for shared colors, fonts, sizing, and drawing helpers
2. move cross-country markdown parsing to a structured JSON artifact
3. add tests for animated GIF frame ordering
