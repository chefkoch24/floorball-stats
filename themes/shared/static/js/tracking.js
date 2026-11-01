/* Shared PostHog event helper for Floorball Stats and Floorball Connect.
   Templates call fbTrack.* instead of posthog.capture so every event has the same
   name style (snake_case) and the same base properties, and nothing free-form leaves
   the browser. Event list and property schema: docs/analytics-events.md.

   - Base properties on every event: site (stats|connect), page_path, page_type and,
     where the URL tells, league, season, phase, division.
   - Strings are only sent when they look like an identifier (no spaces, no "@"), so
     search text, names, e-mail addresses and messages are dropped even by mistake.
   - Search events carry the query length and the result count, never the text, and are
     debounced so typing "stor", "stor v", "stor vi" counts as one search.
   - Cookie and consent behaviour stays with the PostHog init in base.html (cookieless,
     nothing stored in the browser); this file stores nothing either. */
(function (root, factory) {
  var api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root && root.document) {
    root.fbTrack = api;
    api.init(root);
  }
})(typeof window !== 'undefined' ? window : null, function (root) {
  'use strict';

  var SAFE_STRING = /^[A-Za-z0-9_.\/:#=-]{1,80}$/;
  var BLOCKED_KEYS = /^(query|q|text|name|email|message|title|player|team|href|url)$/i;
  var SEARCH_DELAY_MS = 800;
  var SEARCH_MIN_LENGTH = 2;
  // Slugs look like "<league>-<yy-yy>-<phase>": se-26-27-regular-season, 25-26-playoffs, ccw-26-27-playoffs.
  var LEAGUE_CODES = ['se', 'fi', 'cz', 'ch', 'sk', 'lv', 'sew', 'fiw', 'czw', 'chw', 'skw', 'lvw', 'dew', 'cc', 'ccw'];
  var SLUG = /(?:^|[\/-])(?:([a-z]{2,3})-)?(\d{2}-\d{2})-(regular-season|playoffs)(?![a-z])/;

  function slugify(value) {
    return String(value == null ? '' : value)
      .toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '')
      .slice(0, 40);
  }

  // Keeps numbers, booleans and identifier-like strings; drops everything else.
  function sanitize(props) {
    var clean = {};
    Object.keys(props || {}).forEach(function (key) {
      var value = props[key];
      if (BLOCKED_KEYS.test(key) || value == null) return;
      if (typeof value === 'number') {
        if (isFinite(value)) clean[key] = value;
      } else if (typeof value === 'boolean') {
        clean[key] = value;
      } else if (typeof value === 'string' && SAFE_STRING.test(value)) {
        clean[key] = value;
      }
    });
    return clean;
  }

  function isWomenLeague(code) {
    return code.length === 3 && code.charAt(2) === 'w';
  }

  // League, season and phase from any URL or slug that contains a category slug.
  // The league code is the slug prefix ("de" for Germany's men, which has none).
  function parseCategory(text) {
    var match = SLUG.exec(String(text || '').toLowerCase());
    if (!match) return {};
    var code = LEAGUE_CODES.indexOf(match[1]) >= 0 ? match[1] : 'de';
    return {
      league: code,
      season: match[2],
      phase: match[3],
      division: isWomenLeague(code) ? 'women' : 'men'
    };
  }

  // Coarse page kind from the path, used to group events; not meant to be exact.
  function pageType(site, pathname) {
    var path = String(pathname || '/').replace(/\/index\.html$/, '/');
    if (path === '/' || path === '') return 'home';
    if (site === 'connect') {
      var segments = path.split('/').filter(Boolean);
      if (segments.length >= 2) return 'item';
      return segments[0] === 'subscribe' ? 'subscribe' : 'collection';
    }
    if (/^\/category\/.+-players\.html$/.test(path)) return 'league_players';
    if (/^\/category\//.test(path)) return 'league';
    if (/^\/leaders\.html$/.test(path)) return 'leaders';
    if (/^\/stats-explained\.html$/.test(path)) return 'stats_explained';
    if (/^\/player-[0-9a-f]+\.html$/.test(path)) return 'player';
    if (/^\/\d+-.+-vs-.+\.html$/.test(path)) return 'game';
    if (/^\/\d+-.+\.html$/.test(path) && SLUG.test(path)) return 'team';
    return 'page';
  }

  function destination(href, locationHost) {
    try {
      var url = new URL(href, 'https://' + (locationHost || 'example.invalid'));
      if (url.protocol === 'mailto:') return 'mailto';
      if (url.protocol === 'webcal:') return 'webcal';
      return url.host + url.pathname.replace(/\/$/, '/');
    } catch (error) {
      return '';
    }
  }

  // Waits for typing to pause, skips repeats of the same query and stays silent below
  // two characters. `update(rawQuery, resultCount)` after every filter run;
  // `flush()` when the user leaves the field or picks a result.
  function createSearchTracker(report, options) {
    var delay = options && options.delay != null ? options.delay : SEARCH_DELAY_MS;
    var timer = null;
    var pending = null;
    var lastReported = '';
    var setTimer = (options && options.setTimeout) || function (fn, ms) { return setTimeout(fn, ms); };
    var clearTimer = (options && options.clearTimeout) || function (id) { clearTimeout(id); };

    function normalize(raw) {
      return String(raw || '').trim().toLowerCase().replace(/\s+/g, ' ');
    }
    function flush() {
      if (timer != null) { clearTimer(timer); timer = null; }
      if (!pending) return;
      var current = pending;
      pending = null;
      if (current.query.length < SEARCH_MIN_LENGTH || current.query === lastReported) return;
      lastReported = current.query;
      report({
        query_length: current.query.length,
        token_count: current.query.split(' ').length,
        results_count: current.results,
        has_results: current.results > 0
      });
    }
    function update(raw, results) {
      var query = normalize(raw);
      if (timer != null) { clearTimer(timer); timer = null; }
      if (!query) { pending = null; lastReported = ''; return; }
      pending = { query: query, results: Number(results) || 0 };
      timer = setTimer(flush, delay);
    }
    return { update: update, flush: flush };
  }

  var state = { site: 'stats', win: null, filterValues: {}, trackers: [], localLog: [] };

  function baseProps() {
    var win = state.win;
    var path = win && win.location ? win.location.pathname : '/';
    var props = { site: state.site, page_path: path, page_type: pageType(state.site, path) };
    var category = parseCategory(path);
    Object.keys(category).forEach(function (key) { props[key] = category[key]; });
    return props;
  }

  function isLocalHost(hostname) {
    return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1';
  }

  function capture(eventName, props, options) {
    var win = state.win;
    if (!win) return;
    var payload = baseProps();
    var extra = sanitize(props);
    Object.keys(extra).forEach(function (key) { payload[key] = extra[key]; });
    // PostHog is not initialised on localhost; print the event instead so it can be checked.
    if (win.location && isLocalHost(win.location.hostname)) {
      if (win.console && win.console.info) win.console.info('[Analytics][localhost]', eventName, payload);
      state.localLog.push({ event: eventName, properties: payload });
      return;
    }
    if (!win.posthog || typeof win.posthog.capture !== 'function') return;
    try {
      win.posthog.capture(eventName, payload, options);
    } catch (error) { /* analytics must never break the page */ }
  }

  // Convenience wrappers so call sites read like the event list.
  function ctaClicked(ctaId, extra) { capture('cta_clicked', Object.assign({ cta_id: ctaId }, extra)); }
  // Completed = the sign-up or share really went through. Sent immediately because the
  // page often navigates right after.
  function ctaCompleted(ctaId, extra) { capture('cta_completed', Object.assign({ cta_id: ctaId }, extra), { send_instantly: true }); }
  function ctaFailed(ctaId, reason, extra) { capture('cta_failed', Object.assign({ cta_id: ctaId, reason: reason }, extra)); }

  function filterChanged(name, value, extra) {
    var key = name + ':' + (extra && extra.filter_scope || '');
    var next = value == null ? '' : String(value);
    if (state.filterValues[key] === next) return;
    state.filterValues[key] = next;
    capture('filter_changed', Object.assign({ filter_name: name, filter_value: value }, extra));
  }

  function searchTracker(scope, extra) {
    var tracker = createSearchTracker(function (stats) {
      capture('search_used', Object.assign({ search_scope: scope }, stats, extra));
    });
    state.trackers.push(tracker);
    return tracker;
  }

  function searchOpened(scope) { capture('search_opened', { search_scope: scope }); }
  function searchResultClicked(scope, resultType, position) {
    capture('search_result_clicked', { search_scope: scope, result_type: resultType, result_position: position });
  }

  // ---- Declarative bindings: existing markup, no per-template listeners ----

  var FILTER_RULES = [
    // [selector, filter name, how to read the value, "already selected" test]
    ['[data-division-option]', 'division', function (el) { return el.getAttribute('data-division-option'); }],
    ['[data-live-division]', 'division', function (el) { return el.getAttribute('data-live-division'); }],
    ['.fs-segment[data-view]', 'view', function (el) { return el.getAttribute('data-view'); }],
    ['[data-games-tab]', 'games_tab', function (el) { return el.getAttribute('data-games-tab'); }],
    ['[data-game-view-tab]', 'game_view', function (el) { return el.getAttribute('data-game-view-tab'); }],
    ['.playoff-tab[data-round]', 'playoff_round', function (el) { return el.getAttribute('data-round'); }],
    ['[data-filter-facet]', 'facet', function (el) { return slugify(el.getAttribute('data-filter-facet')) || 'all'; }],
    ['[data-track-filter]', null, function (el) { return el.getAttribute('data-track-value'); }]
  ];

  function alreadySelected(el) {
    return el.getAttribute('aria-pressed') === 'true' || el.classList.contains('is-active');
  }

  // Scope of a control: an explicit data-track-group, else the label of its button group
  // ("Table columns" -> table_columns), which are static strings in the templates.
  function groupOf(el) {
    var group = el.closest && el.closest('[data-track-group], [role="group"][aria-label]');
    if (!group) return '';
    return slugify(group.getAttribute('data-track-group') || group.getAttribute('aria-label'));
  }

  function onClick(event) {
    var target = event.target && event.target.closest ? event.target : null;
    if (!target) return;

    // Filters and view switches. Capture phase: aria-pressed is still the old state here,
    // so clicking the option that is already selected counts as nothing.
    for (var i = 0; i < FILTER_RULES.length; i++) {
      var rule = FILTER_RULES[i];
      var el = target.closest(rule[0]);
      if (!el || el.tagName === 'SELECT' || alreadySelected(el)) continue;
      var name = rule[1] || slugify(el.getAttribute('data-track-filter'));
      var scope = el.closest('.main-nav, .nav-menu-top') ? 'nav' : groupOf(el);
      filterChanged(name, rule[2](el), scope ? { filter_scope: scope } : undefined);
      break;
    }

    // League, season and phase picked from a link: the league menu and the league cards on the
    // home page (including the "Earlier" season links). filter_value is the league code of the
    // target, the target's season and phase travel as target_season / target_phase.
    var leagueLink = target.closest('.nav-league__link, .nav-league__name, .fs-league-card a, [data-track-league-link]');
    if (leagueLink && leagueLink.tagName === 'A') {
      var picked = parseCategory(leagueLink.getAttribute('href'));
      if (picked.league) {
        capture('filter_changed', {
          filter_name: 'league', filter_value: picked.league,
          filter_scope: leagueLink.closest('.fs-league-card') ? 'home' : 'nav',
          target_season: picked.season, target_phase: picked.phase
        });
      }
    }

    // CTAs. data-cta is the id; data-support-cta and data-calendar-cta are older
    // attributes that map onto the same event.
    var cta = target.closest('[data-cta], [data-support-cta], [data-calendar-cta], [data-share]');
    if (cta) {
      var id = cta.getAttribute('data-cta');
      var kind = cta.tagName === 'A' ? 'link' : 'button';
      if (!id && cta.hasAttribute('data-support-cta')) { id = 'support-' + cta.getAttribute('data-support-cta'); kind = 'support'; }
      if (!id && cta.hasAttribute('data-calendar-cta')) { id = 'calendar-' + cta.getAttribute('data-calendar-cta'); kind = 'calendar'; }
      if (!id && cta.hasAttribute('data-share')) { id = 'share-' + (slugify(cta.getAttribute('data-share')) || 'page'); kind = 'share'; }
      if (id) {
        var props = { cta_kind: kind };
        var href = cta.getAttribute('href');
        if (href) props.destination = destination(href, state.win.location.host);
        ctaClicked(id, props);
      }
    }
  }

  function onChange(event) {
    var el = event.target;
    if (!el || !el.matches) return;
    if (el.matches('[data-h2h-select]')) {
      // Team choice: the choice itself is a name, so only the fact that it changed is sent.
      capture('filter_changed', { filter_name: 'h2h_team', filter_scope: groupOf(el) || undefined });
    } else if (el.matches('select[data-track-filter]')) {
      filterChanged(slugify(el.getAttribute('data-track-filter')), el.value, groupOf(el) ? { filter_scope: groupOf(el) } : undefined);
    }
  }

  function observeViews(win) {
    if (!('IntersectionObserver' in win)) return;
    var targets = win.document.querySelectorAll('[data-support-card], [data-track-view]');
    if (!targets.length) return;
    var observer = new win.IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        observer.unobserve(el);
        var id = el.getAttribute('data-track-view') || (el.hasAttribute('data-support-card') ? 'support-banner' : '');
        if (id) capture('cta_viewed', { cta_id: id });
      });
    }, { threshold: 0.5 });
    targets.forEach(function (el) { observer.observe(el); });
  }

  function flushSearches() {
    state.trackers.forEach(function (tracker) { tracker.flush(); });
  }

  function init(win) {
    state.win = win;
    var script = win.document.currentScript;
    var declared = script && script.getAttribute('data-site');
    state.site = declared === 'connect' ? 'connect' : 'stats';
    // A search that is still waiting for typing to pause is reported when the page goes away.
    win.addEventListener('pagehide', flushSearches);
    win.document.addEventListener('visibilitychange', function () {
      if (win.document.visibilityState === 'hidden') flushSearches();
    });
    win.document.addEventListener('click', onClick, true);
    win.document.addEventListener('change', onChange, true);
    // The PostHog snippet may come after this script in the page, so wait until the document is parsed.
    function afterParse() {
      // Super property: $pageview and every other event carry the site too.
      if (win.posthog && typeof win.posthog.register === 'function') {
        try { win.posthog.register({ site: state.site }); } catch (error) { /* ignore */ }
      }
      observeViews(win);
    }
    if (win.document.readyState === 'loading') {
      win.document.addEventListener('DOMContentLoaded', afterParse);
    } else {
      afterParse();
    }
  }

  return {
    init: init,
    capture: capture,
    ctaClicked: ctaClicked,
    ctaCompleted: ctaCompleted,
    ctaFailed: ctaFailed,
    filterChanged: filterChanged,
    searchTracker: searchTracker,
    searchOpened: searchOpened,
    searchResultClicked: searchResultClicked,
    // events printed instead of sent while on localhost
    localLog: function () { return state.localLog; },
    // exported for tests
    sanitize: sanitize,
    parseCategory: parseCategory,
    pageType: pageType,
    destination: destination,
    slugify: slugify,
    createSearchTracker: createSearchTracker
  };
});
