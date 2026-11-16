// Drill diagrams: plays a drill drawn from data (connect/drill_diagram.py) step by step.
// Without this script the SVG shows the whole drill at once, with numbered arrows.
(() => {
  const root = document.querySelector('[data-drill-diagram]');
  if (!root) return;
  const svg = root.querySelector('svg');
  const dataNode = root.querySelector('[data-dd="data"]');
  if (!svg || !dataNode) return;
  let data;
  try { data = JSON.parse(dataNode.textContent); } catch (error) { return; }
  const steps = data.steps || [];
  if (!steps.length) return;

  const controls = root.querySelector('.dd__controls');
  const playButton = root.querySelector('[data-dd="play"]');
  const caption = root.querySelector('[data-dd="caption"]');
  const count = root.querySelector('[data-dd="count"]');
  const entities = new Map([...svg.querySelectorAll('[data-entity]')].map((node) => [node.dataset.entity, node]));
  const stepNodes = [...svg.querySelectorAll('[data-step]')];
  const overviewNote = caption.textContent;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  // SVG units (decimetres) per second: a floorball player runs about 7 m/s, with the ball a bit slower.
  const SPEED = { run: 72, dribble: 58, react: 30, pass: 190, shot: 300, pickup: 120 };
  const PAUSE = 380; // between steps

  let current = -1; // -1: overview with every arrow
  let finished = true; // whether the current step ran to its end
  let playing = false;
  let token = 0;

  const place = (id, point) => {
    const node = entities.get(id);
    if (node && point) node.setAttribute('transform', `translate(${point[0].toFixed(1)} ${point[1].toFixed(1)})`);
  };
  const placeAll = (positions) => Object.entries(positions).forEach(([id, point]) => place(id, point));
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const mark = (index) => {
    root.classList.toggle('dd--playing', index >= 0);
    stepNodes.forEach((node) => {
      const step = Number(node.dataset.step);
      node.classList.toggle('is-current', step === index);
      node.classList.toggle('is-past', index >= 0 && step < index);
      node.classList.toggle('is-future', index >= 0 && step > index);
    });
    if (index < 0) {
      caption.textContent = overviewNote;
      count.textContent = '';
    } else {
      caption.textContent = steps[index].text || '';
      count.textContent = `${data.intro ? 'Example run · ' : ''}Step ${index + 1} / ${steps.length}`;
    }
  };

  // Players pick up speed and slow down softly but never stand still in the middle of a run (a pure
  // sine ease looks like a machine); a pass or shot leaves the stick fast and only eases a little.
  const playerEase = (t) => 0.3 * t + 0.7 * (t * t * (3 - 2 * t));
  const ballEase = (t) => 1 - Math.pow(1 - t, 1.6);

  // The timing of one stage of a step. A carried ball ("with") shares its player's timing, so it
  // never runs on alone; a pass into a run ("into") is released late enough to arrive when the run
  // ends. Used by the player on the page and by the video export.
  const planStage = (moves, instant) => {
    const plan = moves.map((move) => {
      const path = svg.getElementById(move.path);
      if (!path) return null;
      const length = path.getTotalLength();
      const ball = Boolean(move.ball);
      const speed = SPEED[move.kind] || (ball ? SPEED.pass : SPEED.run);
      const natural = Math.max(ball ? 260 : 450, (length / speed) * 1000);
      return { move, path, length, duration: instant ? 0 : natural, delay: 0, ease: ball ? ballEase : playerEase };
    }).filter(Boolean);
    const leaders = new Map(plan.filter((p) => !p.move.ball && !p.move.with && p.move.kind !== 'react').map((p) => [p.move.e, p]));
    plan.forEach((p) => {
      const carrier = p.move.with && leaders.get(p.move.with);
      if (carrier) { p.duration = carrier.duration; p.ease = carrier.ease; }
      const runner = p.move.into && leaders.get(p.move.into);
      if (runner) p.delay = Math.max(0, runner.duration - p.duration);
      // A goalie leans as long as the shot flies.
      if (p.move.kind === 'react') {
        const shot = plan.find((other) => other.move.kind === 'shot');
        p.duration = shot ? Math.max(shot.duration, 300) : p.duration;
        p.ease = (t) => 1 - Math.pow(1 - t, 2);
      }
    });
    return { plan, total: Math.max(0, ...plan.map((p) => p.delay + p.duration)) };
  };
  // Where a move is after `elapsed` ms of its stage; null while it waits for its release.
  const pointAt = (p, elapsed) => {
    if (elapsed < p.delay) return null;
    const t = p.duration ? Math.min(1, (elapsed - p.delay) / p.duration) : 1;
    const point = p.path.getPointAtLength(p.length * p.ease(t));
    return [point.x, point.y];
  };

  const animate = (moves, run) => new Promise((resolve) => {
    const { plan, total } = planStage(moves, reduced);
    const finish = () => plan.forEach((p) => place(p.move.e, pointAt(p, Infinity)));
    if (!total) { finish(); resolve(); return; }
    const start = performance.now();
    const frame = (now) => {
      if (run !== token) { resolve(); return; }
      const elapsed = now - start;
      plan.forEach((p) => { const point = pointAt(p, elapsed); if (point) place(p.move.e, point); });
      if (elapsed < total) requestAnimationFrame(frame); else { finish(); resolve(); }
    };
    requestAnimationFrame(frame);
  });

  const playStep = async (index, run) => {
    current = index;
    finished = false;
    placeAll(steps[index].start);
    mark(index);
    for (const stage of steps[index].stages) {
      if (run !== token) return false;
      await animate(stage, run);
    }
    if (run !== token) return false;
    finished = true;
    return true;
  };

  const setPlaying = (value) => {
    playing = value;
    playButton.textContent = value ? 'Pause' : (current >= steps.length - 1 && finished ? 'Replay' : 'Play');
    playButton.setAttribute('aria-pressed', value ? 'true' : 'false');
  };

  const play = async (from) => {
    const run = ++token;
    setPlaying(true);
    for (let index = from; index < steps.length; index += 1) {
      if (!(await playStep(index, run))) return;
      if (index < steps.length - 1) await wait(reduced ? 300 : PAUSE);
      if (run !== token) return;
    }
    setPlaying(false);
  };

  const single = async (index) => {
    const run = ++token;
    current = index;
    setPlaying(false);
    await playStep(index, run);
    if (run === token) setPlaying(false);
  };

  controls.hidden = false;
  root.classList.add('dd--ready');
  playButton.addEventListener('click', () => {
    if (playing) { token += 1; setPlaying(false); return; }
    // From the start, again from the start after the last step, or on from a paused step.
    let from = current < 0 ? 0 : (finished ? current + 1 : current);
    if (from >= steps.length) from = 0;
    play(from);
  });
  root.querySelector('[data-dd="next"]').addEventListener('click', () => single(Math.min(steps.length - 1, current + 1)));
  root.querySelector('[data-dd="prev"]').addEventListener('click', () => {
    if (current <= 0) { token += 1; current = -1; finished = true; placeAll(data.initial); mark(-1); setPlaying(false); return; }
    single(current - 1);
  });

  // ---- Sharing: Instagram-ready image and video of the drill ----------------------------------
  // Drawn in the browser in the formats and look of the share studio on the stats site:
  // Story/Reel 1080x1920 or Post 1080x1350, light or dark theme. On a phone, Share hands the file
  // to the share sheet (Instagram and co.), elsewhere it is downloaded.
  const studio = root.querySelector('[data-dd-share]');
  const title = ((document.querySelector('h1') || {}).textContent || 'Floorball drill').trim();
  const slug = location.pathname.split('/').filter(Boolean).pop() || 'drill';
  const k = parseFloat(svg.style.getPropertyValue('--dd-k')) || 1;
  const DISPLAY = 'Archivo, "Arial Narrow", system-ui, sans-serif';
  const BODY = '"Instrument Sans", system-ui, -apple-system, "Segoe UI", sans-serif';
  const W = 1080;
  const SIDE = 72;
  // top/bottom keep the content out of the zones Instagram covers with its own buttons.
  const FORMATS = {
    story: { h: 1920, top: 230, bottom: 330, footer: 210, titleSize: 92, textSize: 40, label: 'Reel / Story' },
    post: { h: 1350, top: 84, bottom: 84, footer: 84, titleSize: 72, textSize: 36, label: 'Post' },
  };
  const FPS = 30;
  const analytics = window.fbTrack || { ctaCompleted() {}, ctaFailed() {} };

  // Token values of one theme, read from the stylesheet so the cards follow the design system.
  const palette = (theme) => {
    const probe = document.createElement('div');
    probe.setAttribute('data-theme', theme);
    probe.hidden = true;
    document.body.appendChild(probe);
    const style = getComputedStyle(probe);
    const read = (name) => style.getPropertyValue('--' + name).trim();
    const colors = { surface: read('surface'), raised: read('surface-raised'), sunken: read('surface-sunken'), line: read('line'),
      ink: read('ink'), muted: read('ink-muted'), rink: read('rink'), rinkSoft: read('rink-soft'), ball: read('ball'), ballInk: read('ball-ink') };
    probe.remove();
    return colors;
  };

  // An SVG shown as an image sees no page CSS, so the copy carries its colours.
  const exportCss = (c) => `
    .dd-floor{fill:${c.rinkSoft}}.dd-board{fill:none;stroke:${c.rink};stroke-width:2.2}
    .dd-line{fill:none;stroke:${c.rink};stroke-width:1;opacity:.55}.dd-spot{fill:${c.rink};opacity:.55}
    .dd-goal{fill:${c.raised};stroke:${c.ink};stroke-width:1.2}.dd-motion{fill:none;stroke:none}
    .dd-arrow{fill:none;stroke:${c.ink};stroke-width:${1.6 * k};stroke-linecap:round;stroke-linejoin:round}
    .dd-arrow--run{stroke-dasharray:${4 * k} ${3.2 * k}}.dd-arrow--shot{stroke:${c.ballInk};stroke-width:${2.6 * k}}
    .dd-head path{fill:${c.ink}}.dd-head--shot path{fill:${c.ballInk}}
    .dd-player circle{stroke:${c.raised};stroke-width:1.2}
    .dd-player text{font:700 8.4px/1 Arial,Helvetica,sans-serif;text-anchor:middle;fill:#fff}
    .dd-player--red circle{fill:#d93a32}.dd-player--blue circle{fill:#2f5fd0}
    .dd-player--goalie circle{fill:#f2b705}.dd-player--goalie text{fill:#1d1d1d}
    .dd-player--coach circle{fill:${c.ink}}.dd-player--coach text{fill:${c.surface}}.dd-player--joker circle{fill:#1f9d55}
    .dd-ball circle{fill:#fff;stroke:#1d1d1d;stroke-width:${0.8 * k}}
    .dd-cone{fill:${c.ball};stroke:${c.ballInk};stroke-width:.6}
    .dd-step-label circle{fill:${c.raised};stroke:${c.ink};stroke-width:.7}
    .dd-step-label text{font:700 6.4px/1 Arial,Helvetica,sans-serif;text-anchor:middle;fill:${c.ink}}
    svg:not(.x-playing) .is-later{opacity:0}.x-playing .is-future{opacity:0}.x-playing .is-past{opacity:.22}.x-playing .dd-step-label.is-past{opacity:0}
    .x-clean .dd-step-label{display:none}`;

  const copy = svg.cloneNode(true);
  const viewBox = svg.viewBox.baseVal;
  copy.setAttribute('width', String(Math.round(viewBox.width * 4)));
  copy.setAttribute('height', String(Math.round(viewBox.height * 4)));
  copy.removeAttribute('style');
  copy.removeAttribute('class');
  const copyStyle = document.createElementNS('http://www.w3.org/2000/svg', 'style');
  copy.insertBefore(copyStyle, copy.firstChild);
  const copyEntities = new Map([...copy.querySelectorAll('[data-entity]')].map((node) => [node.dataset.entity, node]));
  const copySteps = [...copy.querySelectorAll('[data-step]')];

  // ops: opacity per step (the video fades arrows in and out) and no number badges; null: the still
  // picture with every arrow and its step number.
  const drawSvg = (positions, ops) => new Promise((resolve, reject) => {
    Object.entries(positions).forEach(([id, point]) => {
      const node = copyEntities.get(id);
      if (node) node.setAttribute('transform', `translate(${point[0].toFixed(1)} ${point[1].toFixed(1)})`);
    });
    copy.classList.toggle('x-playing', Boolean(ops));
    copy.classList.toggle('x-clean', Boolean(ops));
    copySteps.forEach((node) => {
      const step = Number(node.dataset.step);
      node.setAttribute('class', node.getAttribute('class').replace(/ ?is-(current|past|future)/g, ''));
      if (ops) node.setAttribute('style', `opacity:${(ops[step] || 0).toFixed(3)}`); else node.removeAttribute('style');
    });
    const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(copy)], { type: 'image/svg+xml' }));
    const image = new Image();
    image.onload = () => { URL.revokeObjectURL(url); resolve(image); };
    image.onerror = (error) => { URL.revokeObjectURL(url); reject(error); };
    image.src = url;
  });

  const font = (ctx, weight, size, family, stretch) => {
    ctx.font = `${weight} ${size}px ${family}`;
    if ('fontStretch' in ctx) ctx.fontStretch = stretch || 'normal';
  };
  const wrap = (ctx, text, width) => {
    const lines = [];
    let line = '';
    String(text || '').split(/\s+/).forEach((word) => {
      const next = line ? `${line} ${word}` : word;
      if (ctx.measureText(next).width > width && line) { lines.push(line); line = word; } else { line = next; }
    });
    if (line) lines.push(line);
    return lines;
  };
  // The biggest size from `size` down to `min` at which the text fits in `maxLines` lines.
  const fit = (ctx, text, width, size, min, maxLines, weight, family, stretch) => {
    for (let s = size; s >= min; s -= 2) {
      font(ctx, weight, s, family, stretch);
      const lines = wrap(ctx, text, width);
      if (lines.length <= maxLines) return { size: s, lines };
    }
    font(ctx, weight, min, family, stretch);
    return { size: min, lines: wrap(ctx, text, width).slice(0, maxLines) };
  };
  const roundRect = (ctx, x, y, w, h, r, fill, stroke) => {
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, r);
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 2; ctx.stroke(); }
  };

  // The steps as a numbered list: each step its own block with a number badge.
  const listLayout = (ctx, list, size, width) => {
    font(ctx, 500, size, BODY);
    const lh = Math.round(size * 1.28);
    const items = list.map((entry) => wrap(ctx, entry, width - size * 1.7));
    const height = items.reduce((sum, lines) => sum + lines.length * lh, 0) + (items.length - 1) * Math.round(size * 0.45);
    return { size, lh, items, height };
  };

  // One card: the brand on top, then title, rink and text centred in the space left,
  // the site at the bottom. Everything stays inside the zones Instagram leaves free.
  // card.underImage + card.imageMix: the picture dissolves from one state into another (loop);
  // card.prevText + card.textMix: the caption dissolves; card.dots: progress without numbers.
  const drawCard = (ctx, fmt, c, image, { label, text, list, underImage, imageMix = 1, prevText, textMix = 1, dots }) => {
    const right = W - SIDE;
    const width = right - SIDE;
    ctx.textBaseline = 'alphabetic';
    ctx.textAlign = 'left';
    ctx.fillStyle = c.surface;
    ctx.fillRect(0, 0, W, fmt.h);
    font(ctx, 800, 44, DISPLAY, 'condensed');
    ctx.fillStyle = c.rink;
    ctx.fillText('Floorball Connect', SIDE, fmt.top + 40);
    // The site name may sit lower than the content: Instagram covers the very bottom only partly.
    const footerY = fmt.h - fmt.footer;
    font(ctx, 700, 32, DISPLAY);
    ctx.fillStyle = c.rink;
    ctx.textAlign = 'right';
    ctx.fillText('floorballconnect.com', right, footerY);
    ctx.textAlign = 'left';

    // Measure: title, text, then the rink gets what is left (at most its natural height).
    const areaTop = fmt.top + 100;
    const areaBottom = fmt.h - fmt.bottom - (fmt.footer === fmt.bottom ? 64 : 0);
    const head = fit(ctx, title, width, fmt.titleSize, 44, 2, 800, DISPLAY, 'condensed');
    const headH = Math.round(head.size * 1.02) * head.lines.length;
    const labelH = label || dots ? 48 : 0;
    let body;
    if (list) {
      const room = (areaBottom - areaTop) * (fmt.h > 1500 ? 0.34 : 0.36);
      for (let size = fmt.textSize; size >= 22; size -= 2) {
        body = listLayout(ctx, list, size, width);
        if (body.height <= room) break;
      }
    } else {
      body = fit(ctx, text, width, fmt.textSize, 28, 3, 500, BODY);
      body.lh = Math.round(body.size * 1.3);
      body.height = Math.round(fmt.textSize * 1.3) * 3;  // fixed, so the rink does not jump between steps
    }
    const gaps = 36 + 44;
    const natural = width * (image.height / image.width) + 40;
    const boxH = Math.max(300, Math.min(natural, areaBottom - areaTop - headH - labelH - body.height - gaps));
    const total = headH + 36 + boxH + 44 + labelH + body.height;
    let y = areaTop + Math.max(0, (areaBottom - areaTop - total) / 2);

    font(ctx, 800, head.size, DISPLAY, 'condensed');
    ctx.fillStyle = c.ink;
    head.lines.forEach((line, i) => ctx.fillText(line, SIDE, y + Math.round(head.size * 1.02) * i + head.size * 0.86));
    y += headH + 36;

    roundRect(ctx, SIDE, y, width, boxH, 28, c.sunken, null);
    const scale = Math.min((width - 40) / image.width, (boxH - 40) / image.height);
    const iw = image.width * scale;
    const ih = image.height * scale;
    if (underImage) ctx.drawImage(underImage, SIDE + (width - iw) / 2, y + (boxH - ih) / 2, iw, ih);
    ctx.globalAlpha = underImage ? imageMix : 1;
    ctx.drawImage(image, SIDE + (width - iw) / 2, y + (boxH - ih) / 2, iw, ih);
    ctx.globalAlpha = 1;
    y += boxH + 44;

    if (dots) {
      const r = dots.n > 12 ? 8 : 11;
      const gap = r * 2.7;
      for (let i = 0; i < dots.n; i += 1) {
        ctx.beginPath();
        ctx.arc(SIDE + r + i * gap, y + 14, i === dots.active ? r * 1.25 : r, 0, Math.PI * 2);
        ctx.fillStyle = i <= dots.active ? c.rink : c.line;
        ctx.fill();
      }
      y += labelH;
    }
    if (label) {
      font(ctx, 700, 26, BODY);
      ctx.fillStyle = c.rink;
      ctx.fillText(label.toUpperCase(), SIDE, y + 22);
      y += labelH;
    }
    if (list) {
      const badge = Math.round(body.size * 1.15);
      body.items.forEach((lines, i) => {
        roundRect(ctx, SIDE, y + (body.lh - badge) / 2, badge, badge, badge / 2, c.rink, null);
        font(ctx, 700, Math.round(body.size * 0.66), BODY);
        ctx.fillStyle = c.surface;
        ctx.textAlign = 'center';
        ctx.fillText(String(i + 1), SIDE + badge / 2, y + body.lh / 2 + body.size * 0.24);
        ctx.textAlign = 'left';
        font(ctx, 500, body.size, BODY);
        ctx.fillStyle = c.ink;
        lines.forEach((line, j) => ctx.fillText(line, SIDE + body.size * 1.7, y + j * body.lh + body.size * 0.92));
        y += lines.length * body.lh + Math.round(body.size * 0.45);
      });
    } else {
      ctx.fillStyle = c.ink;
      const caption = (lines, size, lh, alpha) => {
        ctx.globalAlpha = alpha;
        font(ctx, 500, size, BODY);
        lines.forEach((line, i) => ctx.fillText(line, SIDE, y + i * lh + size * 0.92));
        ctx.globalAlpha = 1;
      };
      if (prevText && textMix < 1) {
        const old = fit(ctx, prevText, width, fmt.textSize, 28, 3, 500, BODY);
        caption(old.lines, old.size, Math.round(old.size * 1.3), Math.max(0, 1 - 2 * textMix));
      }
      // One text fades out, then the next fades in; two texts on top of each other are unreadable.
      caption(body.lines, body.size, body.lh, prevText ? Math.max(0, 2 * textMix - 1) : 1);
    }
  };

  const fontsReady = () => Promise.all(['800 60px Archivo', 'condensed 800 60px Archivo', '700 40px Archivo',
    '500 40px "Instrument Sans"', '600 40px "Instrument Sans"', '700 40px "Instrument Sans"']
    .map((face) => document.fonts.load(face).catch(() => null)));

  const makeImage = async (format, theme) => {
    await fontsReady();
    const fmt = FORMATS[format];
    const c = palette(theme);
    copyStyle.textContent = exportCss(c);
    const image = await drawSvg(data.initial, null);
    const canvas = document.createElement('canvas');
    canvas.width = W;
    canvas.height = fmt.h;
    drawCard(canvas.getContext('2d'), fmt, c, image, { label: `${steps.length} steps`, list: steps.map((step) => step.text) });
    return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
  };

  // The video loops: it starts and ends on the same picture (everyone on their starting spot, no
  // arrows, the first step's text), so Instagram's loop shows no cut. No step numbers, no overview
  // and no end card; arrows fade in with their step and fade back, the caption dissolves.
  const PAST = 0.22;
  const LEAD = 700; // first picture, before the first move
  const INTRO = 3200; // the rule of a game, long enough to read it
  const FADE = 300; // arrows and caption of the next step fade in at the end of the pause
  const HOLD = 560; // pause between steps
  const TAIL = 700; // last picture before it dissolves back into the first
  const DISSOLVE = 800;
  const smooth = (t) => { const x = Math.max(0, Math.min(1, t)); return x * x * (3 - 2 * x); };
  // Opacity of every step's arrows `ms` after step `index` began to fade in.
  const opsAt = (index, ms) => steps.map((_, j) => (j < index - 1 ? PAST : j === index - 1 ? 1 - (1 - PAST) * smooth(ms / FADE) : j === index ? smooth(ms / FADE) : 0));
  const timeline = () => {
    const frames = [];
    const slot = 1000 / FPS;
    const still = (positions, ops, step, ms, extra) => { for (let t = 0; t < ms; t += slot) frames.push({ positions, ops, step, ...(extra ? extra(t) : {}) }); };
    if (data.intro) {
      // The rule first (step -1), then the example run fades in on the same picture.
      still(data.initial, opsAt(-1, 0), -1, INTRO);
      still(data.initial, null, 0, FADE, (t) => ({ ops: opsAt(0, t), prev: -1, mix: smooth(t / FADE) }));
      still(data.initial, opsAt(0, Infinity), 0, 300);
    } else {
      still(data.initial, null, 0, LEAD, (t) => ({ ops: opsAt(0, t) }));
    }
    let positions = data.initial;
    steps.forEach((step, index) => {
      positions = { ...step.start };
      const full = opsAt(index, Infinity);
      step.stages.forEach((stage) => {
        const { plan, total } = planStage(stage, false);
        for (let t = 0; t <= total; t += slot) {
          const now = { ...positions };
          plan.forEach((p) => { const point = pointAt(p, t); if (point) now[p.move.e] = point; });
          frames.push({ positions: now, ops: full, step: index });
        }
        positions = { ...positions };
        plan.forEach((p) => { positions[p.move.e] = pointAt(p, Infinity); });
      });
      if (index < steps.length - 1) {
        // The pause: the next step's arrows and caption fade in during its last FADE ms.
        still(positions, full, index, HOLD, (t) => {
          const m = t - (HOLD - FADE);
          return m <= 0 ? {} : { ops: opsAt(index + 1, m), step: index + 1, prev: index, mix: smooth(m / FADE) };
        });
      }
    });
    const last = steps.length - 1;
    const end = { positions, ops: steps.map((_, j) => (j === last ? 1 : PAST)) };
    still(end.positions, end.ops, last, TAIL);
    const first = data.intro ? -1 : 0;
    still(end.positions, end.ops, first, DISSOLVE, (t) => ({ loop: smooth(t / DISSOLVE), prev: last, mix: smooth(t / DISSOLVE) }));
    frames.push({ positions: data.initial, ops: steps.map(() => 0), step: first, loop: 1, prev: last, mix: 1 });
    frames.end = end;
    return frames;
  };

  const videoType = () => ['video/mp4;codecs=avc1.42E01E', 'video/mp4;codecs=avc1', 'video/mp4']
    .find((type) => window.MediaRecorder && MediaRecorder.isTypeSupported(type));

  const makeVideo = async (format, theme, progress) => {
    const type = videoType();
    if (!type) throw new Error('no-mp4');
    await fontsReady();
    const fmt = FORMATS[format];
    const c = palette(theme);
    copyStyle.textContent = exportCss(c);
    const canvas = document.createElement('canvas');
    canvas.width = W;
    canvas.height = fmt.h;
    const ctx = canvas.getContext('2d');
    const frames = timeline();
    const dots = (active) => ({ n: steps.length, active });
    const startImage = await drawSvg(data.initial, steps.map(() => 0));
    const endImage = await drawSvg(frames.end.positions, frames.end.ops);
    const captionOf = (index) => (index < 0 ? data.intro : steps[index].text);
    const cardFor = async (frame) => {
      const text = captionOf(frame.step);
      const prevText = frame.prev === undefined ? undefined : captionOf(frame.prev);
      if (frame.loop !== undefined) {
        const shown = frame.loop > 0.5 ? frame.step : frame.prev;
        return { underImage: endImage, image: startImage, imageMix: frame.loop, text, prevText, textMix: frame.mix, dots: dots(shown) };
      }
      const shown = frame.mix !== undefined && frame.mix < 0.5 ? frame.prev : frame.step;
      return { image: await drawSvg(frame.positions, frame.ops), text, prevText, textMix: frame.mix === undefined ? 1 : frame.mix, dots: dots(shown) };
    };
    let card = await cardFor(frames[0]);
    drawCard(ctx, fmt, c, card.image, card);
    const stream = canvas.captureStream(FPS);
    const recorder = new MediaRecorder(stream, { mimeType: type, videoBitsPerSecond: 8000000 });
    const chunks = [];
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    const stopped = new Promise((resolve) => { recorder.onstop = resolve; });
    recorder.start();
    // MediaRecorder records in real time, so every frame is drawn at its moment.
    const start = performance.now();
    // A canvas stream only emits a frame when the canvas changes, so a still part (the pauses)
    // is drawn again on every frame; otherwise it would get no duration in the video.
    let lastKey = '';
    for (let i = 0; i < frames.length; i += 1) {
      const frame = frames[i];
      const key = JSON.stringify(frame);
      if (key !== lastKey) {
        card = await cardFor(frame);
        lastKey = key;
      }
      drawCard(ctx, fmt, c, card.image, card);
      progress(i / frames.length);
      const ahead = start + ((i + 1) * 1000) / FPS - performance.now();
      if (ahead > 0) await new Promise((resolve) => setTimeout(resolve, ahead));
    }
    recorder.stop();
    await stopped;
    stream.getTracks().forEach((track) => track.stop());
    return new Blob(chunks, { type: 'video/mp4' });
  };

  if (studio) {
    const state = { format: 'story', theme: 'dark', url: null };
    const result = studio.querySelector('[data-dd-result]');
    const preview = studio.querySelector('[data-dd-preview]');
    const actions = studio.querySelector('[data-dd-actions]');
    const hint = studio.querySelector('[data-dd-hint]');
    const makeButtons = [...studio.querySelectorAll('[data-dd-make]')];
    const videoButton = studio.querySelector('[data-dd-make="video"]');
    if (!videoType() || !HTMLCanvasElement.prototype.captureStream) {
      videoButton.disabled = true;
      videoButton.title = 'This browser cannot record MP4 video. Use Chrome or Safari.';
    }
    studio.hidden = false;
    studio.querySelectorAll('[data-dd-option]').forEach((button) => {
      button.addEventListener('click', () => {
        const [key, value] = button.dataset.ddOption.split(':');
        state[key] = value;
        studio.querySelectorAll(`[data-dd-option^="${key}:"]`).forEach((other) => other.setAttribute('aria-pressed', String(other === button)));
        if (key === 'format') videoButton.textContent = value === 'story' ? 'Create Reel' : 'Create video';
      });
    });

    const show = (blob, kind) => {
      if (state.url) URL.revokeObjectURL(state.url);
      state.url = URL.createObjectURL(blob);
      const ext = kind === 'video' ? 'mp4' : 'png';
      const name = `${slug}-${state.format}-${state.theme}.${ext}`;
      const file = new File([blob], name, { type: kind === 'video' ? 'video/mp4' : 'image/png' });
      const details = { share_kind: 'drill', share_media: kind, share_format: state.format, share_theme: state.theme, drill: slug };
      preview.innerHTML = kind === 'video'
        ? `<video src="${state.url}" controls muted loop playsinline autoplay></video>`
        : `<img src="${state.url}" alt="">`;
      preview.dataset.format = state.format;
      const canShare = Boolean(navigator.canShare && navigator.canShare({ files: [file] }));
      actions.innerHTML = `${canShare ? '<button type="button" class="fs-btn fs-btn--primary" data-dd-send>Share</button>' : ''}
        <a class="fs-btn${canShare ? '' : ' fs-btn--primary'}" href="${state.url}" download="${name}" data-dd-save>Download</a>`;
      hint.textContent = canShare
        ? (state.format === 'story' ? 'Tap Share, pick Instagram and post it as a Reel (or a Story with a link sticker to this page).' : 'Tap Share, pick Instagram and post it to your feed.')
        : 'Download it, then post it on Instagram from your phone' + (state.format === 'story' ? ' as a Reel.' : '.');
      actions.querySelector('[data-dd-save]').addEventListener('click', () => analytics.ctaCompleted('share_drill', { ...details, share_method: 'download' }));
      const send = actions.querySelector('[data-dd-send]');
      if (send) {
        send.addEventListener('click', async () => {
          try {
            await navigator.share({ files: [file] });
            analytics.ctaCompleted('share_drill', { ...details, share_method: 'share_sheet' });
          } catch (error) {
            if (error && error.name !== 'AbortError') analytics.ctaFailed('share_drill', 'share_error', { ...details, error_name: error.name || 'error' });
          }
        });
      }
      result.hidden = false;
    };

    makeButtons.forEach((button) => {
      button.addEventListener('click', async () => {
        const kind = button.dataset.ddMake;
        const label = button.textContent;
        makeButtons.forEach((other) => { other.disabled = true; });
        try {
          const blob = kind === 'video'
            ? await makeVideo(state.format, state.theme, (share) => { button.textContent = `Recording… ${Math.round(share * 100)}%`; })
            : await makeImage(state.format, state.theme);
          show(blob, kind);
        } catch (error) {
          console.error(error);
          hint.textContent = 'That did not work in this browser. Try Chrome or Safari.';
          result.hidden = false;
        } finally {
          button.textContent = label;
          makeButtons.forEach((other) => { other.disabled = other === videoButton && !videoType(); });
        }
      });
    });
  }

})();
