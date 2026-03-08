# League Portals Deep Scan (Portals + JSON Backends)

Date: 2026-03-04

Scope: Sweden (SSL), Finland (F‑liiga), Switzerland (L‑UPL), Czech Republic (Livesport Superliga).

Method: Public web inspection (HTML + documented APIs). Where JS‑only portals exist, note them as "requires runtime network inspection".

---

## Sweden (Svenska Superligan / Svenska IBF)

### Primary portals
- Svenska IBF iBIS API service page (official API access and usage terms). citeturn0search0
- iBIS API documentation endpoint mentioned on the federation page (Swagger). citeturn0search0

### JSON / API backend
- **iBIS API**: `https://api.innebandy.se/v2/` (REST + OAuth2).
  - Access is restricted to clubs with teams in top national leagues and is limited to data for their own teams. citeturn0search0
  - Calls are allowed once per day in a defined time window; API uses OAuth2 Bearer tokens. citeturn0search0

### SSL public API (sports-v2) from ssl.se
- **Base**: `https://www.ssl.se/api`
- **Working schedule endpoint** (example):
  - `GET /api/sports-v2/game-schedule?seasonUuid=...&seriesUuid=...&gameTypeUuid=...&gamePlace=all&played=all`
- **Response fields** (sample): `overtime`, `shootout`, `rawStartDateTime`, `startDateTime`, team/venue/series objects.
- **Endpoints discovered in the SSL JS bundle**:
  - `/sports-v2/season-series-game-types-filter`
  - `/sports-v2/latest-ssgt`
  - `/sports-v2/game-series/by-ssgt`
  - `/sports-v2/game-schedule`
  - `/sports-v2/game-info`
  - `/sports-v2/played-games`, `/sports-v2/upcoming-games`, `/sports-v2/today-games`, `/sports-v2/upcoming-live-games`
  - `/sports-v2/teams`, `/sports-v2/all-teams`, `/sports-v2/all-sites`
  - `/sports-v2/athlete-details`, `/sports-v2/athletes/by-team-uuid`
  - `/sports-v2/staffs`
 - The JS client uses `/api` as base and includes an `x-s8y-instance-id` header (value `ssl1_ssl`) on requests.

### GameType and playoff detection (SSL)
- `GET /api/sports-v2/season-series-game-types-filter` returns `season`, `series`, `gameType`, `ssgtUuid`, and `defaultSsgtFilter`.
- For **SSL Herr 2025/26** (seasonUuid `u19i105cb7`, seriesUuid `qRl-8B5kOFjKL`), the `gameType` list currently includes only `regular` (Seriematch).
  - This likely means playoffs use a different seriesUuid or are not yet active in this dataset.

### Events / play-by-play (SSL)
- `sports-v2/game-info/{gameUuid}` returns core metadata (teams, scores, venue, OT/PS flags), but no detailed events.
- `gameday/play-by-play` and `gameday/play-by-play/initial-events` endpoints returned empty bodies for tested games, and some `gameday/*` endpoints return 404/500 without additional auth or parameters.

### Svenska IBF Stats App (stats.innebandy.se) — event data confirmed
- The match pages on `stats.innebandy.se` are a JS app that pulls data from **api.innebandy.se**.
- A public bootstrap endpoint provides an access token and API root:
  - `GET https://api.innebandy.se/StatsAppApi/api/startkit` → returns `accessToken` + `apiRoot` (currently `https://api.innebandy.se/v2/api/`).
- With the token, **match events are available** at:
  - `GET {apiRoot}matches/{MatchID}` → returns match metadata plus `Events` array.
  - Example: match `1571924` returns a populated `Events` list (goals, penalties, period start, etc.).
- Other discovered endpoints (from the stats app bundle):
  - `matches/{id}/lineups`
  - `competitions/{id}/matches`
  - `competitions/{id}/standings`
  - `seasons/`
  - `federations/` and `federations/{id}/competitions`

### Playoffs representation (SSL)
- SSL navigation includes **Slutspel Herr** and **Slutspel Dam** routes, suggesting playoffs are a separate phase/page.
- The `gameTypeUuid` parameter and the `/sports-v2/season-series-game-types-filter` endpoint indicate that regular season vs playoff games are likely separated by game type.
- The `/slutspelet-herr` page currently appears to be informational content (no embedded playoff schedule IDs found in the HTML).

### Playoffs representation
- iBIS likely represents playoffs as distinct competitions or phases under the same federation system. This is not explicitly documented on the public API service page and requires API inspection once access is granted. citeturn0search0

### Integration notes
- Best path is to apply for iBIS API access and consume via OAuth2.
- If access is not granted, fallback to scraping federation/league HTML pages (not documented here).

---

## Finland (F‑liiga)

### Primary portals
- F‑liiga official site: `https://fliiga.com/en/` (schedule/results and game center pages). citeturn1view1
- Results lists include explicit OT and PS markers in match results. citeturn1view1
- Results service root is a JS‑only SPA: `https://tulospalvelu.fliiga.com/` (requires JS to load). citeturn1view0
- A second SPA host exists at `https://fliiga.dev.torneopal.fi/` (also JS‑only; same "enable JavaScript" shell). citeturn1view2turn1view1

### JSON / API backend
- No JSON or API endpoints are exposed in the static HTML of the F‑liiga front page; the page is server‑rendered. citeturn1view1turn6view0turn6view1
- The **results service is JS‑only** and likely fetches JSON, but endpoints are not visible without runtime network inspection. citeturn1view0
  - Action: open the results service in a browser, capture XHR/Fetch calls, and document endpoints + parameters.

### Playoffs representation
- Playoff phase in schedules likely exists in the SPA results service, but requires runtime inspection to confirm endpoints and filters. citeturn1view0

### Integration notes
- Short‑term: scrape server‑rendered F‑liiga HTML pages for schedules/results and OT/PS markers. citeturn1view1
- Mid‑term: reverse‑engineer JSON calls from the SPA results service for structured schedules/results. citeturn1view0

---

## Switzerland (Swiss Unihockey / L‑UPL)

### Primary portals
- Swiss Unihockey Hub / Game‑Center ecosystem (official). citeturn0search3
- Swiss Unihockey Webmaster page documents an official API v2 and a public “Klick‑In” iFrame service for schedules/standings. citeturn0search1turn0search2

### JSON / API backend
- **Official API v2** with documentation at `https://api-v2.swissunihockey.ch/api/doc`. citeturn0search1turn0search2
  - API access requires key/secret (request via swiss unihockey IT). citeturn0search1turn0search2

### Playoffs representation
- Hub roadmap explicitly mentions “Playoff Darstellung” (playoff display). citeturn0search3turn0search6
- Expected representation: playoff series within Hub/API; confirm via API endpoints after access.

### Integration notes
- Best path: use official API v2 with key/secret.
- Secondary: scrape Hub/Game‑Center HTML or Klick‑In iFrames if API access delayed.

---

## Czech Republic (Český florbal / Livesport Superliga)

### Primary portals
- Official federation site with Livesport Superliga competition pages:
  - Matches: `https://www.ceskyflorbal.cz/competition/detail/matches/8XM1`
  - Overview: `https://www.ceskyflorbal.cz/competition/detail/overview/8XM1`
  - Statistics: `https://www.ceskyflorbal.cz/competition/detail/statistics/8XM1`
  citeturn3view0turn3view1turn3view2

### JSON / API backend
- The competition pages are **server‑rendered HTML**; no obvious JSON/GraphQL endpoints are present in the HTML source. citeturn4view0turn4view1turn4view2turn5view0turn5view1

### Playoffs representation
- Competition detail pages do not show a dedicated “playoff” phase label for Livesport Superliga in the static HTML. citeturn5view0turn5view2turn5view3
- Navigation references a separate Superfinale site, which may indicate a separate competition/final stage. citeturn4view0turn5view4
  - Action: identify if playoffs are separate competition IDs and inspect those pages for structured data.

### Integration notes
- Short‑term: scrape server‑rendered HTML for fixtures/results. citeturn3view0
- Mid‑term: attempt to discover hidden JSON endpoints by monitoring network calls in a browser session.

---

## Cross‑League Summary

### Official APIs confirmed
- Sweden: iBIS API (restricted access; OAuth2). citeturn0search0
- Switzerland: Swiss Unihockey API v2 (key/secret). citeturn0search1turn0search2

### JS‑only portals requiring network reverse engineering
- Finland: tulospalvelu.fliiga.com (SPA). citeturn1view0

### Server‑rendered HTML suitable for scraping
- Finland: F‑liiga schedules/results include OT/PS markers. citeturn1view1
- Czech Republic: Ceskyflorbal competition pages. citeturn3view0turn3view1turn3view2

---

## Next Actions (Concrete)

1. **Finland (F‑liiga)**
   - Open `https://tulospalvelu.fliiga.com/` in a browser and capture network calls for schedules/results.
   - Identify JSON endpoints and auth requirements.

2. **Czech Republic**
   - Inspect competition pages for playoff phase IDs and whether playoff rounds are separate competitions.
   - Test if any XHR calls appear in DevTools; if so, document JSON endpoints.

3. **Sweden**
   - Apply for iBIS API access; confirm endpoint coverage for SSL + playoffs.

4. **Switzerland**
   - Request API v2 key/secret; confirm endpoints for competitions + playoff series.

---

## Notes on Playoff Representation

Because each federation portal differs:

- Sweden/Switzerland (API‑driven): playoffs are likely separate competitions or phase flags within the same season.
- Finland/Czech (HTML‑driven): playoffs are likely separate competition pages and may require identifying a different competition ID.

The **rule profile** and **phase** handling in your platform should treat playoffs as a first‑class phase that can be mapped per league/season.
