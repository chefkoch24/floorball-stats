/* Global search: matching, scope and ranking, without any DOM access, so
   tests/js/search-rank.test.js can run it in node. The search modal in base.html renders the result.

   Index rows (src/build_search_index.py): { type: player | team | league, name, subtitle, url, weight }.
   Rows of one type arrive sorted by weight (newest season, then points), and the sort here is stable,
   so among equally good matches the more relevant row stays first. */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.fsSearchRank = api;
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';

  // The scope buttons of the modal -> the row type they show. "all" shows everything.
  var SCOPES = { all: null, players: 'player', teams: 'team', leagues: 'league' };
  // What the modal shows before anything is typed: a few of each kind, current leagues first.
  var FEATURED = { league: 6, team: 6, player: 8 };

  function normalize(value) {
    return String(value == null ? '' : value)
      .toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/ł/g, 'l')
      .replace(/ø/g, 'o')
      .replace(/ß/g, 'ss');
  }

  function words(text) {
    return text.split(/[^a-z0-9]+/).filter(Boolean);
  }

  // Adds the search keys once, when the index is loaded.
  function prepare(rows) {
    return (Array.isArray(rows) ? rows : []).map(function (row, position) {
      var name = String(row.name || '');
      var subtitle = String(row.subtitle || '');
      var nameKey = normalize(name);
      return {
        type: String(row.type || ''),
        name: name,
        subtitle: subtitle,
        url: String(row.url || ''),
        weight: Number(row.weight) || 0,
        position: position,
        nameKey: nameKey,
        nameWords: words(nameKey),
        key: normalize(name + ' ' + subtitle)
      };
    });
  }

  // 0 exact name, 1 name starts with the query, 2 every word starts a word of the name,
  // 3 every word is somewhere in the name, 4 the words are only found through the subtitle (team, league).
  function tier(row, query, tokens) {
    if (row.nameKey === query) return 0;
    if (row.nameKey.indexOf(query) === 0) return 1;
    var startsWord = tokens.every(function (token) {
      return row.nameWords.some(function (word) { return word.indexOf(token) === 0; });
    });
    if (startsWord) return 2;
    if (tokens.every(function (token) { return row.nameKey.indexOf(token) >= 0; })) return 3;
    return 4;
  }

  function inScope(row, scope) {
    var type = SCOPES[scope] === undefined ? null : SCOPES[scope];
    return !type || row.type === type;
  }

  // Rows for a query, best first. `rows` come from prepare().
  function search(rows, query, scope) {
    var q = normalize(query).trim().replace(/\s+/g, ' ');
    if (!q) return [];
    var tokens = q.split(' ');
    var matches = [];
    rows.forEach(function (row) {
      if (!inScope(row, scope)) return;
      if (!tokens.every(function (token) { return row.key.indexOf(token) >= 0; })) return;
      matches.push({ row: row, tier: tier(row, q, tokens) });
    });
    matches.sort(function (a, b) {
      return a.tier - b.tier || b.row.weight - a.row.weight || a.row.position - b.row.position;
    });
    return matches.map(function (match) { return match.row; });
  }

  // Rows for an empty query.
  function featured(rows, scope) {
    var type = SCOPES[scope] === undefined ? null : SCOPES[scope];
    if (type) return rows.filter(function (row) { return row.type === type; }).slice(0, 20);
    var shown = {};
    var result = [];
    ['league', 'team', 'player'].forEach(function (kind) {
      rows.forEach(function (row) {
        if (row.type !== kind) return;
        shown[kind] = (shown[kind] || 0) + 1;
        if (shown[kind] <= FEATURED[kind]) result.push(row);
      });
    });
    return result;
  }

  return { SCOPES: SCOPES, normalize: normalize, prepare: prepare, search: search, featured: featured };
});
