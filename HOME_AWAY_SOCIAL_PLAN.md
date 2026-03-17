# Home/Away Split Social Plan

## Objective

Build a first "beyond the standings" feature that turns the existing regular-season team stats into:

1. a reusable `Home / Away Split` league table for all supported leagues
2. a clean data artifact that can drive website rendering
3. a template-based image generation flow for Instagram posts, stories, and carousel slides

This should be built entirely on top of the stats already present in `data/team_stats_enhanced.json`.

## Why Start Here

The home/away split is a strong first social feature because it:

- uses stats already in the pipeline
- is easy to explain
- creates clear editorial hooks
- works across all leagues
- maps cleanly into both web tables and visual social templates

Example editorial angles:

- Fortress at home
- Travels well
- Balanced team
- Home-dependent contender
- Better away than at home

## Available Input Stats

For each team we already have:

- `rank`
- `points`
- `home_points`
- `away_points`
- `goals_home`
- `goals_against_home`
- `goals_away`
- `goals_against_away`
- `goal_difference`
- `goals`

These are sufficient for the first version.

## Derived Fields

For each team, compute:

```text
home_diff = goals_home - goals_against_home
away_diff = goals_away - goals_against_away
split_points = home_points - away_points
split_diff = home_diff - away_diff
```

Optional later additions:

```text
home_share = home_points / points
away_share = away_points / points
home_points_per_game
away_points_per_game
```

Those are not required for v1.

## Canonical Output Schema

Create a league-level derived artifact with one row per team:

```json
{
  "table_type": "home_away_split",
  "season": "25-26",
  "phase": "regular-season",
  "rows": [
    {
      "rank": 1,
      "team": "Example Team",
      "points": 42,
      "home_points": 24,
      "away_points": 18,
      "goals_home": 63,
      "goals_against_home": 41,
      "goals_away": 54,
      "goals_against_away": 49,
      "home_diff": 22,
      "away_diff": 5,
      "split_points": 6,
      "split_diff": 17,
      "home_record_label": "63:41",
      "away_record_label": "54:49"
    }
  ]
}
```

Suggested output path:

- `data/home_away_split_table.json`

If league- and season-specific output paths are preferred later, keep the structure but namespace per run.

## Ranking Logic

For v1, do not rank by split directly.

Sort rows by the standard sporting order:

1. `points` descending
2. `goal_difference` descending
3. `goals` descending

Reason:

- keeps the table anchored to the main standings
- makes the home/away comparison easier to scan
- avoids overemphasizing extreme but less relevant splits

Future sort variants:

- `home_points` descending
- `away_points` descending
- `abs(split_points)` descending

## Web Table Specification

Proposed columns:

- `Rank`
- `Team`
- `Pts`
- `Home Pts`
- `Away Pts`
- `Home GF:GA`
- `Away GF:GA`
- `Home Diff`
- `Away Diff`
- `Split`

Rendering rules:

- `Split` should be signed: `+8`, `0`, `-3`
- color-code `Split`
- optionally bold the stronger side between `Home Pts` and `Away Pts`
- keep labels short for mobile readability

Interpretation:

- positive `Split`: stronger at home
- zero `Split`: balanced
- negative `Split`: stronger away

## Content and UX Positioning

Site section:

- `Beyond The Standings`

First advanced table:

- `Home / Away Split`

Subtitle:

- `How differently teams perform at home and on the road`

This should sit on league pages for regular-season content.

## Instagram-Specific Output

The same table data should power a smaller, image-friendly view.

### Post Variant

Recommended columns:

- `Team`
- `Home Pts`
- `Away Pts`
- `Split`
- `Home Diff`
- `Away Diff`

This avoids a table that is too wide for square output.

### Story Variant

Use a top-5 or top-6 crop of the table with a stronger headline:

- Strongest at home
- Best away teams
- Biggest home/away gaps

### Carousel Variant

Split the concept into slides:

1. Intro slide: what the table measures
2. Full league split table
3. Biggest home strengths
4. Best away teams
5. Balanced teams

## Template-Based Image Generation

The end goal is not manual design. The end goal is an automated image pipeline using templates.

### Proposed Architecture

1. compute the `home_away_split_table` JSON artifact
2. normalize it into a presentation-friendly payload
3. feed that payload into one or more visual templates
4. render PNG images automatically

### Suggested Payload for Templates

```json
{
  "template": "instagram-home-away-square",
  "title": "Home / Away Split",
  "subtitle": "Regular Season",
  "league": "1. FBL Herren",
  "season": "25-26",
  "rows": [
    {
      "team": "Example Team",
      "home_points": 24,
      "away_points": 18,
      "split_points": 6,
      "home_diff": 22,
      "away_diff": 5
    }
  ]
}
```

### Template Set

Create a small template family instead of a single image:

- `instagram-home-away-square`
- `instagram-home-away-story`
- `instagram-home-away-carousel-table`
- `instagram-home-away-carousel-insights`

### Visual Rules

- strong title area
- compact table layout
- league and season label
- color-coded `Split`
- consistent team alignment
- no more than 6 to 8 teams on a single image unless typography still holds

## Template Definition Plan

The template should feel close to the website rather than like a separate social brand system.

### Goal

Define one reusable visual language that can render:

- square post images
- story images
- carousel table slides

while staying visually aligned with the current site.

### Step 1: Extract the Existing Site Language

Use the current site and screenshots to define:

- background treatment
- card radius
- border style
- table row spacing
- header hierarchy
- accent colors
- typography sizes and weights
- light and dark treatment choice

Output of this step:

- a small set of visual tokens for social templates

### Step 2: Fix the Social Canvas Sizes

Start with these canvas targets:

- square post: `1080 x 1080`
- story: `1080 x 1920`
- carousel slide: `1080 x 1350` or `1080 x 1080`

Recommendation:

- use `1080 x 1350` for feed carousels because it uses more vertical space
- use `1080 x 1920` for stories

### Step 3: Define the Base Layout Blocks

Each template should be assembled from the same blocks:

- top brand header
- main title
- league and season metadata
- table container
- optional insight footer

This avoids redesigning every format separately.

### Step 4: Define Table Compression Rules

The website table cannot be copied 1:1 into Instagram.

Template rules should define:

- max number of rows per image
- which columns survive in square format
- which columns move to story or carousel variants
- minimum font size
- team name truncation behavior

Recommended first limits:

- square: 6 rows
- story: 8 rows
- carousel table slide: full league if readable, otherwise 2 slides

### Step 5: Define the Insight Layer

Every image should have one editorial takeaway beyond the raw table.

Examples:

- `Leipzig is clearly stronger at home`
- `Team X performs almost identically home and away`
- `Team Y is one of the few stronger road teams`

This should be generated from `split_points` thresholds, not written manually.

### Step 6: Choose the Rendering Stack

For website-like output, the best default is:

- HTML/CSS templates
- rendered to PNG

Reason:

- easiest to match the current site styling
- fastest path from existing CSS ideas to social images
- flexible for iteration after reviewing first exports

### Step 7: Create a Template Spec Before Coding

Before implementing rendering, define for each template:

- canvas size
- content blocks
- row count
- column set
- font sizes
- overflow behavior
- export filename pattern

This should be written as a compact spec for:

- `instagram-home-away-square`
- `instagram-home-away-story`
- `instagram-home-away-carousel-table`

### First Template Spec: Website-Like Feed Post

Primary template:

- `instagram-home-away-feed`

Canvas:

- `1080 x 1350`

Visual direction:

- mirror the main site light theme
- reuse the site color tokens from `themes/my-theme/static/css/style.css`
- use a page background plus a single large panel card, like the site category pages

Layout blocks:

1. site-style brand header
2. chip row with league and season
3. large white panel card
4. table header and compact data table
5. bottom takeaway card

Table rules:

- max `6` rows
- columns: `Team`, `Home`, `Away`, `Split`, `H Diff`, `A Diff`
- secondary record line under each team: `home_GF:GA / away_GF:GA`
- signed values for `Split`, `H Diff`, `A Diff`

Color rules:

- `Home` values use the site home blue
- `Away` values use the site away red
- `Split` pill uses green for positive, red for negative, gray for neutral

Reason for this first template:

- it is the closest translation of the current website design into an Instagram feed format
- it keeps the output readable without inventing a second visual system

### Step 8: Validate Against Real League Data

Use at least three leagues with different team-name lengths to validate:

- Germany
- Slovakia
- Switzerland or Czech Republic

This is important because long names will break naive table layouts.

## Implementation Phases

### Phase 1: Derived Data

- add a transformation step that builds `home_away_split_table.json`
- keep it independent from scraping
- source only from `team_stats_enhanced.json`

### Phase 2: Website Rendering

- add a league-page block under `Beyond The Standings`
- render the table in desktop and mobile-friendly form
- keep the layout reusable for future advanced tables

### Phase 3: Social Payload Builder

- add a lightweight formatter that converts league table data into template payloads
- support at least square post and story output shapes

### Phase 4: Automated Image Rendering

- choose a deterministic rendering approach
- generate images from templates without manual editing
- emit assets into a predictable output directory

Possible implementation options:

- HTML/CSS templates rendered to PNG
- SVG templates rendered to PNG
- server-side image composition in Python

Preferred direction:

- HTML/CSS templates if fast iteration and design flexibility matter most
- SVG if strict layout determinism matters most

## Recommended File Responsibilities

Possible repo additions:

- `src/social_tables.py`
  - compute advanced tables from existing stats
- `src/social_payloads.py`
  - turn table data into template payloads
- `templates/social/`
  - visual templates for web-to-image rendering
- `output/social/`
  - generated social images

This keeps the social layer separate from the core stats engine.

## Acceptance Criteria

### Data

- can build one `home_away_split_table` from current team stats
- output includes all derived values
- works for each regular-season league run

### Web

- league page shows the new table
- mobile rendering remains readable
- `Split` is visually interpretable at a glance

### Social

- can generate at least one square post image automatically
- can generate at least one story image automatically
- templates use the same underlying table payload

## Risks and Notes

- raw home and away points are not normalized for uneven game counts
- if a league has unbalanced schedules, a per-game version may be needed later
- Instagram tables get crowded quickly, so image variants should use fewer columns than the web table
- this should remain provider-agnostic and work across all league backends

## Immediate Next Steps

1. implement the home/away split transformer from `team_stats_enhanced.json`
2. decide the storage location of the derived JSON artifact
3. add the first web table block to league pages
4. define the first square and story social templates
5. add automatic image rendering from the template payloads
