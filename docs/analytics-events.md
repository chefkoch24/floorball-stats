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

### Buttons and CTAs: named after the button

A CTA event is `<button name>_<step>`, where the button name is the snake_case of what the button says (or does) and the step is `clicked`, `completed`, `failed` or `viewed`. So "Join for free" is `join_for_free_clicked`, and the newsletter sign-up is `newsletter_signup_clicked`, `newsletter_signup_completed`, `newsletter_signup_failed`. Every CTA event also carries `cta` (the button name) and `cta_step`, so all CTAs can still be grouped with one property filter.

| Property | Meaning |
|---|---|
| `cta`, `cta_step` | button name, `clicked` / `completed` / `failed` / `viewed` |
| `cta_kind` | `link`, `button`, `calendar`, `share`, `newsletter` |
| `cta_placement` | where it sits: `header`, `footer`, `card`, `hero`, `teaser`, the form (`signup-page`, `signup-footer`) |
| `cta_detail` | the collection it belongs to (`sticks`, `drills`, ...) |
| `destination` | host and path of the link (`mailto` or `webcal` as such, no query) |
| `reason` | on `_failed`: `rejected` (provider said no), `network`, `share_error` |
| `share_method`, `share_kind`, `share_format`, `share_theme`, `feedback_type`, `completion` | on `_completed` of share and feedback, see below |

| Button (what it says) | Events | Where | Completed when |
|---|---|---|---|
| Join for free | `join_for_free_clicked` | header, both sites | the visitor signs up: `newsletter_signup_completed` on the subscribe page |
| Join now (newsletter form) | `newsletter_signup_clicked`, `_completed`, `_failed` | Connect subscribe page and footer form | MailerLite answered `success`; `_failed` with `reason` when it did not or was unreachable |
| Newsletter | `newsletter_clicked` | footer link, both sites | on the subscribe page, see above |
| Support Floorball Stats | `support_floorball_stats_viewed`, `_clicked` | support banner on Stats | external page, not measurable |
| Support | `support_clicked` | Stats footer | external page, not measurable |
| Feedback | `feedback_clicked`, `feedback_completed` | Stats footer and menu | the form was submitted; `completion: mail_draft_opened` (the form builds a `mailto:` link, so only the draft opening is known, not that the mail was sent) |
| Share (page) | `share_page_clicked`, `_completed`, `_failed` | Connect item pages | share sheet resolved or link copied (`share_method`) |
| Share (card) | `share_card_clicked`, `_completed`, `_failed` | Stats share studio | download or share sheet resolved (`share_method: download` / `share_sheet`) |
| Apple / Outlook, Google, .ics | `calendar_apple_outlook_clicked`, `calendar_google_clicked`, `calendar_ics_download_clicked` | team calendar | calendar app or download, not measurable |
| Explore league stats, Read stick reviews | `explore_league_stats_clicked`, `read_stick_reviews_clicked` | Connect home hero | on-site navigation |
| Open Floorball Stats, Leaders across all leagues | `open_floorball_stats_clicked`, `leaders_across_all_leagues_clicked` | Connect home teaser | on-site navigation |
| Write a review / Review this ... | `write_a_review_clicked` (`cta_detail` = collection) | Connect collection and review pages | external form, not measurable |
| Play video | `play_video_clicked` (`cta_detail` = collection) | Connect item pages | |
| View product / Go to the deal | `view_product_clicked`, `go_to_the_deal_clicked` (the collection's link label) | Connect item pages | external, not measurable |

A new button gets its event by adding `data-cta="<snake_case label>"` to it.

### Filters and search

| Event | Fires when | Properties |
|---|---|---|
| `filter_changed` | A filter, tab or view switch changes (clicking the option that is already selected does not count) | `filter_name`, `filter_value`, `filter_scope` (`nav`, `home`, or the control group: its `data-track-group` or `aria-label`, e.g. `table_columns`, `games`) |
| `search_opened` | The header search dialog opens | `search_scope` |
| `search_used` | Typing in a search box paused for 800 ms with at least 2 characters and the query differs from the last reported one | `search_scope`, `query_length`, `token_count`, `results_count`, `has_results` |
| `search_result_clicked` | A header search result is opened | `search_scope`, `result_type` (`team`, `player`), `result_position` (1 = first) |

Plus the automatic `$pageview` (`capture_pageview: true`, unchanged).

**Funnel for "Join for free":** `join_for_free_clicked` → page view of `/subscribe/` → `newsletter_signup_completed`. Cookieless mode has no cross-page session, so link the steps by funnel, not by a stored id.

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
| `calendar_subscribe_clicked` (`kind`, `path`) | `calendar_apple_outlook_clicked`, `calendar_google_clicked`, `calendar_ics_download_clicked` |
| `support_cta_clicked` (`placement`, `path`), `support_cta_viewed` | `support_floorball_stats_clicked` / `_viewed` (banner), `support_clicked` (footer) |
| `share_card_opened` / `_downloaded` / `_shared` / `_failed` | `share_card_clicked` / `share_card_completed` (`share_method: download`) / `share_card_completed` (`share_method: share_sheet`) / `share_card_failed` |
| Connect `cta_clicked` (`cta`, `href`) | one event per button, e.g. `explore_league_stats_clicked` (property `cta`, `destination` instead of `href`); Stats' "Join for free" and footer links were not tracked before |
| Connect `newsletter_signup` (`form`) | `newsletter_signup_completed` (`cta_placement` = form); failures are new (`newsletter_signup_failed`) |
| Path property `path` / `page_path` mixed | always `page_path` |

Existing insights or dashboards that use the old names need to be pointed at the new ones. Old and new events do not overlap in time after this ships.

## Adding an event

1. Prefer markup over code: `data-cta="<snake_case label>"` on a link or button (`<label>_clicked`, with optional `data-cta-placement` and `data-cta-detail`), `data-track-filter="<name>"` plus `data-track-value="<value>"` on a button (`filter_changed`), optionally grouped with `data-track-group="<scope>"`, `data-track-view="<button name>"` for `<button name>_viewed`.
2. In scripts, use `fbTrack.ctaCompleted(buttonName, props)`, `fbTrack.ctaFailed(buttonName, reason, props)`, `fbTrack.filterChanged(name, value)` or `fbTrack.searchTracker(scope)` (call `.update(text, resultCount)` on every filter run; it debounces and drops the text). Guard with `window.fbTrack ||` so the page still works if the script is missing.
3. Add the event or id to this file and a case to `tests/js/tracking.test.js`.

## Checking events

- Tests: `.venv/bin/python -m pytest tests/test_tracking_js.py` (runs `node --test tests/js/tracking.test.js`).
- In the browser on a local build, read the console (`[Analytics][localhost]` lines) or `fbTrack.localLog()`. On a deployed page, filter the network tab for `e.floorballconnect.com` and look at the `/e/` or `/batch/` payload (events are batched, `*_completed` events are sent immediately).
