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
| Compare with another player | `compare_with_another_player_clicked` | button on player pages | the choice of a player on the comparison page: `compare_player_changed` |
| Explore league stats, Read stick reviews | `explore_league_stats_clicked`, `read_stick_reviews_clicked` | Connect home hero | on-site navigation |
| Open Floorball Stats, Leaders across all leagues | `open_floorball_stats_clicked`, `leaders_across_all_leagues_clicked` | Connect home teaser | on-site navigation |
| Write a review / Review this ... | `write_a_review_clicked` (`cta_detail` = collection) | Connect collection and review pages | external form, not measurable |
| Play video | `play_video_clicked` (`cta_detail` = collection) | Connect item pages | |
| View product / Go to the deal | `view_product_clicked`, `go_to_the_deal_clicked` (the collection's link label) | Connect item pages | external, not measurable |

A new button gets its event by adding `data-cta="<snake_case label>"` to it.

### Filters and search: named after the control

Same idea: `<control>_changed` for filters and tabs, `<search box>_used` for searches. The control name, the new choice and the scope are also properties (`filter_name`, `filter_value`, `filter_scope`), so "any filter" can still be grouped.

| Event | Control / fires when | Properties |
|---|---|---|
| `division_changed` | Men/Women switch (league menu with `filter_scope: nav`, home page, leaders page, Connect live block) | `filter_value`: `men`, `women` |
| `league_selected` | A league or season link in the league menu (`filter_scope: nav`) or on the home page's league cards (`home`) | `filter_value`: league code, `target_season`, `target_phase` |
| `table_columns_changed` | Table / Per game / Special teams on league pages | `filter_value`: `table`, `rates`, `special` |
| `games_changed` | Results / Upcoming on league pages | `results`, `upcoming` |
| `power_ranking_columns_changed`, `head_to_head_values_changed` | Segment buttons in the insights views (named after the group's `aria-label`) | the `data-view` value |
| `games_tab_changed`, `game_view_changed`, `playoff_round_changed` | Tabs on team, league and game pages | tab key, round number |
| `collection_filter_changed` | Facet chips (brand, category) on Connect collection pages | slug of the facet, `all` |
| `head_to_head_team_changed` | Team selects in the head-to-head view | no value (it would be a team name) |
| `compare_player_changed` | Choosing a player in the player comparison (`/compare-players.html`), also another player for a side that is already filled (so it is sent with `capture`, not `filterChanged`, which skips a repeated value) | `filter_value`: `a` or `b` (the side), `filter_scope: compare_players`; never the player |
| `compare_players_search_used`, `compare_players_search_result_clicked` | The two player search boxes of the player comparison | `search_scope: compare_players_search`; the click carries `result_type: player` and the suggestion's position |
| `site_search_opened`, `site_search_used`, `site_search_result_clicked` | Header search dialog for teams and players | see below |
| `player_search_used` | Player tables (`search_scope`: `category_players` or `player_stats_page`) | |
| `collection_search_used` | Search box on Connect collection pages | |

Clicking the option that is already selected does not count. A control without a labelled button group falls back to `view_changed`.

`*_search_used` fires when typing paused for 800 ms with at least 2 characters and the query differs from the last reported one. Properties: `search_scope`, `query_length`, `token_count`, `results_count`, `has_results`; never the text. `site_search_result_clicked` carries `result_type` (`team`, `player`) and `result_position` (1 = first).

Plus the automatic `$pageview` (`capture_pageview: true`, unchanged).

**Funnel for "Join for free":** `join_for_free_clicked` → page view of `/subscribe/` → `newsletter_signup_completed`. Cookieless mode has no cross-page session, so link the steps by funnel, not by a stored id.


## What changed from the previous events

| Before | Now |
|---|---|
| `global_search_opened` (`page_path`, `page_title`) | `site_search_opened` |
| `global_search_used` (**raw `query`**, `query_length`, `result_count`, `search_scope`) | `site_search_used` without the text; debounced 450 ms → 800 ms, minimum 2 characters, `results_count` |
| `global_search_result_clicked` (**raw `query`**, `result_name`, `result_type`, `result_url`) | `site_search_result_clicked` with type and position only |
| `player_search_used` (`query_length`, `token_count`, `results_count`, `total_rows`, `page_path`, `search_context`) | `player_search_used` (same name) with `search_scope`; `total_rows` is dropped |
| `nav_division_switched` (`division`, `path`) | `division_changed`; the division switch on the home and leaders pages is now counted too |
| `calendar_subscribe_clicked` (`kind`, `path`) | `calendar_apple_outlook_clicked`, `calendar_google_clicked`, `calendar_ics_download_clicked` |
| `support_cta_clicked` (`placement`, `path`), `support_cta_viewed` | `support_floorball_stats_clicked` / `_viewed` (banner), `support_clicked` (footer) |
| `share_card_opened` / `_downloaded` / `_shared` / `_failed` | `share_card_clicked` / `share_card_completed` (`share_method: download`) / `share_card_completed` (`share_method: share_sheet`) / `share_card_failed` |
| Connect `cta_clicked` (`cta`, `href`) | one event per button, e.g. `explore_league_stats_clicked` (property `cta`, `destination` instead of `href`); Stats' "Join for free" and footer links were not tracked before |
| Connect `newsletter_signup` (`form`) | `newsletter_signup_completed` (`cta_placement` = form); failures are new (`newsletter_signup_failed`) |
| Path property `path` / `page_path` mixed | always `page_path` |

Existing insights or dashboards that use the old names need to be pointed at the new ones. Old and new events do not overlap in time after this ships.

## Adding an event

1. Prefer markup over code: `data-cta="<snake_case label>"` on a link or button (`<label>_clicked`, with optional `data-cta-placement` and `data-cta-detail`), `data-track-filter="<control name>"` plus `data-track-value="<value>"` on a button (`<control name>_changed`), optionally grouped with `data-track-group="<scope>"`, `data-track-view="<button name>"` for `<button name>_viewed`.
2. In scripts, use `fbTrack.ctaCompleted(buttonName, props)`, `fbTrack.ctaFailed(buttonName, reason, props)`, `fbTrack.filterChanged(controlName, value)` or `fbTrack.searchTracker('<search box>_search')` (call `.update(text, resultCount)` on every filter run; it debounces and drops the text). Guard with `window.fbTrack ||` so the page still works if the script is missing.
3. Add the event or id to this file and a case to `tests/js/tracking.test.js`.

## Checking events

- Tests: `.venv/bin/python -m pytest tests/test_tracking_js.py` (runs `node --test tests/js/tracking.test.js`).
- In the browser on a local build, read the console (`[Analytics][localhost]` lines) or `fbTrack.localLog()`. On a deployed page, filter the network tab for `e.floorballconnect.com` and look at the `/e/` or `/batch/` payload (events are batched, `*_completed` events are sent immediately).
