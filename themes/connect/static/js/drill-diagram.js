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
  const PLAYER_SPEED = 95; // SVG units (decimetres) per second
  const BALL_SPEED = 280;
  const PAUSE = 420; // between steps

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
      count.textContent = `Step ${index + 1} / ${steps.length}`;
    }
  };

  // Players speed up and slow down softly; a pass or shot leaves the stick fast and only eases a little.
  const playerEase = (t) => -(Math.cos(Math.PI * t) - 1) / 2;
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
      const natural = ball ? Math.max(240, (length / BALL_SPEED) * 1000) : Math.max(380, (length / PLAYER_SPEED) * 1000);
      return { move, path, length, duration: instant ? 0 : natural, delay: 0, ease: ball ? ballEase : playerEase };
    }).filter(Boolean);
    const leaders = new Map(plan.filter((p) => !p.move.ball && !p.move.with).map((p) => [p.move.e, p]));
    plan.forEach((p) => {
      const carrier = p.move.with && leaders.get(p.move.with);
      if (carrier) { p.duration = carrier.duration; p.ease = carrier.ease; }
      const runner = p.move.into && leaders.get(p.move.into);
      if (runner) p.delay = Math.max(0, runner.duration - p.duration);
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
    svg:not(.x-playing) .is-later{opacity:0}.x-playing .is-future{opacity:0}.x-playing .is-past{opacity:.22}.x-playing .dd-step-label.is-past{opacity:0}`;

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

  const drawSvg = (positions, index) => new Promise((resolve, reject) => {
    Object.entries(positions).forEach(([id, point]) => {
      const node = copyEntities.get(id);
      if (node) node.setAttribute('transform', `translate(${point[0].toFixed(1)} ${point[1].toFixed(1)})`);
    });
    copy.classList.toggle('x-playing', index >= 0);
    copySteps.forEach((node) => {
      const step = Number(node.dataset.step);
      node.setAttribute('class', node.getAttribute('class').replace(/ ?is-(current|past|future)/g, '') +
        (index < 0 ? '' : step === index ? ' is-current' : step < index ? ' is-past' : ' is-future'));
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

  // One card: brand and chip on top, then title, rink and text centred in the space left,
  // the site at the bottom. Everything stays inside the zones Instagram leaves free.
  const drawCard = (ctx, fmt, c, image, { label, text, list }) => {
    const right = W - SIDE;
    const width = right - SIDE;
    ctx.textBaseline = 'alphabetic';
    ctx.textAlign = 'left';
    ctx.fillStyle = c.surface;
    ctx.fillRect(0, 0, W, fmt.h);
    font(ctx, 800, 44, DISPLAY, 'condensed');
    ctx.fillStyle = c.rink;
    ctx.fillText('Floorball Connect', SIDE, fmt.top + 40);
    font(ctx, 600, 26, BODY);
    const chip = 'Floorball drill';
    const chipW = ctx.measureText(chip).width + 44;
    roundRect(ctx, right - chipW, fmt.top + 4, chipW, 50, 25, null, c.line);
    ctx.fillStyle = c.muted;
    ctx.fillText(chip, right - chipW + 22, fmt.top + 38);
    // The site name may sit lower than the content: Instagram covers the very bottom only partly.
    const footerY = fmt.h - fmt.footer;
    font(ctx, 500, 28, BODY);
    ctx.fillText('Free animated drills', SIDE, footerY);
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
    const labelH = label ? 48 : 0;
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
      body.height = body.lh * 3;  // fixed, so the rink does not jump between steps
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
    ctx.drawImage(image, SIDE + (width - iw) / 2, y + (boxH - ih) / 2, iw, ih);
    y += boxH + 44;

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
      font(ctx, 500, body.size, BODY);
      ctx.fillStyle = c.ink;
      body.lines.forEach((line, i) => ctx.fillText(line, SIDE, y + i * body.lh + body.size * 0.92));
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
    const image = await drawSvg(data.initial, -1);
    const canvas = document.createElement('canvas');
    canvas.width = W;
    canvas.height = fmt.h;
    drawCard(canvas.getContext('2d'), fmt, c, image, { label: `${steps.length} steps`, list: steps.map((step) => step.text) });
    return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
  };

  // The same timeline as the player: overview, every step, short pauses, and an end card.
  const timeline = () => {
    const frames = [];
    const hold = (positions, index, ms, end) => { for (let t = 0; t < ms; t += 1000 / FPS) frames.push({ positions, index, end }); };
    hold(data.initial, -1, 1400);
    let positions = data.initial;
    steps.forEach((step, index) => {
      positions = { ...step.start };
      hold(positions, index, 300);
      step.stages.forEach((stage) => {
        const { plan, total } = planStage(stage, false);
        for (let t = 0; t <= total; t += 1000 / FPS) {
          const now = { ...positions };
          plan.forEach((p) => { const point = pointAt(p, t); if (point) now[p.move.e] = point; });
          frames.push({ positions: now, index });
        }
        positions = { ...positions };
        plan.forEach((p) => { positions[p.move.e] = pointAt(p, Infinity); });
      });
      hold(positions, index, index === steps.length - 1 ? 900 : PAUSE + 250);
    });
    hold(positions, steps.length - 1, 1800, true);
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
    drawCard(ctx, fmt, c, await drawSvg(frames[0].positions, -1), { label: 'Overview', text: `${steps.length} steps · watch the drill step by step` });
    const stream = canvas.captureStream(FPS);
    const recorder = new MediaRecorder(stream, { mimeType: type, videoBitsPerSecond: 8000000 });
    const chunks = [];
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    const stopped = new Promise((resolve) => { recorder.onstop = resolve; });
    recorder.start();
    // MediaRecorder records in real time, so every frame is drawn at its moment.
    const start = performance.now();
    // A canvas stream only emits a frame when the canvas changes, so a still part (the pauses,
    // the end card) is drawn again on every frame; otherwise it would get no duration in the video.
    let lastKey = '';
    let card = null;
    for (let i = 0; i < frames.length; i += 1) {
      const frame = frames[i];
      const key = JSON.stringify(frame);
      if (key !== lastKey) {
        const image = await drawSvg(frame.positions, frame.end ? -1 : frame.index);
        let label = `Step ${frame.index + 1} / ${steps.length}`;
        let text = frame.index >= 0 ? steps[frame.index].text : '';
        if (frame.index < 0) { label = 'Overview'; text = `${steps.length} steps · watch the drill step by step`; }
        if (frame.end) { label = 'More drills'; text = 'Animated drills with setup and coaching points: floorballconnect.com'; }
        card = { image, label, text };
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
