# Team logos: research and implementation

Research date: 1 November 2026. The backlog asks for club logos with league/club rights checks and monogram fallback. This is an initial source survey, not an individual clearance of every club or legal advice.

## Findings

The [inventory](TEAM_LOGO_INVENTORY.md) lists 153 team entries across 14 current domestic league datasets. It is a local snapshot; teams may appear in more than one competition or under multiple names. On 1 November 2026 Felix confirmed that he has permission for all club logos for this website, including local storage, and subsequently for share images and link previews. This is a user assertion, not independently verified documentation. All 153 current domestic team entries and 16 Champions Cup mappings are prepared for the corresponding competition data. Historical seasons still need their own identity and season mapping.

- Germany: [Floorball Deutschland](https://floorball.de/) says clubs maintain team logos in Saisonmanager. Its [Bundesliga page](https://floorball.de/bundesliga/) lists team contacts, a potential route to permissions. Neither is a demonstrated grant for Floorball Stats. The [imprint](https://floorball.de/impressum/) restricts copies of the site's own content, so a public image must not be presumed reusable.
- Switzerland: [GC Unihockey offers its logo for download](https://www.gc-unihockey.ch/sektion/verein/downloads/). [Wikimedia Commons lists floorball logos](https://commons.wikimedia.org/wiki/Category:Floorball_logos), including [Floorball Köniz](https://commons.wikimedia.org/wiki/File:Logo_FloorballKoeniz.svg) and [Kloten-Dietlikon Jets](https://commons.wikimedia.org/wiki/File:Logo-kloten-dietlikon-jets.svg). These are leads, not clearance for our specific use; verify each source, license, uploader's authority and trademark position.
- Sweden, Finland, Czech Republic, Slovakia and Latvia: no league-wide permission was established in this survey. Check official competition/team sources and ask the appropriate rights holders. An absence of discovered permission is not a conclusion that permission is legally required or that use is forbidden.
- [Creative Commons explains](https://creativecommons.org/faq/) that CC copyright licenses do not themselves license trademark rights. A file, a press download, or another website displaying it is not by itself proof of permission for this website, including potential commercial use.

## Implementation and operations

The site supports locally hosted, manually reviewed PNG/JPEG/WebP logos in `themes/my-theme/static/team-logos/` with the existing monogram as fallback. Logo data is a small editorial rights registry, separate from scraped league data and the Neon/SQLite match databases; no full data refresh is needed. The registry records Felix’s blanket permission and each logo’s image source. Domestic sources include league organisers, team sites and swiss federation-sourced club listings; Champions Cup entries use the corresponding domestic team’s same-season logo. Team names are matched exactly (ignoring case and surrounding whitespace), with explicitly listed competition prefixes and seasons to avoid accidental cross-league or historical matches. Men's, women's and Champions Cup uses require their own explicit mapping. A missing file, expired permission, invalid record, unknown competition or ambiguous match falls back to the monogram. Images are decorative next to the team name; a load error also exposes the monogram.

To activate a logo, record the basis for permission covering display on stats.floorballconnect.com and local hosting, along with any known credit requirements or conditions. Felix confirmed blanket permission on 1 November 2026; no separate written permissions were provided. Keep the evidence accessible; do not put private correspondence in the public repository. Confirm identity and that the supplied image and current branding match the relevant team. Convert to a safe raster file if necessary, without changing the mark's appearance, and preserve transparency and proportions. Add a record to `config/team_logos.json`:

```json
{
  "team": "Exact team name from site data",
  "league_prefixes": ["ch-"],
  "seasons": ["26-27"],
  "file": "club-name.png",
  "status": "approved",
  "rights_holder": "Rights holder",
  "source_url": "https://example.org/official-source",
  "permission_evidence": "Reference to retained permission or reviewed public grant",
  "reviewed_on": "2026-11-01",
  "expires_on": "2027-12-31",
  "scope": ["website"]
}
```

`expires_on` is optional if permission has no stated end. This registry is build-time and fail-closed, not an automated legal determination: a reviewer must verify the evidence and restrictions before setting `approved`. Any credit requirement must be implemented before activation. Revoked rights require removal or changing status and a rebuild. Felix confirmed use in share images and link previews on 1 November 2026. Publishing Instagram posts and Stories still requires separate explicit approval of the exact version, as specified in AGENTS.md. Other products such as PDFs are outside this scope. Update the inventory when an individual review is completed; keep the backlog task open until coverage and rights have been resolved.
