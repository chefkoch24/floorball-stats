/* Share cards drawn in the browser: a 1080x1920 Instagram story of a game result.
   Nothing is generated at build time; the card is painted on a canvas when someone
   taps Share, then handed to the phone's share sheet (or downloaded on desktop).
   Layout follows the "Game result · Story" artboard of the share-card designs. */
(function () {
  'use strict';

  const W = 1080;
  const H = 1920;
  const SIDE = 96;
  const TOP = 160;
  const BOTTOM = 240;
  const DISPLAY = 'Archivo, "Arial Narrow", system-ui, sans-serif';
  const BODY = '"Instrument Sans", system-ui, -apple-system, "Segoe UI", sans-serif';

  function track(eventName, payload) {
    if (window.posthog && typeof window.posthog.capture === 'function') {
      window.posthog.capture(eventName, payload);
    }
  }

  // Dark-theme token values, read from the stylesheet so the card follows the design system.
  function palette() {
    const probe = document.createElement('div');
    probe.setAttribute('data-theme', 'dark');
    probe.hidden = true;
    document.body.appendChild(probe);
    const style = getComputedStyle(probe);
    const read = (name) => style.getPropertyValue('--' + name).trim();
    const colors = {
      surface: read('surface'),
      raised: read('surface-raised'),
      sunken: read('surface-sunken'),
      line: read('line'),
      lineStrong: read('line-strong'),
      ink: read('ink'),
      muted: read('ink-muted'),
      rink: read('rink'),
      crest: [1, 2, 3, 4, 5, 6, 7, 8].map((n) => read('crest-' + n)),
      onCrest: read('on-crest'),
    };
    probe.remove();
    return colors;
  }

  function loadFonts() {
    const faces = [
      '800 100px Archivo',
      'condensed 800 100px Archivo',
      'semi-expanded 800 100px Archivo',
      '700 40px Archivo',
      '600 40px Archivo',
      '600 40px "Instrument Sans"',
      '500 40px "Instrument Sans"',
      '700 40px "Instrument Sans"',
    ];
    return Promise.all(faces.map((face) => document.fonts.load(face).catch(() => null)));
  }

  function setFont(ctx, weight, size, family, stretch) {
    ctx.font = `${weight} ${size}px ${family}`;
    if ('fontStretch' in ctx) {
      ctx.fontStretch = stretch || 'normal';
    }
  }

  // Largest size (down to min) at which the text fits in up to `maxLines` lines of maxWidth.
  function fitLines(ctx, text, maxWidth, size, minSize, weight, family, stretch, maxLines) {
    for (let s = size; s >= minSize; s -= 2) {
      setFont(ctx, weight, s, family, stretch);
      const lines = wrap(ctx, text, maxWidth);
      if (lines.length <= maxLines && lines.every((line) => ctx.measureText(line).width <= maxWidth)) {
        return { size: s, lines };
      }
    }
    setFont(ctx, weight, minSize, family, stretch);
    return { size: minSize, lines: wrap(ctx, text, maxWidth).slice(0, maxLines) };
  }

  function wrap(ctx, text, maxWidth) {
    const lines = [];
    String(text).split(/\s+/).filter(Boolean).forEach((word) => {
      const last = lines[lines.length - 1];
      if (last && ctx.measureText(last + ' ' + word).width <= maxWidth) {
        lines[lines.length - 1] = last + ' ' + word;
      } else {
        lines.push(word);
      }
    });
    return lines;
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function pill(ctx, text, x, y, opts) {
    setFont(ctx, opts.weight, opts.size, opts.family, opts.stretch);
    const w = ctx.measureText(text).width + opts.padX * 2;
    const h = opts.size * 1.3 + opts.padY * 2;
    const left = opts.align === 'right' ? x - w : x;
    roundRect(ctx, left, y, w, h, opts.radius);
    if (opts.fill) {
      ctx.fillStyle = opts.fill;
      ctx.fill();
    }
    if (opts.stroke) {
      ctx.lineWidth = 2;
      ctx.strokeStyle = opts.stroke;
      ctx.stroke();
    }
    ctx.fillStyle = opts.color;
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    ctx.fillText(text, left + opts.padX, y + h / 2);
    return { w, h };
  }

  function crest(ctx, colors, cx, cy, d, index, initials) {
    ctx.beginPath();
    ctx.arc(cx, cy, d / 2, 0, Math.PI * 2);
    ctx.fillStyle = colors.crest[(Number(index) || 8) - 1];
    ctx.fill();
    setFont(ctx, 800, Math.round(d / 3), DISPLAY, 'semi-condensed');
    ctx.fillStyle = colors.onCrest;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(initials, cx, cy + 2);
  }

  function topScorers(eventsB64) {
    if (!eventsB64) return [];
    let events = [];
    try {
      const bytes = Uint8Array.from(atob(eventsB64), (c) => c.charCodeAt(0));
      events = JSON.parse(new TextDecoder().decode(bytes));
    } catch (error) {
      return [];
    }
    const players = new Map();
    const credit = (name, key) => {
      const clean = String(name || '').trim();
      if (!clean) return;
      const entry = players.get(clean) || { name: clean, goals: 0, assists: 0 };
      entry[key] += 1;
      players.set(clean, entry);
    };
    events.filter((event) => event.event_kind === 'goal').forEach((event) => {
      credit(event.title, 'goals');
      String(event.assist || '').split('/').forEach((name) => credit(name, 'assists'));
    });
    return Array.from(players.values())
      .sort((a, b) => (b.goals + b.assists) - (a.goals + a.assists) || b.goals - a.goals)
      .slice(0, 3);
  }

  function drawGameStory(canvas, data, colors) {
    const ctx = canvas.getContext('2d');
    canvas.width = W;
    canvas.height = H;
    ctx.fillStyle = colors.surface;
    ctx.fillRect(0, 0, W, H);
    const right = W - SIDE;
    const width = W - SIDE * 2;

    // Header: brand and league chip.
    setFont(ctx, 800, 44, DISPLAY, 'condensed');
    ctx.fillStyle = colors.rink;
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    ctx.fillText('Floorball Stats', SIDE, TOP + 26);
    pill(ctx, data.league, right, TOP, { weight: 600, size: 26, family: BODY, padX: 22, padY: 10, radius: 30, stroke: colors.line, color: colors.muted, align: 'right' });
    let y = TOP + 52 + 72;

    // Status and date.
    const status = pill(ctx, data.status.toUpperCase(), SIDE, y, { weight: 700, size: 26, family: BODY, padX: 20, padY: 8, radius: 30, fill: colors.sunken, color: colors.ink });
    setFont(ctx, 500, 30, BODY);
    ctx.fillStyle = colors.muted;
    ctx.fillText(data.date, SIDE + status.w + 20, y + status.h / 2);
    y += status.h + 32;

    // Teams with scores; the losing side is muted.
    const crestD = 144;
    const scoreW = 240;
    const nameX = SIDE + crestD + 32;
    const nameW = right - scoreW - 32 - nameX;
    const sides = [
      { name: data.home, goals: data.homeGoals, crest: data.homeCrest, initials: data.homeInitials, lost: data.homeGoals < data.awayGoals },
      { name: data.away, goals: data.awayGoals, crest: data.awayCrest, initials: data.awayInitials, lost: data.awayGoals < data.homeGoals },
    ];
    sides.forEach((side, index) => {
      const rowH = 176;
      const mid = y + rowH / 2;
      crest(ctx, colors, SIDE + crestD / 2, mid, crestD, side.crest, side.initials);
      const fitted = fitLines(ctx, side.name, nameW, 64, 40, 800, DISPLAY, 'condensed', 2);
      ctx.fillStyle = side.lost ? colors.muted : colors.ink;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      const lineH = fitted.size * 1.04;
      fitted.lines.forEach((line, i) => {
        ctx.fillText(line, nameX, mid + (i - (fitted.lines.length - 1) / 2) * lineH);
      });
      setFont(ctx, 800, 200, DISPLAY, 'semi-expanded');
      ctx.textAlign = 'right';
      ctx.textBaseline = 'alphabetic';
      ctx.fillText(String(side.goals), right, mid + 72);
      y += rowH;
      if (index === 0) {
        y += 12;
        ctx.fillStyle = colors.line;
        ctx.fillRect(SIDE, y, width, 2);
        y += 14;
      }
    });
    y += 32;

    // Period results.
    let x = SIDE;
    data.periods.forEach((period) => {
      const chip = pill(ctx, period, x, y, { weight: 600, size: 30, family: DISPLAY, padX: 22, padY: 10, radius: 16, fill: colors.raised, color: colors.muted });
      x += chip.w + 16;
    });
    y += 60 + 72;

    // Goals over 60 minutes: home above the line, away below, in crest colours.
    setFont(ctx, 600, 26, BODY);
    ctx.fillStyle = colors.muted;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText('GOALS OVER 60 MINUTES', SIDE, y);
    y += 34 + 24;
    const axisY = y + 56;
    ctx.fillStyle = colors.lineStrong;
    ctx.fillRect(SIDE, axisY, width, 2);
    ctx.fillStyle = colors.line;
    [1, 2].forEach((p) => ctx.fillRect(SIDE + width * p / 3, axisY - 40, 2, 80));
    const dot = (minute, above, crestIndex) => {
      const px = SIDE + width * Math.min(Math.max(minute, 0), 60) / 60;
      ctx.beginPath();
      ctx.arc(px, above ? axisY - 30 : axisY + 32, 11, 0, Math.PI * 2);
      ctx.fillStyle = colors.crest[(Number(crestIndex) || 8) - 1];
      ctx.fill();
    };
    data.homeMinutes.forEach((m) => dot(m, true, data.homeCrest));
    data.awayMinutes.forEach((m) => dot(m, false, data.awayCrest));
    y = axisY + 72;
    setFont(ctx, 500, 24, DISPLAY);
    ctx.fillStyle = colors.muted;
    ctx.textBaseline = 'top';
    ["0'", "20'", "40'", "60'"].forEach((label, i) => {
      ctx.textAlign = i === 0 ? 'left' : i === 3 ? 'right' : 'center';
      ctx.fillText(label, SIDE + width * i / 3, y);
    });
    y += 24 + 72;

    // Top scorers of the game.
    if (data.scorers.length) {
      setFont(ctx, 600, 26, BODY);
      ctx.textAlign = 'left';
      ctx.fillText('TOP SCORERS', SIDE, y);
      y += 34 + 20;
      data.scorers.forEach((player) => {
        ctx.fillStyle = colors.line;
        ctx.fillRect(SIDE, y, width, 2);
        setFont(ctx, 600, 36, BODY);
        ctx.fillStyle = colors.ink;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText(player.name, SIDE, y + 38);
        setFont(ctx, 700, 36, DISPLAY);
        ctx.textAlign = 'right';
        ctx.fillText(`${player.goals} G · ${player.assists} A`, right, y + 38);
        y += 76;
      });
      ctx.fillStyle = colors.line;
      ctx.fillRect(SIDE, y, width, 2);
    }

    // Footer.
    const footerY = H - BOTTOM - 20;
    setFont(ctx, 500, 28, BODY);
    ctx.fillStyle = colors.muted;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText('Full stats and timeline', SIDE, footerY);
    setFont(ctx, 700, 30, DISPLAY);
    ctx.fillStyle = colors.rink;
    ctx.textAlign = 'right';
    ctx.fillText('stats.floorballconnect.com', right, footerY);
  }

  function readData(trigger) {
    const source = document.getElementById(trigger.dataset.shareSource);
    const data = JSON.parse(source.textContent);
    const timeline = document.getElementById('gameEventsTimeline');
    data.scorers = topScorers(timeline ? timeline.dataset.eventsB64 : '');
    return data;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  }

  function openDialog(blob, data) {
    const url = URL.createObjectURL(blob);
    const fileName = `floorball-stats-${data.slug}-story.png`;
    const file = new File([blob], fileName, { type: 'image/png' });
    const canShareFile = Boolean(navigator.canShare && navigator.canShare({ files: [file] }));

    const dialog = document.createElement('div');
    dialog.className = 'share-dialog';
    dialog.innerHTML = `
      <div class="share-dialog__backdrop" data-share-close></div>
      <div class="share-dialog__panel" role="dialog" aria-modal="true" aria-label="Share story">
        <img class="share-dialog__image" alt="Story card: ${escapeHtml(data.home)} ${data.homeGoals}:${data.awayGoals} ${escapeHtml(data.away)}">
        <div class="share-dialog__actions">
          ${canShareFile ? '<button type="button" class="fs-btn fs-btn--primary" data-share-send>Share</button>' : ''}
          <a class="fs-btn${canShareFile ? '' : ' fs-btn--primary'}" data-share-download>Download</a>
          <button type="button" class="fs-btn fs-btn--ghost" data-share-close>Close</button>
        </div>
        <p class="share-dialog__hint">${canShareFile ? 'Pick Instagram in the share menu, then add a link sticker to this page.' : 'Save the image and post it as a story.'}</p>
      </div>`;
    dialog.querySelector('img').src = url;
    const download = dialog.querySelector('[data-share-download]');
    download.href = url;
    download.download = fileName;
    download.addEventListener('click', () => track('share_card_downloaded', { kind: 'game_story', path: location.pathname }));

    const close = () => {
      dialog.remove();
      URL.revokeObjectURL(url);
      document.removeEventListener('keydown', onKey);
    };
    const onKey = (event) => { if (event.key === 'Escape') close(); };
    document.addEventListener('keydown', onKey);
    dialog.querySelectorAll('[data-share-close]').forEach((el) => el.addEventListener('click', close));

    const send = dialog.querySelector('[data-share-send]');
    if (send) {
      send.addEventListener('click', async () => {
        try {
          await navigator.share({ files: [file], title: `${data.home} ${data.homeGoals}:${data.awayGoals} ${data.away}` });
          track('share_card_shared', { kind: 'game_story', path: location.pathname });
        } catch (error) {
          if (error && error.name !== 'AbortError') {
            track('share_card_failed', { kind: 'game_story', reason: error.name || 'error' });
          }
        }
      });
    }
    document.body.appendChild(dialog);
    (send || download).focus();
  }

  document.querySelectorAll('[data-share-card]').forEach((trigger) => {
    trigger.addEventListener('click', async () => {
      const label = trigger.textContent;
      trigger.disabled = true;
      trigger.textContent = 'Preparing…';
      try {
        const data = readData(trigger);
        await loadFonts();
        const canvas = document.createElement('canvas');
        drawGameStory(canvas, data, palette());
        const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
        track('share_card_opened', { kind: 'game_story', path: location.pathname });
        openDialog(blob, data);
      } finally {
        trigger.disabled = false;
        trigger.textContent = label;
      }
    });
  });
})();
