# Analytics events (PostHog)

One schema for Floorball Stats (`stats.floorballconnect.com`, `themes/my-theme`) and Floorball Connect (`www.floorballconnect.com`, `themes/connect`). Event names are `snake_case`, code and properties are English.

All events go through `themes/shared/static/js/tracking.js` (`window.fbTrack`), which both themes load right after the PostHog snippet. Templates and scripts never call `posthog.capture` directly; `tests/test_tracking_js.py` fails if one does.

## Privacy and consent

- **Consent:** there is no consent banner and no consent rule in the code. The PostHog init in both `base.html` files runs in `cookieless_mode: 'always'` (nothing stored in the browser, daily rotating server-side hash, no `identify`), which is why none is needed. This change keeps that init as it is. `tracking.js` stores nothing either (no cookie, no `localStorage`), so it does not change that. Cookieless mode must stay enabled in the PostHog project settings.
- **Localhost:** PostHog is not initialised on `localhost`, `127.0.0.1` and `::1`. There `fbTrack` sends nothing and instead prints each event as `[Analytics][localhost] <event> <properties>` to the console and keeps them in `fbTrack.localLog()`.
- **No names, e-mail addresses or free text.** `fbTrack` only passes numbers, booleans and identifier-like strings (`[A-Za-z0-9_./:#=-]`, up to 80 characters, so no spaces and no `@`) and drops keys such as `query`, `name`, `email`, `message`, `href`. Search events carry the query length and result count, never the text. Team and player choices (head-to-head select, search results) are reported without the name.
- **Completion events** fire only after the thing really happened: the newsletter provider answered `success`, the share sheet resolved, the link was copied, the card was downloaded. Feedback is the exception, see below.

## Base properties (every `fbTrack` event)

| Property | Values |
|---|---|
| `site` | `stats` or `connect` (also registered as a PostHog super property, so `$pageview` carries it) |
| `page_path` | `location.pathname` |
| `page_type` | Stats: `home`, `league`, `league_players`, `leaders`, `stats_explained`, `player`, `game`, `team`, `page`. Connect: `home`, `collection`, `item`, `subscribe`. Derived from the path, meant for grouping |
| `league`, `season`, `phase`, `division` | Only where the URL has a category slug (`se-26-27-regular-season`): league code (`de` for Germany's men, which has no prefix), `26-27`, `regular-season` or `playoffs`, `men` or `women` |

## Events

| Event | Fires when | Event properties |
|---|---|---|
| `cta_clicked` | A CTA is clicked (link or button) | `cta_id`, `cta_kind` (`link`, `button`, `support`, `calendar`, `share`), `destination` (host and path, `mailto` or `webcal`, no query) |
| `cta_viewed` | A CTA block is at least half in view, once per page | `cta_id` (`support-banner`) |
| `cta_completed` | The CTA's goal was reached | `cta_id` plus: newsletter `cta_kind: newsletter`; share `share_method` (`share_sheet`, `copy_link`, `download`), card shares also `share_kind`, `share_format`, `share_theme`; feedback `feedback_type`, `completion: mail_draft_opened` |
| `cta_failed` | The attempt did not go through | `cta_id`, `reason` (`rejected` provider answer, `network`, `share_error`), `cta_kind` or `share_kind`, `error_name` |
| `filter_changed` | A filter, tab or view switch changes (clicking the option that is already selected does not count) | `filter_name`, `filter_value`, `filter_scope` (`nav`, `home`, or the control group: its `data-track-group` or `aria-label`, e.g. `table_columns`, `games`) |
| `search_opened` | The header search dialog opens | `search_scope` |
| `search_used` | Typing in a search box paused for 800 ms with at least 2 characters and the query differs from the last reported one | `search_scope`, `query_length`, `token_count`, `results_count`, `has_results` |
| `search_result_clicked` | A header search result is opened | `search_scope`, `result_type` (`team`, `player`), `result_position` (1 = first) |

Plus the automatic `$pageview` (`capture_pageview: true`, unchanged).

### CTA ids

| `cta_id` | Where | Click | Completed |
|---|---|---|---|
| `header` | "Join for free" in the shared header (both sites) | yes | on the subscribe page as `signup-<form id>` |
| `signup-<form id>` (e.g. `signup-signup-page`) | Newsletter forms on Connect (`data-signup`) | submit button click | `cta_completed` after MailerLite answers `success`; `cta_failed` otherwise |
| `footer-newsletter` | Newsletter link in both footers | yes | on the subscribe page |
| `hero-stats`, `hero-reviews`, `teaser-stats`, `teaser-leaders`, `review-<collection>`, `outbound-<collection>`, `youtube-<collection>` | Connect home, collection and item pages | yes | external or on-page, not measurable |
| `support-card`, `support-footer` | Support banner and footer link on Stats | yes (`cta_viewed` for the banner) | external, not measurable |
| `calendar-apple`, `calendar-google`, `calendar-download` | Team calendar links | yes | calendar app or download, not measurable |
| `feedback` | Feedback dialog on Stats | opening the dialog | submitting the form (see below) |
| `share-page` | Share button on Connect items | yes | share sheet resolved or link copied |
| `share-card` | Share studio (Instagram cards) on Stats | opening the studio | download or share sheet resolved |

**Feedback:** the form builds a `mailto:` link, so the browser can only report that the mail draft was opened (`completion: mail_draft_opened`), not that the message was sent.

**Funnel for "Join for free":** `cta_clicked(header)` → page view of `/subscribe/` → `cta_completed(signup-subscribe)`. Cookieless mode has no cross-page session, so link the steps by funnel, not by a stored id.

### Filter names

| `filter_name` | Control | Values |
|---|---|---|
| `division` | Men/Women switch in the league menu, on the home page and leaders page, and the live block on Connect | `men`, `women` |
| `league` | League menu and league cards on the home page (clicking a league or season link) | league code; the target's `target_season` and `target_phase` travel along |
| `view` | Segment buttons: table columns (Table, Per game, Special teams), Results/Upcoming, Ratings/Projections, Points/game, Goal diff | the `data-view` value |
| `games_tab`, `game_view`, `playoff_round` | Tabs on team, league and game pages | tab key, round number |
| `facet` | Facet chips on Connect collection pages | slug of the facet, `all` |
| `h2h_team` | Team selects in the head-to-head view | no value (a team name) |

The player list's own filter is a text search, so it is a search event (`search_scope: category_players`, `player_stats_page`).

### Search scopes

`site` (header dialog for teams and players), `category_players`, `player_stats_page` (player tables), `connect_collection` (search box on Connect collection pages).

## What changed from the previous events

| Before | Now |
|---|---|
| `global_search_opened` (`page_path`, `page_title`) | `search_opened` |
| `global_search_used` (**raw `query`**, `query_length`, `result_count`, `search_scope`) | `search_used` without the text; debounced 450 ms → 800 ms, minimum 2 characters, `results_count` |
| `global_search_result_clicked` (**raw `query`**, `result_name`, `result_type`, `result_url`) | `search_result_clicked` with type and position only |
| `player_search_used` (`query_length`, `token_count`, `results_count`, `total_rows`, `page_path`, `search_context`) | `search_used` with `search_scope`; `total_rows` is dropped |
| `nav_division_switched` (`division`, `path`) | `filter_changed` (`division`); the division switch on the home and leaders pages is now counted too |
| `calendar_subscribe_clicked` (`kind`, `path`) | `cta_clicked` (`calendar-<kind>`) |
| `support_cta_clicked` (`placement`, `path`), `support_cta_viewed` | `cta_clicked` (`support-<placement>`), `cta_viewed` (`support-banner`) |
| `share_card_opened` / `_downloaded` / `_shared` / `_failed` | `cta_clicked` / `cta_completed` (`share_method: download`) / `cta_completed` (`share_method: share_sheet`) / `cta_failed`, all with `cta_id: share-card` |
| Connect `cta_clicked` (`cta`, `href`) | `cta_clicked` (`cta_id`, `destination`); Stats' "Join for free" and footer links were not tracked before |
| Connect `newsletter_signup` (`form`) | `cta_completed` (`signup-<form id>`); failures are new (`cta_failed`) |
| Path property `path` / `page_path` mixed | always `page_path` |

Existing insights or dashboards that use the old names need to be pointed at the new ones. Old and new events do not overlap in time after this ships.

## Adding an event

1. Prefer markup over code: `data-cta="<id>"` on a link or button (`cta_clicked`), `data-track-filter="<name>"` plus `data-track-value="<value>"` on a button (`filter_changed`), optionally grouped with `data-track-group="<scope>"`, `data-track-view="<id>"` for `cta_viewed`.
2. In scripts, use `fbTrack.ctaCompleted(id, props)`, `fbTrack.ctaFailed(id, reason, props)`, `fbTrack.filterChanged(name, value)` or `fbTrack.searchTracker(scope)` (call `.update(text, resultCount)` on every filter run; it debounces and drops the text). Guard with `window.fbTrack ||` so the page still works if the script is missing.
3. Add the event or id to this file and a case to `tests/js/tracking.test.js`.

## Checking events

- Tests: `.venv/bin/python -m pytest tests/test_tracking_js.py` (runs `node --test tests/js/tracking.test.js`).
- In the browser on a local build, read the console (`[Analytics][localhost]` lines) or `fbTrack.localLog()`. On a deployed page, filter the network tab for `e.floorballconnect.com` and look at the `/e/` or `/batch/` payload (events are batched, `cta_completed` is sent immediately).
