# Backlog

Single list of work. Concepts, plans and research live in [`docs/`](docs/README.md); every item that has one links to it.

How to keep it:

- New task: add it under **Open** in the matching group. If it needs a concept, write it in `docs/features/<name>.md` (template in [`docs/README.md`](docs/README.md)) and link it here.
- Finished: tick the box, move the line to **Done** under its topic, and set the concept doc's `Status` line to `shipped`.
- Half done: keep it under **Open** and say in the line what remains.

## Open

### Sharing and branding

- [ ] Improve game report sharing ([concept](docs/features/game-report-sharing.md))
- [ ] Club logos instead of monogram crests ([concept](docs/features/club-logos/plan.md)): current-season logos and share graphics implemented under Felix’s confirmed permission; historical seasons and new-team maintenance remain

### Leagues and cups

- [ ] Scalable process across leagues (see [next-generation design](docs/architecture/next-generation-design.md), [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md))
- [ ] Search across leagues
- [ ] Women's leagues: add playoff configs (series formats) for CH, FI, CZ, SK, LV, DE before the playoffs start in March 2027 (SSL Damer is done)
- [ ] Cup switch on team pages ("include cup" for goals by minute, penalties, power play, goal difference): needs per-team cup aggregates built from the `cup` phase games next to the league aggregates; filter default off
- [ ] Cups with no source yet: Slovakia (no 2026/27 cup in the SZFB stats), Latvia (no senior cup); first approved run of `make refresh-cups`, then hook it into the nightly refresh

### Main site and deployment

- [ ] Notion sync in production: store `NOTION_TOKEN` (Florball Connect integration) as GitHub secret for `deploy.yml`
- [ ] Production deploys from GitHub Actions (`deploy.yml`): set the GitHub secrets `NETLIFY_AUTH_TOKEN` and `NETLIFY_SITE_ID`, then merge

### SEO follow-up (1 November 2026)

Concept: [SEO plan](docs/features/seo.md). Runbook: [Google reindexing](docs/operations/google-reindexing.md).

- [ ] After merge/deployment: verify production redirects and submit both sitemaps in Search Console; inspect the priority URLs in [`google-reindex-urls.txt`](docs/operations/google-reindex-urls.txt)
- [ ] Collect missing product reviews and improve priority product comparisons
- [ ] Recheck streaming prices and deal validity against original sources; show verified update/expiry dates
- [ ] Persist meaningful publication-change timestamps for sitemap freshness in the database-driven publishing path; do not substitute fixture or heartbeat dates
- [ ] Evaluate evergreen league/team hubs and targeted training/language pages using Search Console demand
- [ ] From the SEO plan's tracking list, still unticked: language alignment, `robots.txt`, league descriptive text, server-rendered homepage featured content, archive hubs, related entity links

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
- [x] Newsletter sign-up on the new main site: the MailerLite form (double opt-in) the Softr site used
- [x] Live stats block on the main site's home page (`connect-feed.json` from the stats build)

### SEO and AI readiness

- [x] Improve SEO ([concept](docs/features/seo.md))
- [x] Technical reindexing preparation: canonical sitemaps, player alias redirects, lexicon links, competition titles, factual game HTML, product markup, build checks and a Google Search Console submission guide ([`docs/operations/google-reindexing.md`](docs/operations/google-reindexing.md))
- [x] `llms.txt` at the site root (`plugins/llms_txt.py`): link map for AI assistants and AI search, current-season leagues first, teams and older seasons as optional; pages only, no data export
