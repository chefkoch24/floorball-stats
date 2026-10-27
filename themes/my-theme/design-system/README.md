Floorball Stats shows standings, results and numbers from Europe's top floorball leagues, men and women. The reader is a fan, player or parent checking a result, a table or a team's form on their phone. The design gets out of the way of the numbers: quiet surfaces, one blue accent from the sports-hall floor, the orange of the ball for what is happening right now, and scores set large in a widened grotesque.

## Content fundamentals

- Write the UI in English, sentence case: "Regular season", "Show standings", "Add games to calendar". Uppercase only through the `label` style (column headers, stat labels).
- Use the sport's own terms and abbreviations, explained once in a stat guide per page: GP, W, OTW, OTL, L, GD, Pts, PP% (power play), BP% (box play / penalty kill), OT, PS (penalty shots).
- Team and league names stay exactly as the federation writes them, diacritics included: "FBC ČPP MPL Stavebniny Ostrava", "Täby FC IBK", "ELVI līga sievietēm".
- Dates read "Sat 31 Oct", times in 24-hour local time of the venue ("15:30"). Seasons are "26/27".
- Scores use a colon with no spaces ("3:10"); goal difference always carries its sign ("+28", "−4").
- Numbers: two decimals for per-game rates (2.83), one decimal for percentages (54.6%), whole numbers for counts. Never invent or round to make a number look better; a missing value is "–".
- No emoji, no exclamation marks, no hype. A result is a fact.

## Visual foundations

**Colour.** Neutrals carry a slight blue bias. Pages sit on `surface`; panels, tables and cards on `surface-raised`; table heads and zebra rows on `surface-sunken`. Text is `ink`, secondary text `ink-muted`. The one accent is `rink` (links, active segment, primary button, focus ring) with `on-rink` text on it and `rink-soft` for the followed row and hovered cards. `ball` is reserved for "now": the Live badge, a goal on the momentum line, the playoff cut. Results use `win`, `loss` and `otl` on their `-soft` grounds and always with a letter (W, L, OTW, OTL), never colour alone. Team crests use `crest-1` to `crest-8` with `on-crest` initials. Every text colour reaches 4.5:1 on the grounds its note names, in both themes.

**Type.** Two families from Google Fonts. Archivo (`display`) sets everything that is a number or a title: `score` widened (font-stretch 112%), `display-xl`, `heading-lg` and `heading-md` condensed (75–85%), `stat-value` and `data` at normal width with tabular figures. Instrument Sans (`body`) sets running text (`body`, `body-sm`), `label` and `caption`. Numbers that line up in columns always use `font-variant-numeric: tabular-nums`. Headings get `text-wrap: balance`.

**Spacing and layout.** A 4px grid: `space-1` to `space-12`. Content max width 1200px with a 16px minimum gutter (`space-4`), 24px panel padding on desktop (`space-6`), 32px between sections (`space-8`). Pages are built mobile first: tables scroll inside `fs-table-wrap` with the team column pinned; the score strip scrolls inside itself; the page body never scrolls sideways.

**Radii, borders, shadows.** `radius-sm` for chips, pills and inputs, `radius-md` for cards and tiles, `radius-lg` for page panels and the scoreboard, `radius-pill` for badges, the segmented track and crests. Panels are separated by a `line` hairline, never by shadow. `shadow-menu` is only for things that float: the league menu and the search dialog. Control borders use `line-strong`.

**States.** Hover on cards and links moves the border or text to `rink`. Keyboard focus is a solid 2px `rink` outline with a 2px offset on every interactive element. Disabled phases are dashed chips in `ink-muted`.

**Motion.** Almost none. The Live dot pulses; page changes may use a cross-fade view transition. Everything respects `prefers-reduced-motion`.

**Charts.** Draw with the same tokens: series in `rink` and `ink-muted` (home and away), goals as `ball` dots, gridlines in `line`, labels in `ink-muted` `caption`. One scale per axis, labels only at values the chart reaches, no 3D, no gradients.

## Iconography and imagery

There is no icon set and no logo yet: the name is set in Archivo. Labels are words ("Playoffs", "Download .ics"), not icons. Teams appear as monogram crests (`TeamCrest`), never as club logos, because those are the clubs' trademarks. No photos.

## Building with this system

The website (Pelican, Jinja templates) uses Tailwind CSS v4. The tokens become Tailwind theme colours and spacing (`bg-surface-raised`, `text-ink-muted`, `border-line`, `text-rink`, `rounded-md`, `p-6`), and the components below are CSS classes with the `fs-` prefix in `components/bundle.css`: `fs-btn`, `fs-chip`, `fs-status`, `fs-segmented`, `fs-crest`, `fs-team`, `fs-form`, `fs-stat`, `fs-match`, `fs-strip`, `fs-scoreboard`, `fs-table`, `fs-league-card`. Use a component class for a recurring part and Tailwind utilities for page layout around it. Never hard-code a colour or size that exists as a token. The dark theme follows `data-theme="dark"` on `<html>`.
