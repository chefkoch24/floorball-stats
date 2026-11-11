# Team Map Plan

Date: 2026-11-11

## Goal

Every league page gets a map of its country: only the outline (country border, maybe the regions), no street map. Each club sits at its home town with its logo. Hovering a logo shows the team name and its table place; clicking opens the team page.

## Decisions (Felix, 2026-11-11)

| Question | Decision |
|---|---|
| Where | A section on every league page (regular season), showing only that league's teams |
| Precision | Home town, not the arena |
| Scope v1 | All 7 countries, men and women, 1st leagues 26/27 (153 teams in `config/team_logos.json`) |
| Interaction | Hover tooltip (name, place, points) and click to the team page. No zoom or pan |

## Status (2026-11-11)

Built for all 7 countries, men and women, current and 25/26 regular seasons: `src/team_map.py`, `config/team_locations.json` (146 teams), `config/maps/<iso2>.json` (Latvia without regions, Natural Earth only has its 119 municipalities). The special teams scatter on league pages uses club logos instead of initials.

Assumed locations, not confirmed by a source: Floorball BB United (Berlin, Felix), NND/RJTC and Sparta (Latvian women, Rīga).

## What already exists

- Logos for all 153 teams: `config/team_logos.json` and `themes/my-theme/static/team-logos/`.
- Team pages and table data per league from the build.

## What is missing

1. **Home town coordinates per team.** No location data exists in the repo today.
2. **Country outlines.** Not in the repo.
3. **The map section in the league template.**

## Approach

### 1. Locations: `config/team_locations.json`

A curated manifest next to the logo manifest, keyed the same way (team name + league prefix, ideally the source team id where the logo manifest has one):

```json
{ "team": "Floorball Chur United", "league_prefixes": ["ch-"], "town": "Chur", "lat": 46.85, "lon": 9.53 }
```

- Filled once with a script: town name from the team name or the club website, coordinates from Wikidata or OpenStreetMap Nominatim (one request per town, cached, the generic client name as User-Agent).
- Reviewed by hand in the pull request, because team names do not always contain the town (sponsor names, merged clubs).
- Women's teams of the same club reuse the men's entry.
- Maintenance: promoted teams at the season rollover, the same step as for logos.

### 2. Outlines: static SVG per country, made once

- Source: Natural Earth admin-0 (public domain), 1:10m for the small countries (Latvia, Slovakia, Switzerland).
- A small script projects each of the 7 countries (simple equirectangular projection with a cos(latitude) factor is enough at country size) and writes `themes/my-theme/static/maps/<country>.svg` plus its bounding box.
- Generated once and committed. No map library, no tiles, no external request at runtime.

### 3. Build: map data per league

- A Pelican plugin step (or the existing league page generation) joins table rows, logos and locations into a list of `{team, url, logo, x, y, place, points}` per league, with x/y already projected into the SVG coordinates.
- Teams without a location are left out of the map and logged as a warning in the build, so gaps are visible.

### 4. Template and front end

- New section "Teams on the map" on the league page: inline SVG outline, logos as `<a><image></a>` elements on top.
- Theme colours from the existing design tokens, light and dark mode.
- Hover/focus tooltip with a few lines of vanilla JS; keyboard focus works through the links.
- Towns with several teams (Prague, Helsinki, Zürich area, Riga): logos of the same town fan out in a small circle around the point, so none hide each other. Short leader line to the point.
- Mobile: map scales to the width; logos stay at a minimum tap size.

## Effort

| Step | Time |
|---|---|
| Outline SVGs for 7 countries (script + check) | 1–2 h |
| Locations for 153 teams (script + manual review) | 2–3 h, most of it review |
| Build join + template + tooltip + fan-out | 3–4 h |
| Dark mode, mobile, tests | 1–2 h |
| **Total** | **about 1–1.5 days** |

## Risks and open points

- **Clusters:** Czech and Finnish leagues have several teams in one city. Fan-out handles a few; if a city has more than ~5 teams the circle gets big. Check with real data first.
- **Name ≠ town:** sponsor names hide the town. That is why the locations get a manual review step.
- **Champions Cup / WFC:** out of scope for v1 (needs a Europe map).
- **Later options:** zoom for clusters, a Europe map of all leagues, the map as a share graphic.
