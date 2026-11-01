/* Player comparison page (/compare-players.html).
   The page does not carry the players: plugins/player_compare.py writes
   compare-players/index.json (one short row per player, for the search) and
   compare-players/<uid>.json (the stats of one player, loaded when chosen).

   The first half is pure logic (search, URL selection, comparison rows) and is tested in
   tests/js/player-compare.test.js. The second half builds the page. Events go through
   fbTrack (docs/analytics-events.md) and never carry names or search text. */
(function (root, factory) {
  var api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root && root.document) {
    root.fbPlayerCompare = api;
    api.init(root);
  }
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';

  var SUGGESTIONS = 8;
  var MIN_QUERY = 2;
  // Per-game values of a few games swing a lot; below this the page says so.
  var SMALL_SAMPLE = 5;
  var UID = /^[A-Za-z0-9_-]{1,64}$/;
  var LETTERS = { 'ł': 'l', 'ø': 'o', 'đ': 'd', 'ß': 'ss', 'æ': 'ae', 'œ': 'oe', 'ı': 'i' };

  // 'fi-26-27' -> '2026/27', 'wfc-2024' -> '2024' (same as season_label in src/player_compare.py).
  function seasonLabel(season) {
    var pair = /(\d{2})-(\d{2})$/.exec(String(season || ''));
    if (pair) return '20' + pair[1] + '/' + pair[2];
    var year = /(\d{4})$/.exec(String(season || ''));
    return year ? year[1] : '';
  }

  /* ---------- search ---------- */

  // Lower case, no accents, words separated by single spaces: "Gavlák, Erik" -> "gavlak erik".
  function normalize(text) {
    return String(text == null ? '' : text)
      .toLowerCase()
      .replace(/[łøđßæœı]/g, function (letter) { return LETTERS[letter]; })
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, ' ')
      .trim();
  }

  // index.json ({fields, players: [[...]]}) -> objects with the search keys prepared once.
  function prepareIndex(data) {
    var fields = (data && data.fields) || [];
    return ((data && data.players) || []).map(function (row) {
      var player = {};
      fields.forEach(function (field, position) { player[field] = row[position]; });
      player.nameKey = normalize(player.name);
      player.nameTokens = player.nameKey ? player.nameKey.split(' ') : [];
      player.teamTokens = normalize(player.team).split(' ').filter(Boolean);
      return player;
    });
  }

  function hasPrefix(tokens, prefix) {
    return tokens.some(function (token) { return token.indexOf(prefix) === 0; });
  }

  // Players whose name (words in any order, so "Gavlák Erik" finds "Erik Gavlák") or team
  // starts with every word typed. Exact name first, then names that start with the query,
  // then name matches, then matches that needed the team. The index is sorted by career
  // games, so ties keep the regulars first.
  function search(players, query, options) {
    var opts = options || {};
    var limit = opts.limit || SUGGESTIONS;
    var key = normalize(query);
    if (key.length < MIN_QUERY) return [];
    var words = key.split(' ');
    var hits = [];
    for (var index = 0; index < players.length; index += 1) {
      var player = players[index];
      if (opts.exclude && player.uid === opts.exclude) continue;
      var rank = null;
      if (player.nameKey === key) rank = 0;
      else if (player.nameKey.indexOf(key) === 0) rank = 1;
      else if (words.every(function (word) { return hasPrefix(player.nameTokens, word); })) rank = 2;
      else if (words.every(function (word) { return hasPrefix(player.nameTokens, word) || hasPrefix(player.teamTokens, word); })) rank = 3;
      if (rank !== null) hits.push({ rank: rank, index: index, player: player });
    }
    hits.sort(function (a, b) { return a.rank - b.rank || a.index - b.index; });
    return hits.slice(0, limit).map(function (hit) { return hit.player; });
  }

  /* ---------- selection in the URL ---------- */

  // "?a=<uid>&b=<uid>" -> {a, b}; anything that is not shaped like a player id is dropped.
  function parseSelection(queryString) {
    var params = new URLSearchParams(String(queryString || ''));
    function pick(name) {
      var value = params.get(name) || '';
      return UID.test(value) ? value : '';
    }
    return { a: pick('a'), b: pick('b') };
  }

  function selectionQuery(a, b) {
    var params = new URLSearchParams();
    if (a) params.set('a', a);
    if (b) params.set('b', b);
    var text = params.toString();
    return text ? '?' + text : '';
  }

  /* ---------- comparison ---------- */

  function perGame(total, games) {
    return games > 0 ? total / games : null;
  }

  function seasonValue(key) {
    return function (player) {
      var current = player.current || {};
      if (key.slice(-4) === '_per') return perGame(current[key.slice(0, -4)] || 0, current.games || 0);
      return current[key] == null ? null : current[key];
    };
  }

  function careerValue(key) {
    return function (player) {
      var career = player.career || {};
      if (key.slice(-4) === '_per') return perGame(career[key.slice(0, -4)] || 0, career.games || 0);
      return career[key] == null ? null : career[key];
    };
  }

  function clutchValue(scope, key) {
    return function (player) {
      var line = player.clutch && player.clutch[scope];
      return line && line[key] != null ? line[key] : null;
    };
  }

  function shareValue(player) {
    return player.share && player.share.share != null ? player.share.share : null;
  }

  function shareDetail(player) {
    return player.share ? player.share.points + ' of ' + player.share.team_goals + ' goals' : '';
  }

  function seasonCount(player) {
    return player.seasons > 0 ? player.seasons : null;
  }

  // better: 'high' (more is better), 'low' (less is better, penalty minutes), null (no winner).
  // primary rows are the per-game values, the fair comparison across leagues.
  var SECTIONS = [
    {
      id: 'latest', title: 'Latest season',
      rows: [
        { key: 'games', label: 'Games', kind: 'int', better: 'high', value: seasonValue('games') },
        { key: 'goals', label: 'Goals', kind: 'int', better: 'high', value: seasonValue('goals') },
        { key: 'assists', label: 'Assists', kind: 'int', better: 'high', value: seasonValue('assists') },
        { key: 'points', label: 'Points', kind: 'int', better: 'high', value: seasonValue('points') },
        { key: 'points_per_game', label: 'Points per game', kind: 'rate', better: 'high', primary: true, value: seasonValue('points_per') },
        { key: 'goals_per_game', label: 'Goals per game', kind: 'rate', better: 'high', primary: true, value: seasonValue('goals_per') },
        { key: 'assists_per_game', label: 'Assists per game', kind: 'rate', better: 'high', primary: true, value: seasonValue('assists_per') },
        { key: 'pim', label: 'Penalty minutes', kind: 'int', better: 'low', value: seasonValue('pim') },
        { key: 'pim_per_game', label: 'Penalty minutes per game', kind: 'rate', better: 'low', primary: true, value: seasonValue('pim_per') },
        { key: 'share', label: 'Share of team goals', kind: 'percent', better: 'high', value: shareValue, detail: shareDetail },
        { key: 'gwg', label: 'Game winners', kind: 'int', better: 'high', value: clutchValue('current', 'gwg') },
        { key: 'clutch', label: 'Clutch points', kind: 'int', better: 'high', value: clutchValue('current', 'clutch_points') }
      ]
    },
    {
      id: 'career', title: 'Career, all seasons on the site',
      rows: [
        { key: 'seasons', label: 'Seasons', kind: 'int', better: null, value: seasonCount },
        { key: 'games', label: 'Games', kind: 'int', better: 'high', value: careerValue('games') },
        { key: 'goals', label: 'Goals', kind: 'int', better: 'high', value: careerValue('goals') },
        { key: 'assists', label: 'Assists', kind: 'int', better: 'high', value: careerValue('assists') },
        { key: 'points', label: 'Points', kind: 'int', better: 'high', value: careerValue('points') },
        { key: 'points_per_game', label: 'Points per game', kind: 'rate', better: 'high', primary: true, value: careerValue('points_per') },
        { key: 'goals_per_game', label: 'Goals per game', kind: 'rate', better: 'high', primary: true, value: careerValue('goals_per') },
        { key: 'assists_per_game', label: 'Assists per game', kind: 'rate', better: 'high', primary: true, value: careerValue('assists_per') },
        { key: 'pim', label: 'Penalty minutes', kind: 'int', better: 'low', value: careerValue('pim') },
        { key: 'pim_per_game', label: 'Penalty minutes per game', kind: 'rate', better: 'low', primary: true, value: careerValue('pim_per') },
        { key: 'gwg', label: 'Game winners', kind: 'int', better: 'high', value: clutchValue('all', 'gwg') },
        { key: 'clutch', label: 'Clutch points', kind: 'int', better: 'high', value: clutchValue('all', 'clutch_points') }
      ]
    }
  ];

  function format(kind, value) {
    if (value == null) return '–';
    if (kind === 'rate') return value.toFixed(2);
    if (kind === 'percent') return Math.round(value) + '%';
    return String(value);
  }

  // 'a', 'b' or '' (tie, no data on one side, or a row without a winner).
  function winner(a, b, better) {
    if (!better || a == null || b == null || a === b) return '';
    var aIsBetter = better === 'high' ? a > b : a < b;
    return aIsBetter ? 'a' : 'b';
  }

  function leagueNote(a, b) {
    if (!a.league || !b.league || normalize(a.league) === normalize(b.league)) return '';
    return a.name + ' plays in ' + a.league + ' and ' + b.name + ' in ' + b.league + '. Leagues differ in how many goals are scored per game, so the per-game rows say more than the totals.';
  }

  function seasonNote(a, b) {
    if (!a.season_label || !b.season_label || a.season === b.season) return '';
    return 'The latest season on the site is ' + a.season_label + ' for ' + a.name + ' and ' + b.season_label + ' for ' + b.name + '.';
  }

  function sampleNote(a, b) {
    var small = [a, b].filter(function (player) {
      var games = player.current && player.current.games;
      return games > 0 && games < SMALL_SAMPLE;
    }).map(function (player) { return player.name; });
    if (!small.length) return '';
    return 'Only a few games in the latest season for ' + small.join(' and ') + ': one good night moves the per-game values a lot.';
  }

  // {notes: [text], sections: [{id, title, rows: [{key, label, kind, primary, a, b, winner, detailA, detailB}]}]}
  // Rows without data for both players are left out.
  function compare(a, b) {
    var sections = SECTIONS.map(function (section) {
      var rows = [];
      section.rows.forEach(function (row) {
        var left = row.value(a);
        var right = row.value(b);
        if (left == null && right == null) return;
        rows.push({
          key: row.key,
          label: row.label,
          kind: row.kind,
          primary: !!row.primary,
          a: format(row.kind, left),
          b: format(row.kind, right),
          winner: winner(left, right, row.better),
          detailA: row.detail && left != null ? row.detail(a) : '',
          detailB: row.detail && right != null ? row.detail(b) : ''
        });
      });
      return { id: section.id, title: section.title, rows: rows };
    }).filter(function (section) { return section.rows.length; });
    var notes = [leagueNote(a, b), seasonNote(a, b), sampleNote(a, b)].filter(Boolean);
    return { notes: notes, sections: sections };
  }

  /* ---------- page ---------- */

  function init(win) {
    var doc = win.document;
    var page = doc.querySelector('[data-compare]');
    if (!page) return;
    var site = page.getAttribute('data-site') || '';
    var output = page.querySelector('[data-compare-output]');
    var slots = {};
    var chosen = { a: null, b: null };
    var index = null;
    var indexRequest = null;
    var requests = { a: 0, b: 0 };
    var track = win.fbTrack || null;
    var trackers = {};

    function el(tag, className, children) {
      var node = doc.createElement(tag);
      if (className) node.className = className;
      [].concat(children == null ? [] : children).forEach(function (child) { node.append(child); });
      return node;
    }

    function fetchJson(path) {
      return win.fetch(site + path).then(function (response) {
        if (!response.ok) throw new Error(String(response.status));
        return response.json();
      });
    }

    function loadIndex() {
      if (!indexRequest) {
        indexRequest = fetchJson('/compare-players/index.json').then(function (data) {
          index = prepareIndex(data);
          return index;
        }).catch(function (error) {
          indexRequest = null;
          throw error;
        });
      }
      return indexRequest;
    }

    function describe(player) {
      return [player.team, player.league, player.season_label || seasonLabel(player.season)].filter(Boolean).join(' · ');
    }

    function suggestionText(player) {
      var parts = [player.team, player.league, seasonLabel(player.season)];
      if (player.games) parts.push(player.games + ' games');
      return parts.filter(Boolean).join(' · ');
    }

    function setPicked(slot, player) {
      var ui = slots[slot];
      ui.input.value = player ? player.name : '';
      ui.picked.textContent = player ? describe(player) : '';
      ui.clear.hidden = !player;
    }

    function closeList(slot) {
      var ui = slots[slot];
      ui.list.hidden = true;
      ui.list.replaceChildren();
      ui.input.setAttribute('aria-expanded', 'false');
      ui.input.removeAttribute('aria-activedescendant');
      ui.matches = [];
      ui.active = -1;
    }

    function highlight(slot, position) {
      var ui = slots[slot];
      ui.active = position;
      Array.prototype.forEach.call(ui.list.children, function (item, itemPosition) {
        item.setAttribute('aria-selected', itemPosition === position ? 'true' : 'false');
        if (itemPosition === position) ui.input.setAttribute('aria-activedescendant', item.id);
      });
      if (position < 0) ui.input.removeAttribute('aria-activedescendant');
    }

    function openList(slot, matches, hasQuery) {
      var ui = slots[slot];
      ui.matches = matches;
      ui.list.replaceChildren();
      if (!matches.length) {
        if (hasQuery) ui.list.append(el('li', 'px-3 py-2 text-sm text-ink-muted', 'No player found'));
        ui.list.hidden = !hasQuery;
        ui.input.setAttribute('aria-expanded', hasQuery ? 'true' : 'false');
        return;
      }
      matches.forEach(function (player, position) {
        var item = el('li', 'cursor-pointer px-3 py-2 aria-selected:bg-rink-soft', [
          el('span', 'block font-semibold text-ink', player.name),
          el('span', 'block text-xs text-ink-muted', suggestionText(player))
        ]);
        item.id = 'compare-' + slot + '-option-' + position;
        item.setAttribute('role', 'option');
        item.setAttribute('aria-selected', 'false');
        // mousedown, not click: the input would lose focus (and close the list) first.
        item.addEventListener('mousedown', function (event) {
          event.preventDefault();
          choose(slot, player, position + 1);
        });
        ui.list.append(item);
      });
      ui.list.hidden = false;
      ui.input.setAttribute('aria-expanded', 'true');
      highlight(slot, -1);
    }

    function other(slot) { return slot === 'a' ? 'b' : 'a'; }

    function showMessage(text) {
      output.replaceChildren(el('p', 'm-0 rounded-lg border border-line bg-surface-raised p-4 text-ink-muted', text));
    }

    function writeUrl() {
      var query = selectionQuery(chosen.a && chosen.a.uid, chosen.b && chosen.b.uid);
      try { win.history.replaceState(null, '', win.location.pathname + query); } catch (error) { /* file:// previews */ }
    }

    function link(player) {
      var anchor = el('a', 'text-ink underline decoration-line-strong underline-offset-2 hover:text-rink', player.name);
      anchor.href = site + '/' + player.url;
      return anchor;
    }

    function header(player, side) {
      var teamLine = [];
      if (player.team) {
        if (player.team_url) {
          var team = el('a', 'text-ink-muted underline decoration-line-strong underline-offset-2 hover:text-rink', player.team);
          team.href = site + '/' + player.team_url;
          teamLine.push(team);
        } else {
          teamLine.push(player.team);
        }
      }
      if (player.league) teamLine.push((teamLine.length ? ' · ' : '') + player.league);
      return el('div', 'grid min-w-0 content-start gap-1 ' + (side === 'b' ? 'text-right' : ''), [
        el('div', 'fs-label', 'Player ' + side.toUpperCase()),
        el('div', 'font-display text-xl font-bold text-balance sm:text-2xl', link(player)),
        el('div', 'text-sm text-ink-muted', teamLine)
      ]);
    }

    function valueCell(row, side) {
      var better = row.winner === side;
      var cell = el('td', 'px-2 py-2 tabular-nums align-middle ' + (side === 'b' ? 'text-right' : 'text-left') + (better ? ' bg-rink-soft font-bold text-ink' : ' text-ink'));
      cell.append(row[side]);
      if (better) cell.append(el('span', 'sr-only', ' (better)'));
      var detail = side === 'a' ? row.detailA : row.detailB;
      if (detail) cell.append(el('div', 'text-xs font-normal text-ink-muted', detail));
      return cell;
    }

    function renderTable(section, a, b) {
      var columns = el('colgroup', '', ['w-[30%]', 'w-[40%]', 'w-[30%]'].map(function (width) { return el('col', width); }));
      var head = el('thead', '', el('tr', '', [
        el('th', 'truncate px-2 py-2 text-left', a.name),
        el('th', 'px-2 py-2'),
        el('th', 'truncate px-2 py-2 text-right', b.name)
      ]));
      var body = el('tbody', '', section.rows.map(function (row) {
        var label = el('th', 'px-2 py-2 text-center align-middle text-xs normal-case tracking-normal sm:text-sm ' + (row.primary ? 'font-semibold text-ink' : 'font-normal text-ink-muted'), row.label);
        label.scope = 'row';
        return el('tr', '', [valueCell(row, 'a'), label, valueCell(row, 'b')]);
      }));
      var caption = el('caption', 'caption-top px-2 pb-2 text-left font-display text-lg font-bold text-ink', section.title);
      return el('div', 'fs-table-wrap', el('table', 'fs-table table-fixed', [caption, columns, head, body]));
    }

    function render() {
      writeUrl();
      if (!chosen.a || !chosen.b) {
        showMessage(chosen.a || chosen.b ? 'Choose a second player to see the two side by side.' : 'Choose two players to see their stats side by side.');
        return;
      }
      if (chosen.a.uid === chosen.b.uid) {
        showMessage('Choose two different players.');
        return;
      }
      var result = compare(chosen.a, chosen.b);
      var nodes = [el('section', 'grid grid-cols-2 gap-4 rounded-lg border border-line bg-surface-raised p-4', [header(chosen.a, 'a'), header(chosen.b, 'b')])];
      if (result.notes.length) {
        nodes.push(el('div', 'grid gap-2 rounded-lg border border-line bg-surface-sunken p-4 text-sm text-ink-muted', result.notes.map(function (note) { return el('p', 'm-0', note); })));
      }
      result.sections.forEach(function (section) { nodes.push(renderTable(section, chosen.a, chosen.b)); });
      output.replaceChildren.apply(output, nodes);
    }

    function loadPlayer(slot, uid) {
      var request = requests[slot] += 1;
      return fetchJson('/compare-players/' + encodeURIComponent(uid) + '.json').then(function (player) {
        if (request !== requests[slot]) return;
        slots[slot].pending = null;
        chosen[slot] = player;
        setPicked(slot, player);
        render();
      }).catch(function () {
        if (request !== requests[slot]) return;
        slots[slot].pending = null;
        chosen[slot] = null;
        setPicked(slot, null);
        showMessage('That player could not be loaded.');
      });
    }

    function choose(slot, player, position) {
      closeList(slot);
      // Until the player file arrives the box keeps showing the choice, also after a blur.
      slots[slot].pending = player;
      setPicked(slot, player);
      if (track) {
        track.searchResultClicked('compare_players', 'player', position);
        // Not filterChanged: choosing another player for the same side is a change too.
        track.capture('filter_changed', { filter_name: 'compare_player', filter_value: slot, filter_scope: 'compare_players' });
      }
      loadPlayer(slot, player.uid);
    }

    function clear(slot) {
      requests[slot] += 1;
      slots[slot].pending = null;
      chosen[slot] = null;
      setPicked(slot, null);
      closeList(slot);
      render();
      slots[slot].input.focus();
    }

    function swap() {
      var first = chosen.a;
      chosen.a = chosen.b;
      chosen.b = first;
      setPicked('a', chosen.a);
      setPicked('b', chosen.b);
      render();
    }

    function onInput(slot) {
      var ui = slots[slot];
      var text = ui.input.value;
      loadIndex().then(function (players) {
        if (ui.input.value !== text) return;
        var matches = search(players, text, { exclude: chosen[other(slot)] && chosen[other(slot)].uid });
        openList(slot, matches, normalize(text).length >= MIN_QUERY);
        if (trackers[slot]) trackers[slot].update(text, matches.length);
      }).catch(function () {
        ui.list.replaceChildren(el('li', 'px-3 py-2 text-sm text-ink-muted', 'The player list could not be loaded.'));
        ui.list.hidden = false;
      });
    }

    function onKey(slot, event) {
      var ui = slots[slot];
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        if (!ui.matches.length) return;
        event.preventDefault();
        var step = event.key === 'ArrowDown' ? 1 : -1;
        highlight(slot, (ui.active + step + ui.matches.length) % ui.matches.length);
      } else if (event.key === 'Enter') {
        var pick = ui.matches[ui.active >= 0 ? ui.active : 0];
        if (pick && !ui.list.hidden) {
          event.preventDefault();
          choose(slot, pick, (ui.active >= 0 ? ui.active : 0) + 1);
        }
      } else if (event.key === 'Escape') {
        closeList(slot);
        setPicked(slot, chosen[slot] || ui.pending);
      }
    }

    ['a', 'b'].forEach(function (slot) {
      var root = page.querySelector('[data-compare-slot="' + slot + '"]');
      var ui = slots[slot] = {
        input: root.querySelector('[data-compare-input]'),
        list: root.querySelector('[data-compare-list]'),
        picked: root.querySelector('[data-compare-picked]'),
        clear: root.querySelector('[data-compare-clear]'),
        matches: [],
        active: -1,
        pending: null
      };
      trackers[slot] = track ? track.searchTracker('compare_players') : null;
      ui.input.addEventListener('focus', function () { loadIndex().catch(function () {}); });
      ui.input.addEventListener('input', function () { onInput(slot); });
      ui.input.addEventListener('keydown', function (event) { onKey(slot, event); });
      ui.input.addEventListener('blur', function () {
        if (trackers[slot]) trackers[slot].flush();
        closeList(slot);
        setPicked(slot, chosen[slot] || ui.pending);
      });
      ui.clear.addEventListener('click', function () { clear(slot); });
    });
    page.querySelector('[data-compare-swap]').addEventListener('click', swap);

    var start = parseSelection(win.location.search);
    if (start.a === start.b) start.b = '';
    showMessage('Choose two players to see their stats side by side.');
    ['a', 'b'].forEach(function (slot) {
      setPicked(slot, null);
      if (start[slot]) loadPlayer(slot, start[slot]);
    });
  }

  return {
    init: init,
    normalize: normalize,
    seasonLabel: seasonLabel,
    prepareIndex: prepareIndex,
    search: search,
    parseSelection: parseSelection,
    selectionQuery: selectionQuery,
    compare: compare,
    winner: winner,
    SMALL_SAMPLE: SMALL_SAMPLE
  };
});
