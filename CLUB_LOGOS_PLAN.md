# Club Logos Plan

Date: 2026-10-30

## Goal

Show each club's real logo wherever the site shows a team (tables, match cards, power ranking, table history, team pages, later share images) instead of the monogram crest, with the monogram as the fallback.

## Short answer: is it a one-time job?

Mostly yes. The bulk work is once: map every team to its logo, download it, normalise it, commit it. After that the site serves the logos from its own files on every build.

Maintenance remains in four places, all small:

1. **Promoted teams**, once per season at rollover (`README.md` season rollover checklist gets one step).
2. **Rebrands**: a club changes its logo, roughly a handful per season across all leagues. A monthly check of the source URLs catches them.
3. **Sponsor renames**: names like "UHC Sparkasse Weißenfels" or "FBC ČPP MPL Stavebniny Ostrava" change with sponsors. Mapping by the source's team id instead of the name keeps the logo attached (see Mapping).
4. **New leagues**: each new backend needs its logo source once.

## Research: where the logos come from

Checked on 2026-10-30 with one or two requests per source. 153 teams play in the 14 regular seasons of 26/27. Many women's teams share their club's logo, so the number of distinct logos is lower.

| League | Source | How we get it | Sample format | Status |
|---|---|---|---|---|
| Sweden (SSL, SSL Damer) | StatsApp API we already call (`competitions/{id}/matches`) | `HomeTeamLogotypeUrl` / `AwayTeamLogotypeUrl` on every match, plus `HomeTeamID` | PNG 400×441, transparent | Confirmed, best source |
| Switzerland (L-UPL, Damen) | `api-v2.swissunihockey.ch/api/rankings` | Cloudinary URLs in the ranking rows. The `t_club_logo_small` transform is 50×50, the same id without the transform is the original | PNG up to 1182×926, transparent | Confirmed |
| Finland (F-Liiga, Naiset) | fliiga.com match page we already scrape | Club logos in `wp-content/uploads` (`logo-<club>-f-liiga-*.webp`), several with a separate `-dark-` variant | WebP 200×200, transparent | Confirmed; map by file name or by the match card that shows it |
| Slovakia (Extraliga, women) | szfb.sk results page we already scrape | `isfszfb.szfb.sk/UserImg/Competitor/<id>/…`, some as SVG | SVG or PNG ~100×100 | Confirmed; the competitor id is a stable key |
| Latvia (ELVI) | floorball.lv game protocol we already scrape (`/proto/…`) and team pages (`/komanda/<id>-…`) | `/i/pictures/<id>.png` for home and away | PNG 96×96 | Confirmed; small, enough for table size |
| Germany (1. FBL, Damen) | saisonmanager.de game pages the web fallback renders | Team logo `<img alt="<team>">` on every game page (see `tests/fixtures/saisonmanager/game-45906.html`), served through `/api/storage/blobs/proxy/…` | not measured | Logos confirmed on the pages. The API (key required) probably carries them too; check with the key |
| Czech Republic (Extraliga, ženy) | ceskyflorbal.cz | Not checked: the site answers datacenter IPs with 403. Check from the local Czech job | – | Open |
| Champions Cup, WFC | – | Reuse the national league logos; clubs from other countries (and WFC flags) are sourced by hand or keep the monogram | – | Phase 3 |

Nothing has to be scraped from sites we don't already read, and most logos come with a stable team id from the source.

## Rights and risks (decide before building)

Club logos are the clubs' trademarks, and the logo artwork is protected by copyright. Our own brand book says so today ("Teams appear as monogram crests, never as club logos, because those are the clubs' trademarks"), so this plan changes a deliberate decision.

- **Common practice:** Result sites (Flashscore, Sofascore, the league sites themselves) show club logos to identify teams. That use, a logo next to the name in a table, is the least risky.
- **Higher risk:** Logos on share images and social posts can look like official club or league material. The same goes for any paid or premium feature (the SaaS direction in `VISION.md`).
- **Data terms:** The Swedish iBIS API terms restrict access (see `LEAGUE_PORTALS_RESEARCH.md`). We use the public StatsApp API, so its terms should be read once before we store its images.

Options:

| Option | What it means | Effort | Risk |
|---|---|---|---|
| A. Ask the leagues | One email per federation asking to use their clubs' logos for identification on the site; most want the visibility | 7 emails, waiting time | Lowest |
| B. Identification only, with opt-out | Logos in tables and lists only, a clear "logos belong to the clubs" note and a removal contact on the stats page | Small | Low to medium |
| C. Everywhere including share images | As B, plus logos on share cards and og:images | Small | Higher |

**Recommendation:** Start with B on the website and send the emails from A in parallel. Move to C only with the leagues' consent. This is not legal advice; for the premium plans it is worth a short check with a lawyer.

## Data model

A curated manifest, reviewed in pull requests like the league configs, plus the image files:

```text
config/club_logos.json                  # manifest, the build input
themes/my-theme/static/logos/<key>.webp # 256px, served as 2x
themes/my-theme/static/logos/<key>-64.webp
```

Manifest entry:

```json
{
  "key": "se-ibk-dalen",
  "league_prefixes": ["se-", "sew-"],
  "source": "sweden",
  "source_team_ids": ["4711"],
  "names": ["IBK Dalen"],
  "source_url": "https://ibis.innebandy.se/images/Forening/….png",
  "sha256": "…",
  "fetched": "2026-10-30",
  "dark_variant": false,
  "rights": "identification"
}
```

- **Why a file rather than Neon:** The mapping is curated, small (~150 entries) and needs human review (rights status, manual fixes). The Netlify build must work without the database. If an API needs it later, the manifest syncs to a `club_logos` table in one step.
- **Size:** ~150 logos × 2 sizes × 5 to 10 KB is about 2 to 3 MB in the repository.

## Mapping

- **Key:** the source's team id where there is one (Sweden, Switzerland, Slovakia, Latvia, probably Germany); otherwise `prefix + normalised name`.
- **Aliases:** `names` holds every spelling seen, so sponsor renames only add an alias. The scrapers already canonicalise names within a season (`run_stats_engine._canonicalize_team_names`). The logo lookup uses the same canonical name, which is what every template has.
- **Women's teams:** They point at their club's logo through `league_prefixes`.
- **Unmapped teams:** The build reports them and keeps the monogram. Logos are never guessed.

## Processing

`src/club_logos.py`, run by `make refresh-club-logos`. It is never part of the nightly refresh, so it cannot block it.

1. **Collect candidates** from the backends (logo URL + source team id + name). Sweden, Switzerland, Finland, Slovakia and Latvia need one extra field each in the existing scrapers. Germany reads the rendered game pages. Czech Republic runs in the local job.
2. **Download** only new or changed URLs, with the crawl delays the scrapers already respect.
3. **Normalise:**
   - Trim transparent padding and fit the logo into a square canvas.
   - Export WebP at 256 and 64 px.
   - Rasterise SVGs instead of serving them; SVG files can carry scripts.
4. **Flag** logos that would disappear on the dark theme (dark artwork on transparent background) by measuring the luminance of their opaque pixels against `surface` dark.
5. **Write manifest changes** with `rights: "pending"` for new entries, so a person reviews every new logo before it goes live.

A monthly check (or a step in the rollover checklist) re-runs 1 to 4 and opens a pull request for changed logos.

## Display

- **One place to change:** Every team image goes through the `fs-crest` component and the `crest_index` / `team_initials` filters, used in 7 templates, 3 plugins and `share-card.js`.
- **New filter and markup:** A `team_logo(team, category)` filter returns the logo path or nothing. `fs-crest` gets a logo variant (`<span class="fs-crest fs-crest--logo"><img …></span>`) with the initials as fallback.
- **Backdrop:** Logos sit on a fixed light rounded backdrop in both themes, so dark logos stay visible in dark mode. Finland's dark variants can replace the backdrop later.
- **Loading:** `loading="lazy"`, explicit width and height (no layout shift), and empty `alt` next to the visible team name.
- **Docs:** The design system README and the brand book line about logos change with this, plus a token for the backdrop.

## Delivery order

1. **Phase 0, decision:** choose an option under Rights. Send the league emails if A.
2. **Phase 1:** manifest, processing and site display for Sweden, Switzerland, Finland, Slovakia and Latvia (confirmed sources, about two thirds of the teams).
3. **Phase 2:**
   - Germany, from the web pages or the API with the key.
   - Czech Republic, from the local job.
   - The rollover checklist step and the monthly check.
4. **Phase 3:**
   - Champions Cup clubs from other countries.
   - Share cards and og:images, if the rights decision allows.

## Testing

- **Unit tests:**
  - name and alias mapping, including a sponsor rename
  - normalisation (output size, transparency kept, SVG rasterised)
  - dark-theme flag
- **Build check:** every current-season team has a logo or is listed as unmapped. A missing file falls back to the monogram, it never shows a broken image.
- **Visual check:** league, team and game pages in light and dark at 390 px and desktop.

## Open questions

1. Which rights option (A, B or C)?
2. Logos on share images and og:images, or website only?
3. Should promoted teams be mapped by hand at rollover, or should `make refresh-club-logos` run then and open a pull request?
