# Vision

## Why This Project Exists

`floorball-stats` should become the best structured and most trusted public source for floorball statistics across leagues and international competitions.

The site should make it easy to:
- follow leagues, teams, players, and games,
- follow international tournaments and cross-border matchups,
- understand performance through clear and explainable metrics,
- discover insights quickly through search and comparisons,
- reuse the same data foundation for future products.


## Product Direction

The long-term goal is not just to publish static pages.

The long-term goal is to build a live floorball data platform with:
- reliable multi-league ingestion,
- international competition coverage,
- consistent derived statistics,
- SEO-friendly public pages,
- internal tooling for analysis and debugging,
- a foundation for future SaaS features.


## Core Principles

### 1. One trustworthy source of truth

Operational truth should live in a remote database, not in scattered generated artifacts.

Current direction:
- Neon/PostgreSQL is the canonical derived data store.
- Markdown and HTML are publishing outputs.
- Generated files should remain traceable to a specific pipeline run and schema version.

### 2. Static where possible, dynamic where useful

SEO pages should remain fast, indexable, and stable.

At the same time, live or frequently changing stats should not require full site rebuilds.

Target model:
- Pelican/static pages for structure, navigation, and search visibility.
- Dynamic data blocks and APIs for live or rapidly changing stats.

### 3. One user-facing identity per entity

Users should not have to understand internal pipeline boundaries.

That means:
- one team identity in search,
- one player identity in search,
- one canonical page per user-facing entity where possible,
- phase-specific stats shown as sections or tabs instead of duplicate search results.

### 4. Explainability over raw numbers

Stats are only useful if people understand them.

Every visible metric should be explainable in context with:
- short definitions,
- abbreviation help,
- consistent naming,
- tooltips or stat guides where needed.

### 5. Incremental over full refreshes

Full refreshes are useful for recovery and initialization, but they should not be the normal operating mode.

The default system should:
- update only affected leagues, games, teams, and players,
- recompute only impacted derived rows,
- reduce rebuild cost and runtime,
- support near-real-time refresh windows when games are active.


## Near-Term Vision

In the next stage, the project should evolve from a repository-driven stats generator into a database-driven publishing system.

Near-term priorities:
- Make Neon the only derived source for markdown generation.
- Keep pipelines incremental by default.
- Add version metadata to generated outputs.
- Improve global search across teams and players.
- Reduce duplicate entities caused by season-phase splits.
- Extend the data model so international games fit naturally beside league and playoff data.
- Support better debugging of pipeline results and freshness.


## Mid-Term Vision

Once the database-first setup is stable, the site should support much more live behavior without losing SEO quality.

Mid-term goals:
- dynamic stat delivery for selected page sections,
- short refresh windows around active games,
- richer player and team profiles,
- stronger cross-league discovery,
- unified views that connect domestic and international performance,
- internal admin/debug views for freshness, pipeline health, and scrape coverage.


## Long-Term Vision

The long-term opportunity is bigger than a stats website.

This project can become the data layer for a floorball SaaS product.

Potential expansion areas:
- team and league dashboards,
- sponsor-facing or media-facing insights,
- premium scouting and analytics features,
- embeddings/search across historical data,
- APIs for third-party integrations,
- editorial workflows on top of structured sports data.


## Growth Strategy

The project should not rely on a single growth channel.

The strongest growth path is to combine product quality, distribution, and future monetization.

### 1. Win on utility

The product should become genuinely useful on matchdays and for research.

That means:
- strong team, player, and game pages,
- fast search,
- understandable metrics,
- broad competition coverage,
- reliable freshness around active games.

### 2. Win on discovery

SEO should remain a major channel, but not the only one.

Additional discovery loops:
- shareable player and game pages,
- team and competition landing pages,
- social-ready stat summaries,
- embeddable widgets for clubs, blogs, and media,
- internal linking across players, teams, games, and competitions.

### 3. Win on depth before broadness

The project does not need to be perfect everywhere at once.

It is better to be clearly best in a few areas first, for example:
- player profiles,
- playoff coverage,
- live game pages,
- international competition coverage,
- historical archives and comparisons.

### 4. Build contribution loops

Growth becomes more durable when users, clubs, and media participants help improve the product.

Examples:
- issue reporting for broken or missing data,
- correction workflows for clubs,
- public freshness and coverage status,
- internal tooling that makes manual fixes fast and traceable.

### 5. Build toward monetizable workflows

The public site should create trust and reach.

The same data platform should later support paid or premium workflows such as:
- private dashboards for clubs and leagues,
- scouting and comparison tools,
- sponsor and media stat packs,
- automated reports,
- API access for partners.


## What Success Looks Like

Success means:
- users trust the numbers,
- pages are fast and searchable,
- live data feels current,
- internal data flow is easy to inspect,
- adding a new league is operationally cheap,
- adding an international competition is operationally cheap,
- the same platform can power both the public site and future paid products.


## Non-Goals

This project should not optimize for:
- fully manual data maintenance,
- duplicated entities that leak internal modeling into UX,
- full-repository rebuilds for every small update,
- hidden or unexplained metrics,
- brittle one-off league logic without a path to standardization.
