const test = require('node:test');
const assert = require('node:assert/strict');
const rank = require('../../themes/my-theme/static/js/search-rank.js');

const rows = rank.prepare([
  { type: 'player', name: 'Eppu Suhanto', subtitle: 'Oilers · Finland · 2026/27', url: '/p1.html', weight: 26010 },
  { type: 'player', name: 'Eppu Suhanto Jr', subtitle: 'Classic · Finland · 2024/25', url: '/p2.html', weight: 24005 },
  { type: 'player', name: 'Mikko Suhanto', subtitle: 'Oilers · Finland · 2026/27', url: '/p3.html', weight: 26030 },
  { type: 'player', name: 'Łukasz Nowak', subtitle: 'Sparta · Czech Republic · 2026/27', url: '/p4.html', weight: 26001 },
  { type: 'team', name: 'Oilers', subtitle: 'Finland · F-Liiga · 2026/27', url: '/t1.html', weight: 263 },
  { type: 'team', name: 'Storvreta IBK', subtitle: 'Sweden · SSL · 2026/27', url: '/t2.html', weight: 263 },
  { type: 'league', name: 'Sweden · SSL', subtitle: '2026/27 · Regular season', url: '/l1.html', weight: 263 },
  { type: 'league', name: 'Finland · F-Liiga', subtitle: '2026/27 · Playoffs', url: '/l2.html', weight: 262 },
]);

const urls = (list) => list.map((row) => row.url);

test('the player scope only returns players', () => {
  const found = rank.search(rows, 'suhanto', 'players');
  assert.deepEqual(urls(found), ['/p3.html', '/p1.html', '/p2.html']);
  assert.ok(found.every((row) => row.type === 'player'));
});

test('an exact name beats a longer name, weight breaks ties', () => {
  assert.deepEqual(urls(rank.search(rows, 'Eppu Suhanto', 'players')), ['/p1.html', '/p2.html']);
});

test('words match in any order, accents and case do not matter', () => {
  assert.deepEqual(urls(rank.search(rows, 'suhanto EPPU', 'players')), ['/p1.html', '/p2.html']);
  assert.deepEqual(urls(rank.search(rows, 'lukasz', 'players')), ['/p4.html']);
});

test('a hit in the name ranks above a hit only through the team', () => {
  // "oilers" is the name of the team and only the subtitle of two players.
  const found = rank.search(rows, 'oilers', 'all');
  assert.equal(found[0].url, '/t1.html');
  assert.deepEqual(urls(found).slice(1).sort(), ['/p1.html', '/p3.html']);
});

test('leagues and teams are found in their own scopes', () => {
  assert.deepEqual(urls(rank.search(rows, 'ssl', 'leagues')), ['/l1.html']);
  assert.deepEqual(urls(rank.search(rows, 'storvreta', 'teams')), ['/t2.html']);
  assert.deepEqual(urls(rank.search(rows, 'playoffs', 'leagues')), ['/l2.html']);
});

test('nothing typed shows a few of each kind, one kind in a scope', () => {
  assert.deepEqual(urls(rank.featured(rows, 'all')).slice(0, 2), ['/l1.html', '/l2.html']);
  assert.ok(rank.featured(rows, 'players').every((row) => row.type === 'player'));
  assert.deepEqual(rank.search(rows, '   ', 'all'), []);
});

test('a query without a match returns nothing', () => {
  assert.deepEqual(rank.search(rows, 'zzzz', 'all'), []);
});
