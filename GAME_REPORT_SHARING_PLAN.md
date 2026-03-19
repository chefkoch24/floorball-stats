# Game Report Sharing Plan

Backlog reference:

- [BACKLOG.md](/Users/felixkuennecke/Projects/floorball-stats/BACKLOG.md)

## Goal

Make game report pages easier to share across messaging apps, social platforms, and direct links without tightly coupling the implementation to the current template layout or a single platform.

The feature should:

- improve link previews
- reduce friction for users who want to share a game
- create a reusable foundation for future social asset generation
- stay robust when templates, leagues, or naming conventions evolve

## Product Direction

Game reports are the most naturally shareable pages on the site because they already answer a specific intent:

- what happened
- what was the score
- how can I send this to someone

The sharing feature should focus on:

1. better previews when a game URL is pasted into chat or social apps
2. one-click share actions on the game page itself
3. deterministic summary text that can be copied or reused
4. a reusable payload that can power future social formats

## MVP Scope

### User-facing features

- `Copy link` button on game pages
- `Copy summary` button on game pages
- `Share` button using `navigator.share` where available
- improved Open Graph metadata for game pages
- improved Twitter card metadata for game pages
- fallback share image for game pages

### Internal foundation

- normalized share payload derived from the game article
- centralized helper functions for share title, summary, phase label, and image path
- deterministic, testable summary generation

## Design Principles

### 1. Keep sharing logic data-driven

The sharing feature should not depend on hardcoded fragments scattered across templates.

Instead:

- generate one normalized share payload
- let templates and metadata consume that payload

This makes the system easier to maintain when:

- team names change
- phase naming changes
- breadcrumbs evolve
- future social platforms are added

### 2. Separate metadata generation from visual layout

The same game page data should support:

- page metadata
- copy-to-clipboard summary text
- native share text
- OG image generation

This avoids duplicate logic and drift between page content and share content.

### 3. Prefer deterministic summaries over generated prose

For the initial version, use rule-based summaries instead of LLM-generated text.

Example:

- `Pixbo IBK beat Falun 6:4 in Sweden Regular Season 25/26 on 2026-03-14.`
- `Pixbo IBK beat Falun 6:4 after overtime in Sweden Playoffs 25/26 on 2026-04-02.`
- `Pixbo IBK beat Falun 6:5 after a shootout in Sweden Playoffs 25/26 on 2026-04-05.`

This is:

- predictable
- easy to test
- cheap
- easy to localize later

### 4. Always provide fallbacks

The share feature should work even if:

- no game-specific share image exists yet
- some fields are missing
- `navigator.share` is not supported

Fallback behavior should be built in by default.

## Proposed Architecture

## 1. Share Payload Model

Introduce a normalized game share payload derived from a game article.

Suggested shape:

```python
{
  "title": "Pixbo IBK vs Falun 6:4 | Sweden Regular Season 25/26",
  "summary": "Pixbo IBK beat Falun 6:4 in Sweden Regular Season 25/26 on 2026-03-14.",
  "url": "https://stats.floorballconnect.com/1571895-storvreta-ibk-vs-pixbo-ibk.html",
  "image_url": "https://stats.floorballconnect.com/social/game/1571895-storvreta-ibk-vs-pixbo-ibk.png",
  "image_alt": "Pixbo IBK vs Falun final score 6:4",
  "competition": "Sweden Regular Season 25/26",
  "date": "2026-03-14",
  "home_team": "Pixbo IBK",
  "away_team": "Falun",
  "score": "6:4",
  "decision_type": "regulation"
}
```

Required fields:

- `title`
- `summary`
- `url`
- `image_url`
- `competition`
- `home_team`
- `away_team`
- `score`

Optional fields:

- `decision_type`
- `attendance`
- `image_alt`

## 2. Jinja / Helper Layer

Add helper functions for share logic instead of composing strings inline in templates.

Suggested helpers:

- `category2phase_label`
- `game_share_title(article)`
- `game_share_summary(article)`
- `game_share_image_path(article)`
- `game_share_image_url(article, siteurl)`
- `game_share_decision_label(article)`

Best initial location:

- [pelicanconf.py](/Users/felixkuennecke/Projects/floorball-stats/pelicanconf.py)

Longer-term option:

- move these helpers into a dedicated utility module if the share layer grows

## 3. Metadata Integration

Extend the existing SEO metadata support so game pages can set:

- `og:image`
- `og:image:alt`
- `twitter:card`
- `twitter:title`
- `twitter:description`
- `twitter:image`

Files:

- [themes/my-theme/templates/base.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/base.html)
- [themes/my-theme/templates/article.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/article.html)

Fallback behavior:

- use a game-specific image if available
- otherwise use a site-level fallback image

## 4. Share Action UI on Game Pages

Add a compact share toolbar near the top of:

- [themes/my-theme/templates/game.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/game.html)

Recommended actions:

- `Copy link`
- `Copy summary`
- `Share`

Implementation detail:

- render a small toolbar element with `data-*` attributes
- let JS read from those attributes rather than duplicating the strings inline in multiple handlers

Suggested data attributes:

- `data-share-title`
- `data-share-summary`
- `data-share-url`

Recommended JS behavior:

- `Copy link` copies canonical URL
- `Copy summary` copies summary plus URL
- `Share` uses `navigator.share({ title, text, url })`
- if `navigator.share` is unavailable, fall back to copy behavior

## 5. Share Image Generation

Do not generate share images inside the template.

Instead, add a build-time step that creates a stable image path such as:

- `output/social/game/<slug>.png`

Suggested initial image content:

- home team
- away team
- final score
- competition
- date
- optional OT / PS marker

Initial rollout options:

- generate for all game pages
- or generate only for current-season games

Recommended long-term trigger rules for richer assets:

- playoffs
- overtime / shootout
- one-goal games
- rivalry games
- top-team matchups

## 6. Fallback Asset Strategy

Always define a fallback image:

- `theme/images/og-default.png`

This fallback should be used when:

- no game-specific image exists
- image generation is disabled
- a build is partial or interrupted

## 7. Testing Strategy

The share layer should be tested at the helper level.

Suggested tests:

- regulation win summary
- overtime summary
- shootout summary
- missing date
- missing attendance
- category / phase label conversion
- special-character team names
- safe image path generation
- canonical URL consistency

Target area:

- `tests/`

## Robustness Requirements

To keep this feature robust against future changes:

### 1. Centralize slug handling

All share URLs and image paths must rely on the same canonical slug normalization used by the site.

Do not duplicate slug logic in:

- templates
- inline JS
- image generation scripts
- tests

### 2. Centralize phase naming

Do not hardcode strings like:

- `Regular Season`
- `Playoffs`

in multiple places.

Those labels should come from one helper layer so breadcrumb updates, metadata, and share summaries stay aligned.

### 3. Avoid platform-specific logic in the core payload

The normalized payload should stay generic.

If future integrations are added for:

- WhatsApp
- X
- Facebook
- Instagram assets

those should consume the generic payload rather than reshape the game data again from scratch.

### 4. Make missing data safe

If a game is missing some fields, the share feature should degrade cleanly:

- no broken JS
- no invalid metadata
- no broken image URL if a fallback exists

### 5. Keep the visual layer optional

The page should remain valid even if the share toolbar is hidden or restyled later.

That means:

- metadata logic should not depend on the toolbar
- toolbar JS should not be the source of truth for share content

## File-Level Implementation Plan

### Phase 1

1. [pelicanconf.py](/Users/felixkuennecke/Projects/floorball-stats/pelicanconf.py)
   - add share helper functions
   - register them in `JINJA_FILTERS`

2. [themes/my-theme/templates/base.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/base.html)
   - add support for `og:image`
   - add support for `og:image:alt`
   - add support for `twitter:*` share tags

3. [themes/my-theme/templates/article.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/article.html)
   - inject game-specific share metadata
   - populate fallback image values when necessary

4. [themes/my-theme/templates/game.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/game.html)
   - add share toolbar
   - add `data-*` payload fields
   - add minimal share/copy JS

5. [themes/my-theme/static/css/style.css](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/static/css/style.css)
   - style the share toolbar

### Phase 2

6. `tests/`
   - add tests for share title / summary / slug-safe image paths

7. fallback asset path
   - add generic OG image asset

### Phase 3

8. `src/`
   - add build-time generator for game-specific share images

9. integrate image generation into the content/build flow

## Recommended Delivery Order

1. helper functions
2. metadata support
3. share toolbar
4. fallback OG image
5. tests
6. generated game images

## Out of Scope for MVP

- Instagram-only custom formats
- per-platform custom share text
- automatic social posting
- LLM-generated recap text
- player-based share cards

## Tracking Checklist

### MVP

- [ ] game share payload helper layer
- [ ] game share title helper
- [ ] game share summary helper
- [ ] game share image helper
- [ ] OG image metadata support
- [ ] Twitter card metadata support
- [ ] game page share toolbar
- [ ] copy link action
- [ ] copy summary action
- [ ] native mobile share action
- [ ] fallback OG image

### Robustness

- [ ] centralized slug handling for share assets
- [ ] centralized phase naming
- [ ] graceful fallback for missing image
- [ ] graceful fallback for unsupported native share
- [ ] helper tests

### Later Expansion

- [ ] generated game-specific share images
- [ ] important-game share asset rules
- [ ] platform-specific adapters if needed
