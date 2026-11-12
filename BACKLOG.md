# Backlog

Single list of work. Concepts, plans and research live in [`docs/`](docs/README.md); every item that has one links to it.

How to keep it:

- New task: add it under **Open** in the right priority group. If it needs a concept, write it in `docs/features/<name>.md` (template in [`docs/README.md`](docs/README.md)) and link it here.
- Finished: tick the box, move the line to **Done** under its topic, and set the concept doc's `Status` line to `shipped`.
- Half done: keep it under **Open** and say in the line what remains.

How it is ranked (as of 2026-11-12): reach first (stats.floorballconnect.com has about 3,500 unique visitors per 30 days), then the first euro, then a hard deadline. A task that Claude can do alone from data and research beats one that needs sales or outreach. Effort: S = under a day, M = a few days, L = a week or more.

## Open

### P1: do next

Reach work that Claude can do alone. Details: [SEO plan](docs/features/seo.md). Share links and the search scopes shipped on 2026-11-12, see Done.

- [ ] SEO, visible text on league pages: `league_v2.html` shows an H1 and tables only, no overview paragraph. Add a short factual text per league (teams, season, champion or leader, number of games) so league queries have something to match · M
- [ ] SEO, related links between entities: no "related" blocks exist on team, league, game or player pages. Link league ↔ cup ↔ women's/men's league, team ↔ rivals/head-to-head, player ↔ team · M

### P2: next

- [ ] Search for games: players, teams and leagues/cups are searchable in scopes; games are not (search by team pair or date). Decide first whether people look for games by name · S to M
- [ ] Share images for past seasons and for players without a club logo: today only current-season games, teams, leagues and players with a logo have their own `og:image`, the rest gets `og/default.png` · S, low reach
- [ ] SEO, homepage: today's games are drawn by JavaScript ("Loading games…"), so crawlers see an empty list. Render the games of the build date into the HTML, keep the script for the date strip · S, not urgent
- [ ] Women's leagues: playoff configs (series formats) for CH, FI, CZ, SK, LV, DE. Not needed before the playoffs start in March 2027; they are added once the regular fetches show the playoff phase (SSL Damer is done) · trigger: March 2027
- [ ] Notion sync in production: store `NOTION_TOKEN` (Florball Connect integration) as GitHub secret for `deploy.yml`; until then new reviews on the main site do not sync · Felix, 5 min, parked on purpose
- [ ] Collect missing product reviews and improve priority product comparisons (main site) · closest to the first euro, needs real review data
- [ ] Recheck streaming prices and deal validity against original sources; show verified update/expiry dates · trust, and affiliate-relevant · S
- [ ] Cup switch on team pages ("include cup" for goals by minute, penalties, power play, goal difference): needs per-team cup aggregates built from the `cup` phase games next to the league aggregates; filter default off · M
- [ ] Cups with no source yet: Slovakia (no 2026/27 cup in the SZFB stats), Latvia (no senior cup); first approved run of `make refresh-cups`, then hook it into the nightly refresh · S
- [ ] Club logos instead of monogram crests: current-season logos and share graphics are done under Felix’s confirmed permission; historical seasons and new-team maintenance remain · M · [concept](docs/features/club-logos/plan.md)
- [ ] Persist meaningful publication-change timestamps for sitemap freshness in the database-driven publishing path; do not substitute fixture or heartbeat dates · S

### P3: later

- [ ] Scalable process across leagues · pays off when league number 8 comes, no visible effect for users now · L · [next-generation design](docs/architecture/next-generation-design.md), [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
- [ ] Evaluate evergreen league/team hubs and targeted training/language pages using Search Console demand · wait for a few weeks of Search Console data
- [ ] SEO plan leftovers to re-check first: language alignment, archive hubs (not verified whether they are still missing)

## Ideas and user feedback

Not yet planned. Move an idea into **Open** (with a concept doc if it is bigger than a day) once it is decided.

- Add short summaries via LLMs to each game
- Add Highlight videos
- Integrate Player Stats
- Integrate Offense and Defense Ratings for all teams
- More advanced H2H in particular for upcoming games
- Auth and premium access: parked outline in [`docs/features/auth-premium-access.md`](docs/features/auth-premium-access.md)
- Home/away split as a social format: partly built, see [`docs/features/home-away-social.md`](docs/features/home-away-social.md) (phases not verified against the code)

## Done

### Games and results

- [x] Share links in the share studio: copy link, copy text, device share sheet, WhatsApp, Telegram, X, Facebook, LinkedIn, Reddit, Bluesky, e-mail; links tagged `utm_source=share`; PostHog events `share_link_clicked/_completed/_failed` ([`share-links.js`](themes/my-theme/static/js/share-links.js), [analytics events](docs/operations/analytics-events.md))
- [x] Share studio: Instagram cards (Story and Post, dark or light) for game, team, player and table, drawn in the browser (`themes/my-theme/static/js/share-card.js`), with download and native share of the image
- [x] Share images (`og:image`, 1200×630) for current-season games, teams, players with a club logo, and league, playoff, cup and player-table pages, team calendar feeds (.ics) for Apple/Outlook/Google (`plugins/share_assets.py`, `tests/test_share_assets.py`)
- [x] Global search with scopes (All, Players, Teams, Leagues & cups): all 4,703 players with team and season, one row per club and league, 78 league/cup pages, ranked by name match, newest season and points (`src/build_search_index.py`, `search-rank.js`)

- [x] Show if a game was won in OT or PS from the games overview templates
- [x] Show in the game lists the winning (including ot or ps wins) team in bold. If it was a draw make both teams not bold
- [x] Add similar to flashscore.de a green W for a win, a red L for a loss or a half yellow for win or loss in ot or ps. This should be added to all games from a respective team always from the view of the team itself
- [x] Integrate full game events to have one place to check scorers, ... (research: [scorer names](docs/research/scorer-names-feasibility.md))
- [x] Game page: mark powerplay/shorthanded goals in the event timeline, "Topspiel" label in the schedule, opponents' table places next to the fixture (#6 – #5), venue name
- [x] Game story on game pages: live win chance through the game, key moments, lead changes, excitement (replaces the cumulative goals chart)

### Leagues and playoffs

- [x] Research and implement a way to integrate the Slovakian top mens league similar to all other leagues
- [x] Research and implement a way to integrate the Latvian top mens league similar to all other leagues (research: [league portals](docs/research/league-portals.md))
- [x] Bug: on the latvian website the teams have different points. Check it and adapt the calculation only for the latvian league
- [x] Playoff Bracket Visualization
- [x] Prepare the playoffs for all other leagues as well. In CZ and SWE they are starting very soon as the regular seasons are over
- [x] National cups imported as their own phase `cup` (SE, CH, CZ, FI, DE, men and women), kept out of tables, leaders and player stats; sources per country in the README ("Cups")

### Stats and analysis

- [x] Clutch stats (game winners, go-ahead goals, equalizers, clutch points) and scoring duos on player, team and league pages
- [x] Power ranking: Elo ratings, win probabilities on game pages, biggest upsets, season and playoff projections per league
- [x] Table history: every team's place after each round, as a chart on league and team pages
- [x] Head-to-head matrix, "What's at stake" with game of the week, remaining schedule, streaks and records, goal timing, comebacks and leads, share of team goals, crowds
- [x] "How our stats work" page with all definitions (Elo, projections, clutch, game-changing goals, duos, table history), linked from every new section
- [x] Crowd analysis (idea from liveticker.floorba11.stream): `/crowds.html` compares the leagues for the newest season (average, median, total, highest, gap between best and smallest home average, share of the top 3 teams) and shows weekday, face-off time and regular season vs. playoffs per league. No comparison with previous seasons (women's leagues have no 25/26 games)
- [x] Special teams view per league: scatter (powerplay goals per opportunity vs. penalty kills without a goal against) plus table with PP, PP %, BP, BP %, shorthanded goals, SH goals against, PP minutes
- [x] Player page: powerplay and shorthanded goals as KPIs, game log (result, own goals/assists/points per game) with filter by league/cup and season
- [x] Search for Players in the player list

### Map and travel

- [x] Team map on league pages: country outline with club logos at their home towns, hover tooltip and link to the team page ([concept](docs/features/team-map.md))
- [x] Travel on league pages: away kilometres per team, straight line between home towns (`src/travel.py`). Derbies left out for now: what counts as a derby differs per country

### Design

- [x] Bug: in darkmode you can not read the leagues on the home page due to the contrast. Check all contrasts

### Main site (floorballconnect.com)

- [x] Main site floorballconnect.com off Softr: own Pelican site in `connect/` on the stats design system, content imported, Softr URLs redirected ([ARCHITECTURE.md 4.8a](docs/architecture/ARCHITECTURE.md))
- [x] Go live with the new main site: www.floorballconnect.com and floorballconnect.com on the stats Netlify site (DNS at STRATO: A 75.2.60.5, www CNAME floorball-stats.netlify.app)
- [x] Notion sync for the main site: database ids, publish filters and review relations in `connect/notion.json`; first sync run against Notion
- [x] Daily build for new reviews: `.github/workflows/deploy.yml` rebuilds and deploys at 04:17 UTC
- [x] Production deploys from GitHub Actions (`deploy.yml`): `NETLIFY_AUTH_TOKEN` and `NETLIFY_SITE_ID` are set, deploys run
- [x] Newsletter sign-up on the new main site: the MailerLite form (double opt-in) the Softr site used
- [x] Live stats block on the main site's home page (`connect-feed.json` from the stats build)

### SEO and AI readiness

- [x] Google Search Console is set up (Felix); sitemaps submitted
- [x] `robots.txt` (written by `plugins/seo.py`, points to the sitemap; closes the site on preview builds) and a cleaned `sitemap.xml` with canonical URLs, no fake `lastmod`
- [x] Canonical URLs, Open Graph and Twitter card tags, JSON-LD for games, standings tables and players, covered by `tests/test_seo.py`

- [x] Improve SEO ([concept](docs/features/seo.md))
- [x] Technical reindexing preparation: canonical sitemaps, player alias redirects, lexicon links, competition titles, factual game HTML, product markup, build checks and a Google Search Console submission guide ([`docs/operations/google-reindexing.md`](docs/operations/google-reindexing.md))
- [x] `llms.txt` at the site root (`plugins/llms_txt.py`): link map for AI assistants and AI search, current-season leagues first, teams and older seasons as optional; pages only, no data export
