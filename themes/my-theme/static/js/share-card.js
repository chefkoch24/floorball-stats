/* Share studio: Instagram cards drawn in the browser when someone taps Share.
   Four cards (game, team, player, table), each as Story (1080x1920) or Post
   (1080x1350), in the dark or light theme of the design system. Nothing is
   generated at build time. Layouts follow the share-card designs on the canvas. */
(function () {
  'use strict';

  const FORMATS = {
    story: { w: 1080, h: 1920, top: 160, bottom: 240, side: 96, gap: 72, label: 'Story' },
    post: { w: 1080, h: 1350, top: 96, bottom: 96, side: 96, gap: 56, label: 'Post' },
  };
  const DISPLAY = 'Archivo, "Arial Narrow", system-ui, sans-serif';
  const BODY = '"Instrument Sans", system-ui, -apple-system, "Segoe UI", sans-serif';
  const LABEL_SIZE = 26;

  function track(eventName, payload) {
    if (window.posthog && typeof window.posthog.capture === 'function') {
      window.posthog.capture(eventName, payload);
    }
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  }

  // Token values of one theme, read from the stylesheet so the cards follow the design system.
  function palette(theme) {
    const probe = document.createElement('div');
    probe.setAttribute('data-theme', theme);
    probe.hidden = true;
    document.body.appendChild(probe);
    const style = getComputedStyle(probe);
    const read = (name) => style.getPropertyValue('--' + name).trim();
    const colors = {
      surface: read('surface'), raised: read('surface-raised'), sunken: read('surface-sunken'),
      line: read('line'), lineStrong: read('line-strong'), ink: read('ink'), muted: read('ink-muted'),
      rink: read('rink'), onRink: read('on-rink'), ball: read('ball'), ballInk: read('ball-ink'),
      win: read('win'), winSoft: read('win-soft'), loss: read('loss'), lossSoft: read('loss-soft'),
      otl: read('otl'), otlSoft: read('otl-soft'), onCrest: read('on-crest'),
      crest: [1, 2, 3, 4, 5, 6, 7, 8].map((n) => read('crest-' + n)),
    };
    probe.remove();
    return colors;
  }

  let fontsReady = null;
  function loadFonts() {
    if (!fontsReady) {
      const faces = ['800 100px Archivo', 'condensed 800 100px Archivo', 'semi-expanded 800 100px Archivo', '700 40px Archivo',
        '600 40px Archivo', '500 40px Archivo', '400 40px "Instrument Sans"', '500 40px "Instrument Sans"',
        '600 40px "Instrument Sans"', '700 40px "Instrument Sans"'];
      fontsReady = Promise.all(faces.map((face) => document.fonts.load(face).catch(() => null)));
    }
    return fontsReady;
  }

  /* ---------- Painter: drawing primitives bound to one canvas, format and palette ---------- */

  function painter(canvas, format, colors) {
    const ctx = canvas.getContext('2d');
    canvas.width = format.w;
    canvas.height = format.h;
    const p = { ctx, c: colors, f: format, left: format.side, right: format.w - format.side, width: format.w - format.side * 2 };

    p.font = (weight, size, family, stretch) => {
      ctx.font = `${weight} ${size}px ${family}`;
      if ('fontStretch' in ctx) ctx.fontStretch = stretch || 'normal';
    };
    p.measure = (text, weight, size, family, stretch) => {
      p.font(weight, size, family, stretch);
      return ctx.measureText(text).width;
    };
    p.text = (text, x, y, o) => {
      p.font(o.weight, o.size, o.family || BODY, o.stretch);
      ctx.fillStyle = o.color || colors.ink;
      ctx.textAlign = o.align || 'left';
      ctx.textBaseline = o.baseline || 'middle';
      ctx.fillText(String(text), x, y);
    };
    p.label = (text, x, y, color) => p.text(String(text).toUpperCase(), x, y, { weight: 600, size: LABEL_SIZE, color: color || colors.muted, baseline: 'top' });
    p.rect = (x, y, w, h, r, fill, stroke) => {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + w, y, x + w, y + h, r);
      ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r);
      ctx.arcTo(x, y, x + w, y, r);
      ctx.closePath();
      if (fill) { ctx.fillStyle = fill; ctx.fill(); }
      if (stroke) { ctx.lineWidth = 2; ctx.strokeStyle = stroke; ctx.stroke(); }
    };
    p.hline = (y, x, w) => { ctx.fillStyle = colors.line; ctx.fillRect(x === undefined ? p.left : x, y, w === undefined ? p.width : w, 2); };
    // A pill-shaped label; returns its size. `x` is its left edge (or right edge with align: 'right').
    p.pill = (text, x, y, o) => {
      const w = p.measure(text, o.weight, o.size, o.family || BODY, o.stretch) + o.padX * 2;
      const h = Math.round(o.size * 1.3 + o.padY * 2);
      const left = o.align === 'right' ? x - w : x;
      p.rect(left, y, w, h, o.radius, o.fill, o.stroke);
      p.text(text, left + o.padX, y + h / 2, { weight: o.weight, size: o.size, family: o.family, stretch: o.stretch, color: o.color });
      return { w, h };
    };
    p.crest = (cx, cy, d, index, initials) => {
      ctx.beginPath();
      ctx.arc(cx, cy, d / 2, 0, Math.PI * 2);
      ctx.fillStyle = colors.crest[(Number(index) || 8) - 1];
      ctx.fill();
      p.text(initials, cx, cy + 2, { weight: 800, size: Math.round(d / 3), family: DISPLAY, stretch: 'semi-condensed', color: colors.onCrest, align: 'center' });
    };
    // Largest size (down to min) at which text fits maxWidth in up to maxLines lines.
    p.fit = (text, maxWidth, size, minSize, weight, family, stretch, maxLines) => {
      const wrap = () => {
        const lines = [];
        String(text).split(/\s+/).filter(Boolean).forEach((word) => {
          const last = lines[lines.length - 1];
          if (last && ctx.measureText(last + ' ' + word).width <= maxWidth) lines[lines.length - 1] = last + ' ' + word;
          else lines.push(word);
        });
        return lines;
      };
      for (let s = size; s >= minSize; s -= 2) {
        p.font(weight, s, family, stretch);
        const lines = wrap();
        if (lines.length <= maxLines && lines.every((line) => ctx.measureText(line).width <= maxWidth)) return { size: s, lines };
      }
      p.font(weight, minSize, family, stretch);
      return { size: minSize, lines: wrap().slice(0, maxLines) };
    };
    p.lines = (fitted, x, top, o) => {
      const lh = Math.round(fitted.size * (o.lineHeight || 1.0));
      fitted.lines.forEach((line, i) => p.text(line, x, top + i * lh, { ...o, size: fitted.size, baseline: 'top' }));
      return fitted.lines.length * lh;
    };
    // A tile with a label and a big value, as on the team and player cards.
    p.tile = (x, y, w, h, label, value, valueSize) => {
      p.rect(x, y, w, h, 24, colors.raised, colors.line);
      p.label(label, x + 32, y + 32);
      p.text(value, x + 32, y + h - 32, { weight: 700, size: valueSize, family: DISPLAY, baseline: 'alphabetic' });
    };
    return p;
  }

  /* ---------- Frame: background, header and footer; blocks are stacked and centred between ---------- */

  function compose(p, header, blocks, footer) {
    const { ctx, c, f } = p;
    ctx.fillStyle = c.surface;
    ctx.fillRect(0, 0, f.w, f.h);
    p.text('Floorball Stats', p.left, f.top + 22, { weight: 800, size: 44, family: DISPLAY, stretch: 'condensed', color: c.rink });
    if (header.badge) {
      p.pill(header.chip, p.right, f.top, { weight: 700, size: 24, padX: 22, padY: 10, radius: 30, fill: c.ball, color: c.surface, align: 'right' });
    } else {
      p.pill(header.chip, p.right, f.top, { weight: 600, size: 26, padX: 22, padY: 10, radius: 30, stroke: c.line, color: c.muted, align: 'right' });
    }
    const footerY = f.h - f.bottom - 20;
    p.text(footer, p.left, footerY, { weight: 500, size: 28, color: c.muted });
    p.text('stats.floorballconnect.com', p.right, footerY, { weight: 700, size: 30, family: DISPLAY, color: c.rink, align: 'right' });

    const top = f.top + 50 + f.gap;
    const bottom = footerY - 20 - f.gap;
    const total = blocks.reduce((sum, block) => sum + block.h, 0) + f.gap * (blocks.length - 1);
    let y = top + Math.max(0, (bottom - top - total) / 2);
    blocks.forEach((block) => { block.draw(y); y += block.h + f.gap; });
  }

  /* ---------- Data helpers ---------- */

  function gameEvents() {
    const timeline = document.getElementById('gameEventsTimeline');
    const b64 = timeline ? timeline.dataset.eventsB64 : '';
    if (!b64) return [];
    try {
      const bytes = Uint8Array.from(atob(b64), (ch) => ch.charCodeAt(0));
      return JSON.parse(new TextDecoder().decode(bytes));
    } catch (error) {
      return [];
    }
  }

  function topScorers(events) {
    const players = new Map();
    const credit = (name, key) => {
      const clean = String(name || '').trim();
      if (!clean) return;
      const entry = players.get(clean) || { name: clean, goals: 0, assists: 0 };
      entry[key] += 1;
      players.set(clean, entry);
    };
    events.filter((e) => e.event_kind === 'goal').forEach((e) => {
      credit(e.title, 'goals');
      String(e.assist || '').split('/').forEach((name) => credit(name, 'assists'));
    });
    return Array.from(players.values()).sort((a, b) => (b.goals + b.assists) - (a.goals + a.assists) || b.goals - a.goals);
  }

  // Longest run of unanswered goals: {count, against, period}.
  function longestRun(events) {
    let best = null;
    let current = null;
    events.filter((e) => e.event_kind === 'goal').forEach((e) => {
      if (current && current.team === e.team) {
        current.count += 1;
      } else {
        current = { team: e.team, count: 1, period: e.period };
      }
      if (!best || current.count > best.count) best = { ...current };
    });
    return best && best.count >= 3 ? best : null;
  }

  function signed(n) {
    return n > 0 ? `+${n}` : n < 0 ? `−${-n}` : '0';
  }

  /* ---------- Cards ---------- */

  function gameCard(p, data, format) {
    const { c } = p;
    const events = gameEvents();
    const scorers = topScorers(events).slice(0, 3);
    const sides = [
      { name: data.home, goals: data.homeGoals, crest: data.homeCrest, initials: data.homeInitials, lost: data.homeGoals < data.awayGoals },
      { name: data.away, goals: data.awayGoals, crest: data.awayCrest, initials: data.awayInitials, lost: data.awayGoals < data.homeGoals },
    ];
    const blocks = [];
    const chips = (x, y, fill) => {
      data.periods.forEach((period) => {
        x += p.pill(period, x, y, { weight: 600, size: format === 'story' ? 30 : 28, family: DISPLAY, padX: 22, padY: 10, radius: 16, fill, color: c.muted }).w + 16;
      });
    };
    const statusPill = (x, y, align) => p.pill(data.status.toUpperCase(), x, y, { weight: 700, size: 26, padX: 20, padY: 8, radius: 30, fill: c.sunken, color: c.ink, align });

    if (format === 'story') {
      blocks.push({ h: 50 + 32 + 400 + 32 + 59, draw: (y) => {
        const s = statusPill(p.left, y);
        p.text(data.date, p.left + s.w + 20, y + s.h / 2, { weight: 500, size: 30, color: c.muted });
        let rowY = y + 50 + 32;
        const nameX = p.left + 144 + 32;
        const nameW = p.right - 240 - 32 - nameX;
        sides.forEach((side, i) => {
          const mid = rowY + 88;
          p.crest(p.left + 72, mid, 144, side.crest, side.initials);
          const fitted = p.fit(side.name, nameW, 64, 40, 800, DISPLAY, 'condensed', 2);
          p.lines(fitted, nameX, mid - (fitted.lines.length * fitted.size * 1.04) / 2, { weight: 800, family: DISPLAY, stretch: 'condensed', color: side.lost ? c.muted : c.ink, lineHeight: 1.04 });
          p.text(side.goals, p.right, mid + 72, { weight: 800, size: 200, family: DISPLAY, stretch: 'semi-expanded', color: side.lost ? c.muted : c.ink, align: 'right', baseline: 'alphabetic' });
          rowY += 176;
          if (i === 0) { p.hline(rowY + 23); rowY += 48; }
        });
        chips(p.left, rowY + 32, c.raised);
      } });

      const axisH = 112;
      blocks.push({ h: 34 + 24 + axisH + 16 + 24, draw: (y) => {
        p.label('Goals over 60 minutes', p.left, y);
        const axisY = y + 58 + 56;
        p.ctx.fillStyle = c.lineStrong;
        p.ctx.fillRect(p.left, axisY, p.width, 2);
        p.ctx.fillStyle = c.line;
        [1, 2].forEach((k) => p.ctx.fillRect(p.left + p.width * k / 3, axisY - 40, 2, 80));
        const dot = (minute, above, crest) => {
          p.ctx.beginPath();
          p.ctx.arc(p.left + p.width * Math.min(Math.max(minute, 0), 60) / 60, above ? axisY - 30 : axisY + 32, 11, 0, Math.PI * 2);
          p.ctx.fillStyle = c.crest[(Number(crest) || 8) - 1];
          p.ctx.fill();
        };
        data.homeMinutes.forEach((m) => dot(m, true, data.homeCrest));
        data.awayMinutes.forEach((m) => dot(m, false, data.awayCrest));
        ["0'", "20'", "40'", "60'"].forEach((label, i) => {
          p.text(label, p.left + p.width * i / 3, y + 58 + axisH + 16, { weight: 500, size: 24, family: DISPLAY, color: c.muted, baseline: 'top', align: i === 0 ? 'left' : i === 3 ? 'right' : 'center' });
        });
      } });

      if (scorers.length) {
        blocks.push({ h: 34 + 20 + scorers.length * 76 + 2, draw: (y) => {
          p.label('Top scorers', p.left, y);
          let rowY = y + 54;
          scorers.forEach((player) => {
            p.hline(rowY);
            p.text(player.name, p.left, rowY + 38, { weight: 600, size: 36 });
            p.text(`${player.goals} G · ${player.assists} A`, p.right, rowY + 38, { weight: 700, size: 36, family: DISPLAY, align: 'right' });
            rowY += 76;
          });
          p.hline(rowY);
        } });
      }
      return { header: { chip: data.league }, blocks, footer: 'Full stats and timeline' };
    }

    // Post: scoreboard panel plus up to three highlight tiles.
    const panelH = 48 + 50 + 36 + 136 + 20 + 80 + 36 + 56 + 48;
    blocks.push({ h: panelH, draw: (y) => {
      p.rect(p.left, y, p.width, panelH, 32, c.raised, c.line);
      const cx = p.left + p.width / 2;
      const s = p.measure(data.status.toUpperCase(), 700, 26, BODY) + 40;
      statusPill(cx - s / 2, y + 48);
      const rowY = y + 48 + 50 + 36;
      const colW = (p.width - 96 - 360) / 2;
      sides.forEach((side, i) => {
        const colX = i === 0 ? p.left + 48 + colW / 2 : p.right - 48 - colW / 2;
        p.crest(colX, rowY + 68, 136, side.crest, side.initials);
        const fitted = p.fit(side.name, colW, 40, 28, 800, DISPLAY, 'condensed', 2);
        const lh = Math.round(fitted.size * 1.05);
        fitted.lines.forEach((line, k) => p.text(line, colX, rowY + 136 + 20 + k * lh, { weight: 800, size: fitted.size, family: DISPLAY, stretch: 'condensed', color: side.lost ? c.muted : c.ink, align: 'center', baseline: 'top' }));
      });
      const scoreY = rowY + 68 + 42;
      const home = String(data.homeGoals);
      const away = String(data.awayGoals);
      p.font(800, 120, DISPLAY, 'semi-expanded');
      const wHome = p.ctx.measureText(home).width;
      const wColon = p.ctx.measureText(':').width;
      const wAway = p.ctx.measureText(away).width;
      let x = cx - (wHome + wColon + wAway) / 2;
      [[home, sides[0].lost ? c.muted : c.ink], [':', c.lineStrong], [away, sides[1].lost ? c.muted : c.ink]].forEach(([t, color]) => {
        p.text(t, x, scoreY, { weight: 800, size: 120, family: DISPLAY, stretch: 'semi-expanded', color, baseline: 'alphabetic' });
        x += p.ctx.measureText(t).width;
      });
      const chipsW = data.periods.reduce((sum, period) => sum + p.measure(period, 600, 28, DISPLAY) + 44 + 16, -16);
      chips(cx - chipsW / 2, y + panelH - 48 - 56, c.sunken);
    } });

    const tiles = scorers.slice(0, 2).map((player) => ({
      value: `${player.goals + player.assists} P`, title: player.name,
      sub: player.goals && player.assists ? `${player.goals} goals, ${player.assists} assists` : player.goals ? `${player.goals} goals` : `${player.assists} assists`,
    }));
    const run = longestRun(events);
    if (run) tiles.push({ value: `${run.count}–0`, title: `Run in period ${run.period}`, sub: run.team });
    if (tiles.length) {
      const tileH = 240;
      blocks.push({ h: tileH, draw: (y) => {
        const gap = 24;
        const w = (p.width - gap * (tiles.length - 1)) / tiles.length;
        tiles.forEach((tile, i) => {
          const x = p.left + i * (w + gap);
          p.rect(x, y, w, tileH, 24, null, c.line);
          p.text(tile.value, x + 32, y + 32, { weight: 700, size: 56, family: DISPLAY, baseline: 'top' });
          const title = p.fit(tile.title, w - 64, 28, 22, 600, BODY, 'normal', 2);
          const used = p.lines(title, x + 32, y + 32 + 56 + 16, { weight: 600, family: BODY, lineHeight: 1.2 });
          const sub = p.fit(tile.sub, w - 64, 24, 20, 400, BODY, 'normal', 2);
          p.lines(sub, x + 32, y + 32 + 56 + 16 + used + 8, { weight: 400, family: BODY, color: c.muted, lineHeight: 1.3 });
        });
      } });
    }
    return { header: { chip: `${data.league} · ${data.dateShort}` }, blocks, footer: data.attendance ? `${data.attendance} spectators` : 'Full stats and timeline' };
  }

  function formTiles(p, form, y, h, size) {
    const { c } = p;
    const gap = 16;
    const slots = 5;
    const w = (p.width - gap * (slots - 1)) / slots;
    form.forEach((letter, i) => {
      const style = letter === 'W' ? [c.winSoft, c.win] : letter === 'L' ? [c.lossSoft, c.loss] : letter === 'D' ? [c.sunken, c.muted] : [c.otlSoft, c.otl];
      const x = p.left + i * (w + gap);
      p.rect(x, y, w, h, 20, style[0]);
      p.text(letter, x + w / 2, y + h / 2 + 2, { weight: 800, size: letter.length > 1 ? size - 8 : size, family: DISPLAY, color: style[1], align: 'center' });
    });
  }

  function teamCard(p, data, format) {
    const { c } = p;
    const story = format === 'story';
    const crestD = story ? 176 : 128;
    const nameSize = story ? 104 : 84;
    const rankSize = story ? 150 : 112;
    const fitted = p.fit(data.name, p.width, nameSize, 56, 800, DISPLAY, 'condensed', 2);
    const nameH = fitted.lines.length * Math.round(fitted.size * 0.95);
    const blocks = [];
    blocks.push({ h: crestD + 32 + nameH, draw: (y) => {
      p.crest(p.left + crestD / 2, y + crestD / 2, crestD, data.crest, data.initials);
      if (data.rank) {
        p.text(`#${data.rank}`, p.right, y + crestD / 2 + rankSize * 0.32, { weight: 800, size: rankSize, family: DISPLAY, stretch: 'semi-expanded', color: c.rink, align: 'right', baseline: 'alphabetic' });
        p.text(`of ${data.teams} after round ${data.round}`, p.right, y + crestD / 2 + rankSize * 0.32 + 16, { weight: 500, size: 28, color: c.muted, align: 'right', baseline: 'top' });
      }
      p.lines(fitted, p.left, y + crestD + 32, { weight: 800, family: DISPLAY, stretch: 'condensed', lineHeight: 0.95 });
    } });
    const tileH = story ? 176 : 152;
    blocks.push({ h: tileH, draw: (y) => {
      const gap = 24;
      const w = (p.width - gap * 2) / 3;
      const values = [['Points', String(data.points)], ['Goals', `${data.goals}:${data.goalsAgainst}`], ['Goal diff', signed(data.goals - data.goalsAgainst)]];
      values.forEach(([label, value], i) => p.tile(p.left + i * (w + gap), y, w, tileH, label, value, story ? 72 : 60));
    } });
    if (data.form.length) {
      const formH = story ? 112 : 88;
      blocks.push({ h: 34 + 20 + formH, draw: (y) => {
        p.label(data.form.length === 5 ? 'Last five games' : `Last ${data.form.length} games`, p.left, y);
        formTiles(p, data.form, y + 54, formH, story ? 48 : 40);
      } });
    }
    if (data.next) {
      const panelH = story ? 208 : 176;
      blocks.push({ h: panelH, draw: (y) => {
        p.rect(p.left, y, p.width, panelH, 24, null, c.line);
        p.label('Next game', p.left + 32, y + 32, c.ballInk);
        p.text(`${data.next.date}${data.next.time ? ' · ' + data.next.time : ''}`, p.right - 32, y + 32, { weight: 600, size: 28, family: DISPLAY, color: c.muted, align: 'right', baseline: 'top' });
        const d = story ? 80 : 64;
        const rowMid = y + panelH - 32 - d / 2;
        p.crest(p.left + 32 + d / 2, rowMid, d, data.next.crest, data.next.initials);
        p.text(data.next.home ? 'Home against' : 'Away at', p.left + 32 + d + 20, rowMid - 22, { weight: 500, size: 26, color: c.muted });
        const opponent = p.fit(data.next.opponent, p.width - 64 - d - 20, story ? 44 : 38, 28, 700, DISPLAY, 'semi-condensed', 1);
        p.text(opponent.lines[0], p.left + 32 + d + 20, rowMid + 20, { weight: 700, size: opponent.size, family: DISPLAY, stretch: 'semi-condensed' });
      } });
    }
    return { header: { chip: `${data.league} · ${data.season}` }, blocks, footer: 'Table, form and calendar' };
  }

  function playerCard(p, data, format) {
    const { c } = p;
    const story = format === 'story';
    const fitted = p.fit(data.name, p.width, story ? 168 : 120, 64, 800, DISPLAY, 'condensed', 2);
    const nameH = fitted.lines.length * Math.round(fitted.size * 0.92);
    const blocks = [];
    blocks.push({ h: 56 + 24 + nameH, draw: (y) => {
      p.crest(p.left + 28, y + 28, 56, data.crest, data.initials);
      p.text(`${data.team} · Season ${data.season}`, p.left + 56 + 16, y + 28, { weight: 600, size: 30, color: c.muted });
      p.lines(fitted, p.left, y + 56 + 24, { weight: 800, family: DISPLAY, stretch: 'condensed', lineHeight: 0.92 });
    } });
    // The points figure gets as large as it can while leaving the stat list at least 400px.
    let bigSize = story ? 360 : 260;
    while (bigSize > 160 && p.measure(String(data.points), 800, bigSize, DISPLAY, 'semi-expanded') > p.width - 56 - 400) bigSize -= 10;
    const bigWidth = p.measure(String(data.points), 800, bigSize, DISPLAY, 'semi-expanded');
    const ppg = data.games ? (data.points / data.games).toFixed(2) : '0.00';
    const rows = [['Goals', data.goals], ['Assists', data.assists], ['Games', data.games], ['Points per game', ppg]];
    const rowH = story ? 84 : 62;
    const statsH = Math.max(bigSize * 0.8 + 12 + 34, rows.length * rowH);
    blocks.push({ h: statsH, draw: (y) => {
      const bottom = y + statsH;
      p.text(String(data.points), p.left, bottom - 46, { weight: 800, size: bigSize, family: DISPLAY, stretch: 'semi-expanded', color: c.rink, baseline: 'alphabetic' });
      p.label('Points', p.left, bottom - 34);
      const listX = p.left + Math.max(bigWidth, 200) + 56;
      const listW = p.right - listX;
      rows.forEach(([label, value], i) => {
        const rowTop = bottom - (rows.length - i) * rowH;
        p.text(label, listX, rowTop + rowH / 2, { weight: 600, size: story ? 38 : 32, color: c.muted });
        p.text(value, p.right, rowTop + rowH / 2, { weight: 700, size: story ? 38 : 32, family: DISPLAY, align: 'right' });
        if (i < rows.length - 1) p.hline(rowTop + rowH - 1, listX, listW);
      });
    } });
    if (data.previousGames > 0) {
      blocks.push({ h: 104, draw: (y) => {
        p.rect(p.left, y, p.width, 104, 24, c.raised, c.line);
        p.text('Last season', p.left + 32, y + 52, { weight: 500, size: 28, color: c.muted });
        p.text(`${data.previousPoints} points in ${data.previousGames} games`, p.right - 32, y + 52, { weight: 700, size: 32, family: DISPLAY, align: 'right' });
      } });
    }
    return { header: { chip: `${data.league} · ${data.season}` }, blocks, footer: 'Career, splits and rankings' };
  }

  function tableCard(p, data, format) {
    const { c, f } = p;
    const story = format === 'story';
    const titleSize = story ? 120 : 96;
    const rows = data.rows;
    const titleH = 34 + 12 + Math.round(titleSize * 0.92);
    const headerH = 30 + 12;
    const available = (f.h - f.bottom - 40 - f.gap) - (f.top + 50 + f.gap) - titleH - f.gap - headerH;
    const rowH = Math.max(44, Math.min(story ? 80 : 64, Math.floor(available / Math.max(rows.length, 1))));
    const scale = rowH / 76;
    const cols = { rank: p.left, crest: p.left + 68, team: p.left + 68 + Math.round(52 * scale) + 20, gd: p.right - 100, gp: p.right - 196, pts: p.right };
    const blocks = [];
    blocks.push({ h: titleH, draw: (y) => {
      p.label(`Standings after round ${data.round}`, p.left, y);
      p.text(data.league, p.left, y + 46, { weight: 800, size: titleSize, family: DISPLAY, stretch: 'condensed', baseline: 'top' });
    } });
    blocks.push({ h: headerH + rows.length * rowH, draw: (y) => {
      const head = { weight: 600, size: 22, color: c.muted, baseline: 'top' };
      p.text('#', cols.rank, y, head);
      p.text('TEAM', cols.team, y, head);
      p.text('GP', cols.gp, y, { ...head, align: 'right' });
      p.text('GD', cols.gd, y, { ...head, align: 'right' });
      p.text('PTS', cols.pts, y, { ...head, align: 'right' });
      let rowY = y + headerH;
      const numSize = Math.round(30 * Math.min(scale, 1.05));
      rows.forEach((row) => {
        p.hline(rowY);
        const mid = rowY + rowH / 2 + 1;
        p.text(row.rank, cols.rank, mid, { weight: 700, size: numSize, family: DISPLAY, color: c.muted });
        p.crest(cols.crest + Math.round(26 * scale), mid, Math.round(52 * scale), row.crest, row.initials);
        const name = p.fit(row.team, cols.gp - 72 - cols.team, Math.round(32 * Math.min(scale, 1.05)), 20, 600, BODY, 'normal', 1);
        p.text(name.lines[0], cols.team, mid, { weight: 600, size: name.size });
        p.text(row.games, cols.gp, mid, { weight: 600, size: numSize, family: DISPLAY, color: c.muted, align: 'right' });
        p.text(signed(row.gd), cols.gd, mid, { weight: 600, size: numSize, family: DISPLAY, color: c.muted, align: 'right' });
        p.text(row.points, cols.pts, mid, { weight: 800, size: Math.round(38 * Math.min(scale, 1.05)), family: DISPLAY, align: 'right' });
        rowY += rowH;
      });
    } });
    return { header: { chip: `${data.country} · ${data.season}` }, blocks, footer: 'Full table and form' };
  }

  const CARDS = { game: gameCard, team: teamCard, player: playerCard, table: tableCard };

  function render(data, format, theme) {
    const canvas = document.createElement('canvas');
    const p = painter(canvas, FORMATS[format], palette(theme));
    const card = CARDS[data.kind](p, data, format);
    compose(p, card.header, card.blocks, card.footer);
    return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
  }

  /* ---------- Studio dialog ---------- */

  function readData(trigger) {
    const data = JSON.parse(document.getElementById(trigger.dataset.shareSource).textContent);
    if (trigger.dataset.shareRows) {
      data.rows = JSON.parse(document.getElementById(trigger.dataset.shareRows).textContent);
    }
    data.kind = data.kind || 'game';
    return data;
  }

  function segmented(name, options, value) {
    return `<div class="fs-segmented" role="group" aria-label="${name}">${options.map(([key, label]) =>
      `<button type="button" class="fs-segment" data-option="${key}" aria-pressed="${key === value}">${label}</button>`).join('')}</div>`;
  }

  function openStudio(data) {
    const state = {
      format: 'story',
      theme: document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark',
      blob: null,
      url: null,
    };
    const dialog = document.createElement('div');
    dialog.className = 'share-dialog';
    dialog.innerHTML = `
      <div class="share-dialog__backdrop" data-share-close></div>
      <div class="share-dialog__panel" role="dialog" aria-modal="true" aria-label="Share card">
        <div class="share-dialog__controls">
          <div data-share-format>${segmented('Format', [['story', 'Story'], ['post', 'Post']], state.format)}</div>
          <div data-share-theme>${segmented('Theme', [['dark', 'Dark'], ['light', 'Light']], state.theme)}</div>
        </div>
        <img class="share-dialog__image" alt="">
        <div class="share-dialog__actions"></div>
        <p class="share-dialog__hint"></p>
      </div>`;
    const img = dialog.querySelector('img');
    const actions = dialog.querySelector('.share-dialog__actions');
    const hint = dialog.querySelector('.share-dialog__hint');
    const fileName = () => `floorball-stats-${data.slug}-${state.format}-${state.theme}.png`;

    const close = () => {
      dialog.remove();
      if (state.url) URL.revokeObjectURL(state.url);
      document.removeEventListener('keydown', onKey);
    };
    const onKey = (event) => { if (event.key === 'Escape') close(); };

    let paintId = 0;
    const paint = async () => {
      const id = ++paintId;
      dialog.classList.add('is-busy');
      const blob = await render(data, state.format, state.theme);
      // A newer switch started meanwhile: its result wins.
      if (id !== paintId) return;
      if (state.url) URL.revokeObjectURL(state.url);
      state.blob = blob;
      state.url = URL.createObjectURL(blob);
      img.src = state.url;
      img.alt = `${FORMATS[state.format].label} card, ${state.theme} theme`;
      img.dataset.format = state.format;
      const file = new File([blob], fileName(), { type: 'image/png' });
      const canShare = Boolean(navigator.canShare && navigator.canShare({ files: [file] }));
      actions.innerHTML = `${canShare ? '<button type="button" class="fs-btn fs-btn--primary" data-share-send>Share</button>' : ''}
        <a class="fs-btn${canShare ? '' : ' fs-btn--primary'}" data-share-download href="${state.url}" download="${escapeHtml(fileName())}">Download</a>
        <button type="button" class="fs-btn fs-btn--ghost" data-share-close>Close</button>`;
      hint.textContent = canShare
        ? (state.format === 'story' ? 'Pick Instagram, then add a link sticker to this page.' : 'Pick Instagram and post it to your feed.')
        : 'Save the image and post it on Instagram.';
      actions.querySelector('[data-share-close]').addEventListener('click', close);
      actions.querySelector('[data-share-download]').addEventListener('click', () => track('share_card_downloaded', { kind: data.kind, format: state.format, theme: state.theme }));
      const send = actions.querySelector('[data-share-send]');
      if (send) {
        send.addEventListener('click', async () => {
          try {
            await navigator.share({ files: [file] });
            track('share_card_shared', { kind: data.kind, format: state.format, theme: state.theme });
          } catch (error) {
            if (error && error.name !== 'AbortError') track('share_card_failed', { kind: data.kind, reason: error.name || 'error' });
          }
        });
      }
      dialog.classList.remove('is-busy');
    };

    const bindGroup = (selector, key) => {
      dialog.querySelectorAll(`${selector} [data-option]`).forEach((button) => {
        button.addEventListener('click', () => {
          if (state[key] === button.dataset.option) return;
          state[key] = button.dataset.option;
          dialog.querySelectorAll(`${selector} [data-option]`).forEach((other) => other.setAttribute('aria-pressed', String(other === button)));
          paint();
        });
      });
    };
    bindGroup('[data-share-format]', 'format');
    bindGroup('[data-share-theme]', 'theme');
    dialog.querySelector('.share-dialog__backdrop').addEventListener('click', close);
    document.addEventListener('keydown', onKey);
    document.body.appendChild(dialog);
    return paint();
  }

  document.querySelectorAll('[data-share-card]').forEach((trigger) => {
    trigger.addEventListener('click', async () => {
      const label = trigger.textContent;
      trigger.disabled = true;
      trigger.textContent = 'Preparing…';
      try {
        const data = readData(trigger);
        await loadFonts();
        await openStudio(data);
        track('share_card_opened', { kind: data.kind, path: location.pathname });
      } finally {
        trigger.disabled = false;
        trigger.textContent = label;
      }
    });
  });

  // For local checks: window.fsShareCard.render(data, 'story' | 'post', 'dark' | 'light') -> Promise<Blob>.
  window.fsShareCard = { render: (data, format, theme) => loadFonts().then(() => render(data, format, theme)) };
})();
