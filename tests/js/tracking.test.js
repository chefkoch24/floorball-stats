// Run with: node --test tests/js   (also called from tests/test_tracking_js.py)
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const fbTrack = require(path.join(__dirname, '..', '..', 'themes', 'shared', 'static', 'js', 'tracking.js'));

function fakeWindow(pathname, site) {
  const calls = [];
  const listeners = {};
  const doc = {
    readyState: 'complete',
    currentScript: { getAttribute: () => site || null },
    addEventListener: (type, fn) => { listeners[type] = fn; },
    querySelectorAll: () => [],
  };
  const win = {
    document: doc,
    location: { pathname, host: 'stats.floorballconnect.com' },
    posthog: { capture: (...args) => calls.push(args), register: () => {} },
    addEventListener: () => {},
  };
  return { win, calls, listeners };
}

// A click target whose closest() answers only for the given selectors.
function target(matches, attrs, extra) {
  const el = {
    tagName: (extra && extra.tag) || 'BUTTON',
    classList: { contains: (name) => Boolean(extra && extra.classes && extra.classes.includes(name)) },
    getAttribute: (name) => (name in attrs ? attrs[name] : null),
    hasAttribute: (name) => name in attrs,
    closest: (selector) => (selector in matches ? matches[selector] : null),
  };
  Object.keys(matches).forEach((selector) => { if (matches[selector] === true) matches[selector] = el; });
  return el;
}

test('sanitize keeps identifiers and numbers, drops free text, e-mails and name-like keys', () => {
  const clean = fbTrack.sanitize({
    filter_value: 'rates', results_count: 12, has_results: true,
    query: 'storvreta', name: 'Gabriel Kohonen', email: 'a@b.co',
    note: 'free text with spaces', mail: 'felix@example.com', empty: null, nan: NaN,
  });
  assert.deepEqual(clean, { filter_value: 'rates', results_count: 12, has_results: true });
});

test('parseCategory reads league, season and phase from category, team and game URLs', () => {
  assert.deepEqual(fbTrack.parseCategory('/category/se-26-27-regular-season.html'),
    { league: 'se', season: '26-27', phase: 'regular-season', division: 'men' });
  assert.deepEqual(fbTrack.parseCategory('/1-fbc-trencin-sk-25-26-playoffs-sk-25-26-playoffs.html'),
    { league: 'sk', season: '25-26', phase: 'playoffs', division: 'men' });
  assert.deepEqual(fbTrack.parseCategory('/1097639-fb-riders-dbr-vs-red-ants-winterthur-chw-26-27-regular-season.html'),
    { league: 'chw', season: '26-27', phase: 'regular-season', division: 'women' });
  assert.deepEqual(fbTrack.parseCategory('/category/ccw-26-27-playoffs.html'),
    { league: 'ccw', season: '26-27', phase: 'playoffs', division: 'women' });
  // Germany's men have no prefix; a short team word must not be taken for a league.
  assert.equal(fbTrack.parseCategory('/category/26-27-regular-season.html').league, 'de');
  assert.equal(fbTrack.parseCategory('/uhc-ulm-25-26-playoffs.html').league, 'de');
  assert.deepEqual(fbTrack.parseCategory('/leaders.html'), {});
});

test('pageType groups paths for both sites', () => {
  assert.equal(fbTrack.pageType('stats', '/'), 'home');
  assert.equal(fbTrack.pageType('stats', '/index.html'), 'home');
  assert.equal(fbTrack.pageType('stats', '/category/se-26-27-regular-season.html'), 'league');
  assert.equal(fbTrack.pageType('stats', '/category/se-26-27-regular-season-players.html'), 'league_players');
  assert.equal(fbTrack.pageType('stats', '/leaders.html'), 'leaders');
  assert.equal(fbTrack.pageType('stats', '/player-03f56dc019238b3b.html'), 'player');
  assert.equal(fbTrack.pageType('stats', '/1073807-zug-united-vs-uhc-uster-ch-25-26-regular-season.html'), 'game');
  assert.equal(fbTrack.pageType('stats', '/1-fbc-trencin-sk-25-26-playoffs-sk-25-26-playoffs.html'), 'team');
  assert.equal(fbTrack.pageType('connect', '/'), 'home');
  assert.equal(fbTrack.pageType('connect', '/subscribe/'), 'subscribe');
  assert.equal(fbTrack.pageType('connect', '/floorball-sticks/'), 'collection');
  assert.equal(fbTrack.pageType('connect', '/floorball-sticks/zone-airlight/'), 'item');
});

test('destination keeps host and path, never query strings or mail addresses', () => {
  assert.equal(fbTrack.destination('https://example.com/a/b?x=1#y', 'x'), 'example.com/a/b');
  assert.equal(fbTrack.destination('mailto:hello@floorballconnect.com', 'x'), 'mailto');
  assert.equal(fbTrack.destination('/leaders.html', 'stats.floorballconnect.com'), 'stats.floorballconnect.com/leaders.html');
});

test('search tracker waits for typing to pause and reports one event without the text', () => {
  const reports = [];
  const timers = [];
  const tracker = fbTrack.createSearchTracker((stats) => reports.push(stats), {
    setTimeout: (fn) => { timers.push(fn); return timers.length; },
    clearTimeout: (id) => { timers[id - 1] = null; },
  });
  tracker.update('s', 20);
  tracker.update('st', 9);
  tracker.update('Stor', 3);
  tracker.update('Stor  v', 1);
  timers.forEach((fn) => fn && fn());
  assert.equal(reports.length, 1);
  assert.deepEqual(reports[0], { query_length: 6, token_count: 2, results_count: 1, has_results: true });
  assert.ok(!JSON.stringify(reports[0]).includes('stor'));

  // The same query again is not counted twice, a new one is, and clearing the field resets.
  tracker.update('stor v', 1); tracker.flush();
  assert.equal(reports.length, 1);
  tracker.update('', 20); tracker.update('stor v', 1); tracker.flush();
  assert.equal(reports.length, 2);
  // One character is not a search; zero results are reported as such.
  tracker.update('x', 0); tracker.flush();
  tracker.update('xyz', 0); tracker.flush();
  assert.equal(reports.length, 3);
  assert.deepEqual([reports[2].results_count, reports[2].has_results], [0, false]);
});

test('capture adds site and page context and removes anything free-form', () => {
  const { win, calls } = fakeWindow('/category/sew-26-27-playoffs.html');
  fbTrack.init(win);
  fbTrack.capture('search_used', { search_scope: 'site', results_count: 4, query: 'secret', note: 'a b' });
  assert.equal(calls.length, 1);
  const [name, props] = calls[0];
  assert.equal(name, 'search_used');
  assert.deepEqual(props, {
    site: 'stats', page_path: '/category/sew-26-27-playoffs.html', page_type: 'league',
    league: 'sew', season: '26-27', phase: 'playoffs', division: 'women',
    search_scope: 'site', results_count: 4,
  });
});

test('the connect script tag switches the site property', () => {
  const { win, calls } = fakeWindow('/subscribe/', 'connect');
  fbTrack.init(win);
  fbTrack.ctaCompleted('signup-subscribe', { cta_kind: 'newsletter' });
  const [name, props, options] = calls[0];
  assert.equal(name, 'cta_completed');
  assert.equal(props.site, 'connect');
  assert.equal(props.cta_id, 'signup-subscribe');
  assert.equal(props.page_type, 'subscribe');
  assert.deepEqual(options, { send_instantly: true });
});

test('clicking an already selected filter option sends nothing, a new one sends once', () => {
  const { win, calls, listeners } = fakeWindow('/leaders.html');
  fbTrack.init(win);
  const selected = target({ '[data-division-option]': true }, { 'data-division-option': 'men', 'aria-pressed': 'true' });
  listeners.click({ target: selected });
  assert.equal(calls.length, 0);
  const other = target({ '[data-division-option]': true }, { 'data-division-option': 'women', 'aria-pressed': 'false' });
  listeners.click({ target: other });
  listeners.click({ target: other });
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], 'filter_changed');
  assert.equal(calls[0][1].filter_name, 'division');
  assert.equal(calls[0][1].filter_value, 'women');
});

test('CTA clicks use data-cta and the older support and calendar attributes', () => {
  const { win, calls, listeners } = fakeWindow('/');
  fbTrack.init(win);
  const sel = '[data-cta], [data-support-cta], [data-calendar-cta], [data-share]';
  listeners.click({ target: target({ [sel]: true }, { 'data-cta': 'header', href: 'https://www.floorballconnect.com/subscribe/' }, { tag: 'A' }) });
  listeners.click({ target: target({ [sel]: true }, { 'data-support-cta': 'card', href: 'https://ko-fi.com/x?ref=1' }, { tag: 'A' }) });
  listeners.click({ target: target({ [sel]: true }, { 'data-calendar-cta': 'google', href: 'webcal://x/y.ics' }, { tag: 'A' }) });
  assert.deepEqual(calls.map((c) => [c[0], c[1].cta_id, c[1].destination]), [
    ['cta_clicked', 'header', 'www.floorballconnect.com/subscribe/'],
    ['cta_clicked', 'support-card', 'ko-fi.com/x'],
    ['cta_clicked', 'calendar-google', 'webcal'],
  ]);
});

test('league links report the target league, season and phase; selects report on change only', () => {
  const { win, calls, listeners } = fakeWindow('/');
  fbTrack.init(win);
  const card = {};
  const sel = '.nav-league__link, .nav-league__name, .fs-league-card a, [data-track-league-link]';
  listeners.click({ target: target({ [sel]: true, '.fs-league-card': card }, { href: '/category/czw-25-26-playoffs.html' }, { tag: 'A' }) });
  // closest('.fs-league-card') is looked up on the link itself, so the home-page scope needs the card match.
  assert.equal(calls.length, 1);
  assert.deepEqual([calls[0][1].filter_name, calls[0][1].filter_value, calls[0][1].target_season, calls[0][1].target_phase, calls[0][1].filter_scope],
    ['league', 'czw', '25-26', 'playoffs', 'home']);

  const select = target({ 'select[data-track-filter]': true, '[data-track-filter]': true }, { 'data-track-filter': 'season' }, { tag: 'SELECT' });
  listeners.click({ target: select });
  assert.equal(calls.length, 1);
  select.matches = (selector) => selector === 'select[data-track-filter]';
  select.value = '25-26';
  listeners.change({ target: select });
  assert.equal(calls.length, 2);
  assert.deepEqual([calls[1][1].filter_name, calls[1][1].filter_value], ['season', '25-26']);
});

test('on localhost events are logged instead of sent', () => {
  const { win, calls } = fakeWindow('/leaders.html');
  win.location.hostname = 'localhost';
  const logged = [];
  win.console = { info: (...args) => logged.push(args) };
  fbTrack.init(win);
  const before = fbTrack.localLog().length;
  fbTrack.capture('search_opened', { search_scope: 'site' });
  assert.equal(calls.length, 0);
  assert.equal(fbTrack.localLog().length, before + 1);
  assert.equal(logged[0][1], 'search_opened');
});
