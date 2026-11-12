const test = require('node:test');
const assert = require('node:assert/strict');
const links = require('../../themes/my-theme/static/js/share-links.js');

test('game text has the score, the decision and the league', () => {
  const text = links.shareText({ kind: 'game', home: 'Storvreta IBK', away: 'Falun', homeGoals: 5, awayGoals: 4, status: 'Final · OT', league: 'SSL', season: '2026/27' });
  assert.equal(text, 'Storvreta IBK 5:4 Falun (OT) · SSL 2026/27');
});

test('a game without a result reads as a fixture', () => {
  const text = links.shareText({ kind: 'game', home: 'A', away: 'B', homeGoals: '', awayGoals: '', league: 'SSL' });
  assert.equal(text, 'A vs B · SSL');
});

test('a goalless 0:0 is still a result', () => {
  assert.equal(links.shareText({ kind: 'game', home: 'A', away: 'B', homeGoals: 0, awayGoals: 0 }), 'A 0:0 B');
});

test('team, player, table and leaderboard texts', () => {
  assert.equal(links.shareText({ kind: 'team', name: 'Storvreta', rank: '1', points: 21, games: 8, league: 'SSL', season: '2026/27' }),
    'Storvreta · Rank 1, 21 pts, 8 games · SSL 2026/27');
  assert.equal(links.shareText({ kind: 'player', name: 'Eppu Suhanto', team: 'Classic', games: 10, goals: 6, assists: 7, points: 13, league: 'F-liiga', season: '2026/27' }),
    'Eppu Suhanto (Classic) · 6G 7A 13P in 10 games · F-liiga 2026/27');
  assert.equal(links.shareText({ kind: 'table', league: 'SSL', season: '2026/27', round: 8 }), 'SSL table · 2026/27 · after 8 games');
  assert.equal(links.shareText({ kind: 'leaderboard', title: 'Top scorers', division: 'Men', season: '2026/27' }), 'Top scorers · Men · 2026/27');
});

test('tagged links carry source, medium and campaign and drop the hash', () => {
  const url = new URL(links.taggedUrl('https://stats.floorballconnect.com/a.html?x=1&utm_medium=old#top', 'whatsapp', 'game'));
  assert.equal(url.searchParams.get('utm_source'), 'share');
  assert.equal(url.searchParams.get('utm_medium'), 'whatsapp');
  assert.equal(url.searchParams.get('utm_campaign'), 'game');
  assert.equal(url.searchParams.get('x'), '1');
  assert.equal(url.hash, '');
});

test('every platform link contains the tagged page link and the text', () => {
  const data = { kind: 'team', name: 'Storvreta', rank: '1', points: 21, games: 8 };
  const all = links.platformLinks(data, 'https://stats.floorballconnect.com/t.html');
  assert.deepEqual(all.map((link) => link.method), ['whatsapp', 'telegram', 'x', 'facebook', 'linkedin', 'reddit', 'bluesky', 'email']);
  all.forEach((link) => {
    assert.ok(decodeURIComponent(link.href).includes('utm_medium=' + link.method), link.method);
    assert.ok(decodeURIComponent(link.href).includes('stats.floorballconnect.com/t.html'), link.method);
  });
  const facebook = all.find((link) => link.method === 'facebook');
  assert.ok(!decodeURIComponent(facebook.href).includes('Storvreta'), 'Facebook only takes a URL');
  assert.ok(decodeURIComponent(all.find((link) => link.method === 'x').href).includes('Storvreta'));
});

test('canonical link wins over the address bar', () => {
  const doc = { querySelector: () => ({ getAttribute: () => 'https://stats.floorballconnect.com/c.html' }) };
  assert.equal(links.canonicalUrl(doc, { origin: 'http://localhost:8000', pathname: '/c.html' }), 'https://stats.floorballconnect.com/c.html');
  assert.equal(links.canonicalUrl({ querySelector: () => null }, { origin: 'http://localhost:8000', pathname: '/c.html' }), 'http://localhost:8000/c.html');
});
