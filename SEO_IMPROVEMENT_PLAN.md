# SEO Improvement Plan

## Scope

This plan is based on the current Pelican templates and config in this repository, with a focus on:

- homepage SEO
- category / season hub SEO
- team page SEO
- game page SEO
- league page SEO
- crawl and indexing infrastructure

Main files reviewed:

- [themes/my-theme/templates/base.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/base.html)
- [themes/my-theme/templates/index.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/index.html)
- [themes/my-theme/templates/category.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/category.html)
- [themes/my-theme/templates/article.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/article.html)
- [themes/my-theme/templates/team.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/team.html)
- [themes/my-theme/templates/game.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/game.html)
- [themes/my-theme/templates/liga.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/liga.html)
- [pelicanconf.py](/Users/felixkuennecke/Projects/floorball-stats/pelicanconf.py)
- [publishconf.py](/Users/felixkuennecke/Projects/floorball-stats/publishconf.py)

## Current Findings

### 1. Metadata foundation is missing

Severity: High
Scope: Sitewide
Complexity: Low
Impact: High

Issues:

- all pages currently use the same `<title>` in [themes/my-theme/templates/base.html:6](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/base.html#L6)
- no page-specific meta descriptions
- no canonical tags
- no Open Graph tags
- no Twitter card tags
- no robots meta handling

Why this matters:

- search engines cannot clearly distinguish team, game, league, and season pages
- click-through rate from search results will be weaker than necessary
- duplicate URL handling is weaker than it should be

### 2. Production URL handling is incomplete

Severity: High
Scope: Config
Complexity: Low
Impact: High

Issues:

- `SITEURL = ''` in [pelicanconf.py:4](/Users/felixkuennecke/Projects/floorball-stats/pelicanconf.py#L4)
- `SITEURL = ''` in [publishconf.py:10](/Users/felixkuennecke/Projects/floorball-stats/publishconf.py#L10)

Why this matters:

- proper canonical URLs cannot be generated
- structured data URLs cannot be made absolute
- sitemap quality is limited

Recommended production value:

- `https://stats.floorballconnect.com`

### 3. Sitemap and robots support are missing

Severity: High
Scope: Build / publishing
Complexity: Medium
Impact: High

Issues:

- no sitemap generation is configured
- no `robots.txt` was found

Why this matters:

- the site has many long-tail URLs
- index discovery is more efficient with sitemap support
- `robots.txt` is basic crawl hygiene and should include the sitemap location

### 4. Game pages are data-rich but text-light

Severity: High
Scope: Game template
Complexity: Medium
Impact: High

Files:

- [themes/my-theme/templates/game.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/game.html)

Issues:

- game pages rely heavily on tables, charts, and client-side rendering
- there is no short server-rendered summary paragraph near the top
- no sports event structured data is present

Why this matters:

- search engines understand concise server-rendered text better than chart-heavy layouts alone
- game pages are ideal targets for `SportsEvent` or generic `Event` schema

Recommended summary pattern:

- "`{{ home_team }}` beat `{{ away_team }}` `{{ home_goals }}:{{ away_goals }}` on `{{ date }}` in `{{ competition }}`."

### 5. Team pages have strong stats but weak SEO framing

Severity: High
Scope: Team template
Complexity: Medium
Impact: High

Files:

- [themes/my-theme/templates/team.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/team.html)

Issues:

- only the team name is used as the main heading in [themes/my-theme/templates/team.html:4](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/team.html#L4)
- subtitle text is generic
- no structured data for the team entity
- no explicit league / season / country keyword framing in metadata

Why this matters:

- team pages should rank for searches combining team + competition + season + stats intent

Recommended title pattern:

- `{{ team }} Stats, Results and Special Teams | {{ league }} {{ season }}`

### 6. League pages need stronger descriptive context

Severity: Medium
Scope: League pages
Complexity: Low to Medium
Impact: Medium

Files:

- [themes/my-theme/templates/liga.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/liga.html)

Issues:

- page content is dominated by KPI and table output
- subtitle copy is generic in [themes/my-theme/templates/liga.html:5](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/liga.html#L5)
- no league overview paragraph exists

Why this matters:

- these pages should target league-level informational queries
- a small amount of descriptive text can improve topical clarity significantly

### 7. Category / season hub pages are valuable but under-optimized

Severity: Medium
Scope: Category template
Complexity: Low
Impact: Medium to High

Files:

- [themes/my-theme/templates/category.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/category.html)

Issues:

- heading is good, but intro copy is generic in [themes/my-theme/templates/category.html:26](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/category.html#L26)
- standings and game lists have little explanatory text
- there are no breadcrumbs

Why this matters:

- category pages are likely the best ranking pages for league + season queries
- these pages should be treated as high-value hubs

Recommended additions:

- 100-200 words of server-rendered intro copy
- short explanations above standings, league reports, and season games
- breadcrumb navigation

### 8. Homepage is useful for users but weaker than it could be for search

Severity: Medium
Scope: Homepage
Complexity: Low to Medium
Impact: Medium

Files:

- [themes/my-theme/templates/index.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/index.html)

Issues:

- “Today’s Games” is rendered client-side from hidden source markup
- homepage copy is minimal
- there is no server-rendered featured content block for search engines

Why this matters:

- the homepage should establish topical authority across leagues, seasons, teams, and game data

Recommended additions:

- server-rendered featured games
- latest results block
- short descriptive paragraph about league coverage and stat types

### 9. Internal linking can be stronger

Severity: Medium
Scope: Sitewide
Complexity: Low
Impact: Medium

Issues:

- no breadcrumb structure
- limited reverse linking from game pages back to league / category / team hubs
- limited discovery of archives and related entities

Why this matters:

- strong internal linking helps crawlers understand site structure
- entity-heavy sites benefit from dense contextual linking

Recommended additions:

- breadcrumbs on all page types
- links from game pages to both teams and the season hub
- links from team pages back to standings and league overview
- archive links by season and league

### 10. Language targeting is inconsistent

Severity: Medium
Scope: Sitewide
Complexity: Low
Impact: Medium

Files:

- [pelicanconf.py:17](/Users/felixkuennecke/Projects/floorball-stats/pelicanconf.py#L17)
- [themes/my-theme/templates/base.html:2](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/base.html#L2)

Issues:

- `DEFAULT_LANG = 'de'`
- document `<html lang="de">` is hardcoded
- current UI copy is mostly English

Why this matters:

- search engines should receive a language signal that matches the actual content

Recommendation:

- if the site remains English-first, switch the site language handling to English
- if multilingual support is planned later, make language selection explicit per page

## Quick Wins

These are the changes with the best speed-to-value ratio.

| Improvement | Scope | Complexity | Impact | Notes |
|---|---|---:|---:|---|
| Add unique page titles for homepage, category, team, game, and league pages | Sitewide templates | Low | High | Highest-priority metadata fix |
| Add meta descriptions per page type | Sitewide templates | Low | High | Improves search snippets |
| Add canonical tags using absolute URLs | Sitewide config + base template | Low | High | Reduces duplicate URL ambiguity |
| Set production `SITEURL` in publish config | Config | Low | High | Unblocks canonicals and schema |
| Add Open Graph tags | Sitewide templates | Low | Medium | Better social sharing and metadata completeness |
| Add short intro copy to category pages | Category template | Low | Medium / High | Strong improvement for season hub rankings |
| Add breadcrumb navigation | Sitewide templates | Low / Medium | Medium | Good for UX and SEO |
| Align site language with actual copy | Config + base template | Low | Medium | Cleaner language targeting |

## Worth Doing Next

| Improvement | Scope | Complexity | Impact | Notes |
|---|---|---:|---:|---|
| Add XML sitemap generation | Build / config | Medium | High | Important for a large URL set |
| Add `robots.txt` | Static output | Low | Medium | Include sitemap declaration |
| Add `SportsEvent` JSON-LD on game pages | Game template | Medium | High | Best structured-data opportunity |
| Add `SportsTeam` JSON-LD on team pages | Team template | Medium | Medium / High | Helps entity understanding |
| Add breadcrumb JSON-LD | Sitewide templates | Medium | Medium | Easy once breadcrumbs exist |
| Add a server-rendered match summary paragraph on game pages | Game template + markdown generation | Medium | High | Makes game pages more indexable |
| Add homepage featured results / upcoming games as server-rendered content | Homepage template | Medium | Medium | Stronger crawlable homepage |
| Add descriptive copy to league pages | League template | Low / Medium | Medium | Improves query relevance |

## Higher Investment, High Return

| Improvement | Scope | Complexity | Impact | Notes |
|---|---|---:|---:|---|
| Generate entity-specific summaries in the pipeline | Markdown generation + templates | High | High | Unique text at scale across the site |
| Build archive hubs by league, season, and team | Site architecture | Medium / High | High | Strong long-tail SEO inventory |
| Add comparison and head-to-head pages | New content / templates | High | High | Strong search intent if data supports it |
| Add player pages later if data is available | Data + templates | High | High | Large SEO inventory expansion |

## Recommended Implementation Order

1. Metadata foundation
2. Crawl and indexing foundation
3. Server-rendered summary text on key page types
4. Structured data
5. Archive and inventory expansion

More specifically:

1. Add titles, descriptions, canonicals, and OG tags in [themes/my-theme/templates/base.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/base.html)
2. Set production `SITEURL` in [publishconf.py](/Users/felixkuennecke/Projects/floorball-stats/publishconf.py)
3. Add sitemap and `robots.txt`
4. Add category intro copy and breadcrumbs
5. Add game summary text and `SportsEvent` schema
6. Add team summary text and `SportsTeam` schema
7. Add archive hubs and richer internal linking

## Suggested Title Patterns

Homepage:

- `Floorball Stats for SSL, F-Liiga, L-UPL and More | Floorball Stats`

Category pages:

- `SSL 2025/26 Regular Season Standings, Teams and Results | Floorball Stats`

Team pages:

- `{{ team }} Stats, Results and Special Teams | {{ league }} {{ season }}`

Game pages:

- `{{ home_team }} vs {{ away_team }} {{ home_goals }}:{{ away_goals }} | {{ league }} {{ season }} Game Stats`

League pages:

- `{{ league }} {{ season }} League Stats, Scoring and Special Teams`

## Suggested Meta Description Patterns

Category pages:

- `Standings, team stats, league reports, results, and upcoming games for {{ league }} {{ season }} on Floorball Stats.`

Team pages:

- `Season stats, results, special teams, scoring profile, and recent games for {{ team }} in {{ league }} {{ season }}.`

Game pages:

- `Match stats, scoring flow, penalties, special teams, and event timeline for {{ home_team }} vs {{ away_team }} in {{ league }} {{ season }}.`

League pages:

- `League-wide scoring, special teams, and result trends for {{ league }} {{ season }}.`

## Concrete First Implementation Targets

If work starts now, these should be the first practical tasks:

1. Update [themes/my-theme/templates/base.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/base.html) so page types can inject:
   - title
   - meta description
   - canonical URL
   - Open Graph values
2. Update [publishconf.py](/Users/felixkuennecke/Projects/floorball-stats/publishconf.py) to use the production URL
3. Add server-rendered descriptive copy to:
   - [themes/my-theme/templates/category.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/category.html)
   - [themes/my-theme/templates/team.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/team.html)
   - [themes/my-theme/templates/game.html](/Users/felixkuennecke/Projects/floorball-stats/themes/my-theme/templates/game.html)
4. Add breadcrumbs across category, team, game, and league pages
5. Add sitemap and `robots.txt`

## Tracking View

Suggested tracking buckets:

### Quick Wins

- [x] unique page titles
- [x] meta descriptions
- [x] canonical tags
- [x] production `SITEURL`
- [x] Open Graph tags
- [x] category intro copy
- [x] breadcrumbs
- [ ] language alignment

### Foundation

- [ ] sitemap generation
- [ ] `robots.txt`
- [x] breadcrumb structured data

### Page Quality

- [x] game summary text
- [x] game structured data
- [x] team summary text
- [x] team structured data
- [ ] league descriptive text
- [ ] server-rendered homepage featured content

### Expansion

- [ ] archive hubs
- [ ] related entity links
- [ ] comparison / head-to-head pages
- [ ] player pages if data becomes available
