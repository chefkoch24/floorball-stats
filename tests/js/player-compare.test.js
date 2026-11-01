// Run with: node --test tests/js   (also called from tests/test_player_compare.py)
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const compare = require(path.join(__dirname, '..', '..', 'themes', 'my-theme', 'static', 'js', 'player-compare.js'));

const FIELDS = ['uid', 'name', 'team', 'league', 'season', 'games'];
const ROWS = [
  ['player-1', 'Erik Peter Gavlák', 'Slovan', 'Slovakia', 'sk-26-27', 80],
  ['player-2', 'Gavlák Erik Peter', 'Slovan', 'Slovakia', 'sk-25-26', 12],
  ['player-3', 'Janne Autio', 'SPV', 'Finland', 'fi-26-27', 17],
  ['player-4', 'Łukasz Nowak', 'Karlstad IBF', 'Sweden', 'se-26-27', 40],
  ['player-5', 'Anna Nowak', 'Malmö FBC', 'Sweden Women', 'sew-26-27', 30],
  ['player-6', 'Erika Berg', 'Karlstad IBF', 'Sweden', 'se-26-27', 5],
];
const index = compare.prepareIndex({ fields: FIELDS, players: ROWS });
const names = (hits) => hits.map((player) => player.uid);

function player(overrides) {
  return Object.assign({
    uid: 'p', name: 'P', url: 'p.html', team: 'T', team_url: '', league: 'Sweden', season: 'se-26-27', season_label: '2026/27', seasons: 3,
    current: { games: 10, goals: 5, assists: 5, points: 10, pim: 4 },
    career: { games: 30, goals: 12, assists: 18, points: 30, pim: 10 },
    clutch: { current: { gwg: 1, clutch_points: 2, game_changing: 3 }, all: { gwg: 2, clutch_points: 4, game_changing: 6 } },
    share: { share: 20, points: 10, team_goals: 50 },
  }, overrides);
}

function row(result, sectionId, key) {
  const section = result.sections.find((item) => item.id === sectionId);
  return section && section.rows.find((item) => item.key === key);
}

test('the season label matches the one the build writes', () => {
  assert.equal(compare.seasonLabel('fi-26-27'), '2026/27');
  assert.equal(compare.seasonLabel('26-27'), '2026/27');
  assert.equal(compare.seasonLabel('wfc-2024'), '2024');
  assert.equal(compare.seasonLabel(''), '');
});

test('normalize drops accents, case and punctuation', () => {
  assert.equal(compare.normalize('Gavlák, Erik-Peter'), 'gavlak erik peter');
  assert.equal(compare.normalize('Łukasz Müller'), 'lukasz muller');
  assert.equal(compare.normalize(null), '');
});

test('search finds a name in either word order', () => {
  // The name that starts with the words as typed comes first, the same words reordered follow.
  assert.deepEqual(names(compare.search(index, 'Gavlak Erik')), ['player-2', 'player-1']);
  assert.deepEqual(names(compare.search(index, 'Erik Gavlak')), ['player-1', 'player-2']);
  assert.deepEqual(names(compare.search(index, 'erik gavlák peter')), ['player-1', 'player-2']);
});

test('search ranks exact names first and keeps regulars ahead on ties', () => {
  assert.deepEqual(names(compare.search(index, 'erik')), ['player-1', 'player-6', 'player-2']);
  assert.equal(compare.search(index, 'anna nowak')[0].uid, 'player-5');
});

test('search matches prefixes, accents and the team as a second word', () => {
  assert.deepEqual(names(compare.search(index, 'lukas')), ['player-4']);
  assert.deepEqual(names(compare.search(index, 'nowak karl')), ['player-4']);
  assert.deepEqual(names(compare.search(index, 'karlstad')), ['player-4', 'player-6']);
});

test('search needs two characters, skips the excluded player and limits the list', () => {
  assert.deepEqual(compare.search(index, 'e'), []);
  assert.deepEqual(compare.search(index, '  '), []);
  assert.deepEqual(names(compare.search(index, 'nowak', { exclude: 'player-4' })), ['player-5']);
  assert.equal(compare.search(index, 'er', { limit: 2 }).length, 2);
  assert.deepEqual(compare.search(index, 'zzzz'), []);
});

test('selection is read from and written to the URL', () => {
  assert.deepEqual(compare.parseSelection('?a=player-03f5&b=player-9'), { a: 'player-03f5', b: 'player-9' });
  assert.deepEqual(compare.parseSelection('?a=player-03f5'), { a: 'player-03f5', b: '' });
  assert.deepEqual(compare.parseSelection(''), { a: '', b: '' });
  assert.equal(compare.selectionQuery('player-1', 'player-2'), '?a=player-1&b=player-2');
  assert.equal(compare.selectionQuery('', 'player-2'), '?b=player-2');
  assert.equal(compare.selectionQuery('', ''), '');
});

test('selection drops values that are not player ids', () => {
  assert.deepEqual(compare.parseSelection('?a=../../etc&b=%3Cscript%3E'), { a: '', b: '' });
  assert.deepEqual(compare.parseSelection('?a=' + 'x'.repeat(65)), { a: '', b: '' });
});

test('the better value of a row is the higher one, the lower one for penalty minutes', () => {
  const result = compare.compare(
    player({ current: { games: 10, goals: 8, assists: 2, points: 10, pim: 12 } }),
    player({ current: { games: 12, goals: 4, assists: 8, points: 12, pim: 4 } }),
  );
  assert.equal(row(result, 'latest', 'goals').winner, 'a');
  assert.equal(row(result, 'latest', 'assists').winner, 'b');
  assert.equal(row(result, 'latest', 'points').winner, 'b');
  assert.equal(row(result, 'latest', 'pim').winner, 'b');
  assert.equal(row(result, 'latest', 'pim').a, '12');
});

test('per-game values come from the totals and the games', () => {
  const result = compare.compare(
    player({ current: { games: 8, goals: 4, assists: 4, points: 8, pim: 2 } }),
    player({ current: { games: 10, goals: 5, assists: 7, points: 12, pim: 10 } }),
  );
  const ppg = row(result, 'latest', 'points_per_game');
  assert.deepEqual([ppg.a, ppg.b, ppg.winner], ['1.00', '1.20', 'b']);
  const pim = row(result, 'latest', 'pim_per_game');
  assert.deepEqual([pim.a, pim.b, pim.winner], ['0.25', '1.00', 'a']);
});

test('equal values and rows without a rating highlight nothing', () => {
  const result = compare.compare(player(), player());
  assert.equal(row(result, 'latest', 'points').winner, '');
  const unequal = compare.compare(player({ seasons: 2 }), player({ seasons: 9 }));
  assert.equal(row(unequal, 'career', 'seasons').winner, '');
});

test('a player without games has no per-game value and no winner', () => {
  const idle = player({ current: { games: 0, goals: 0, assists: 0, points: 0, pim: 0 } });
  const result = compare.compare(idle, player());
  const ppg = row(result, 'latest', 'points_per_game');
  assert.deepEqual([ppg.a, ppg.winner], ['–', '']);
});

test('clutch and share rows are left out when neither player has the data', () => {
  const none = { clutch: { current: null, all: null }, share: null };
  const result = compare.compare(player(none), player(none));
  assert.equal(row(result, 'latest', 'gwg'), undefined);
  assert.equal(row(result, 'latest', 'share'), undefined);
  assert.equal(row(result, 'career', 'clutch'), undefined);
  assert.ok(row(result, 'latest', 'points'));
});

test('clutch and share rows show a dash for the player without data', () => {
  const result = compare.compare(player(), player({ clutch: { current: null, all: null }, share: null }));
  const share = row(result, 'latest', 'share');
  assert.deepEqual([share.a, share.b, share.winner, share.detailA, share.detailB], ['20%', '–', '', '10 of 50 goals', '']);
  assert.equal(row(result, 'latest', 'gwg').b, '–');
});

test('players from different leagues and seasons get a note that names the per-game rows', () => {
  const result = compare.compare(
    player({ name: 'Ann', league: 'Sweden' }),
    player({ name: 'Bo', league: 'Finland', season: 'fi-24-25', season_label: '2024/25' }),
  );
  assert.equal(result.notes.length, 2);
  assert.match(result.notes[0], /Ann plays in Sweden and Bo in Finland/);
  assert.match(result.notes[0], /per-game/);
  assert.match(result.notes[1], /2026\/27 for Ann and 2024\/25 for Bo/);
});

test('players of one league and season get no cross-league note', () => {
  assert.deepEqual(compare.compare(player(), player()).notes, []);
});

test('a player with only a few games gets a small-sample note', () => {
  const few = player({ name: 'Cy', current: { games: 2, goals: 2, assists: 0, points: 2, pim: 0 } });
  const [note] = compare.compare(few, player()).notes;
  assert.match(note, /Cy/);
});
