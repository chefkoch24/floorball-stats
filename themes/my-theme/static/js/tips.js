// Info boxes for abbreviations and short labels.
// Every [data-tip] element, and every element in the page content with a title (table headers,
// <abbr>, labels), shows its explanation on hover or keyboard focus and on tap on touch screens.
// One floating box is positioned against the viewport, so scroll containers never clip it.
(() => {
  const SELECTOR = 'main [title]:not(a):not(button):not(input):not(select):not(option):not(iframe), [data-tip]';
  // One place for what the site's abbreviations mean. Headers, labels and form letters whose whole
  // text is one of these get the explanation, on every page.
  const GLOSSARY = {
    'GP': 'Games played',
    'W': 'Wins in regulation time',
    'L': 'Losses in regulation time',
    'D': 'Draws',
    'OTW': 'Wins after overtime or penalty shots',
    'OTL': 'Losses after overtime or penalty shots',
    'OT': 'Overtime',
    'PS': 'Penalty shots (shootout)',
    'GD': 'Goal difference: goals scored minus goals conceded',
    'Pts': 'Points in the table',
    'PPG': 'Points per game',
    'GPG': 'Goals per game',
    'GF/G': 'Goals scored per game',
    'GA/G': 'Goals conceded per game',
    'GD/G': 'Goal difference per game',
    'PP%': 'Power play: share of power plays that produced a goal',
    'BP%': 'Box play (penalty kill): share of penalty kills without a goal against',
    'PK%': 'Penalty kill: share of penalty kills without a goal against',
    'PIM': 'Penalty minutes',
    'PIM/G': 'Penalties per game',
    'P/GP': 'Points per game played',
    'G': 'Goals',
    'G + A': 'Goals plus assists',
    'G or A': 'Goals the player scored or assisted',
    'GWG': 'Game-winning goals: the goal that put the winner one goal above the loser\'s final total',
    'W–L': 'Wins and losses',
    'Proj. pts': 'Average final points in the season simulations',
    'Proj. points': 'Average final points in the season simulations',
    'Clutch pts': 'Clutch goals plus assists on them: tying or go-ahead goals in the last ten minutes or overtime',
    '1st': 'Chance to finish first',
    'Top 4': 'Chance to finish in the top four',
    'P1': 'First period',
    'P2': 'Second period',
    'P3': 'Third period',
  };
  const GLOSSARY_SCOPE = 'th, dt, abbr, .fs-label, .fs-stat__label, .kpi-label, .tile-title, .fs-form__game, td.value-label';
  document.querySelectorAll(GLOSSARY_SCOPE).forEach((element) => {
    if (element.dataset.tip || element.hasAttribute('title')) return;
    const text = element.textContent.replace(/\s+/g, ' ').trim();
    if (GLOSSARY[text]) element.dataset.tip = GLOSSARY[text];
  });
  // Result badges such as "Final · OT" or "Final · PS".
  document.querySelectorAll('.fs-status').forEach((element) => {
    if (element.dataset.tip) return;
    const text = element.textContent;
    if (/·\s*OT\b/.test(text)) element.dataset.tip = 'Decided in overtime';
    else if (/·\s*PS\b/.test(text)) element.dataset.tip = 'Decided by penalty shots';
  });
  const box = document.createElement('div');
  box.className = 'fs-tip';
  box.id = 'fs-tip';
  box.setAttribute('role', 'tooltip');
  box.hidden = true;
  document.body.appendChild(box);
  let current = null;

  const prepare = (element) => {
    if (element.dataset.tipReady) return;
    const text = element.dataset.tip || element.getAttribute('title');
    if (!text) return;
    element.dataset.tip = text;
    element.removeAttribute('title');
    element.dataset.tipReady = '1';
    element.classList.add('fs-abbr');
    if (!element.hasAttribute('tabindex') && !element.matches('a, button, [href]')) element.tabIndex = 0;
  };

  const place = (element) => {
    const rect = element.getBoundingClientRect();
    box.style.left = '0px';
    box.style.top = '0px';
    const width = box.offsetWidth;
    const height = box.offsetHeight;
    const left = Math.min(Math.max(8, rect.left + rect.width / 2 - width / 2), window.innerWidth - width - 8);
    const above = rect.top - height - 8;
    const top = above > 8 ? above : rect.bottom + 8;
    box.style.left = `${left + window.scrollX}px`;
    box.style.top = `${top + window.scrollY}px`;
  };

  const show = (element) => {
    current = element;
    box.textContent = element.dataset.tip;
    box.hidden = false;
    element.setAttribute('aria-describedby', 'fs-tip');
    place(element);
  };

  const hide = () => {
    if (current) current.removeAttribute('aria-describedby');
    current = null;
    box.hidden = true;
  };

  document.querySelectorAll(SELECTOR).forEach(prepare);

  const target = (event) => event.target instanceof Element ? event.target.closest('[data-tip-ready]') : null;
  // After a tap, browsers also send emulated mouse and focus events; the pointerup handler
  // alone decides for touch.
  let lastTouch = 0;
  const fromTouch = () => Date.now() - lastTouch < 800;
  document.addEventListener('pointerdown', (event) => { if (event.pointerType !== 'mouse') lastTouch = Date.now(); });
  document.addEventListener('mouseover', (event) => { const element = target(event); if (element && !fromTouch()) show(element); });
  document.addEventListener('mouseout', (event) => { if (target(event) && !fromTouch()) hide(); });
  document.addEventListener('focusin', (event) => { const element = target(event); if (element && !fromTouch()) show(element); });
  document.addEventListener('focusout', (event) => { if (target(event) && !fromTouch()) hide(); });
  // Touch and pen: a tap opens the box, a second tap or a tap elsewhere closes it.
  // Mice already opened it on hover.
  document.addEventListener('pointerup', (event) => {
    if (event.pointerType === 'mouse') return;
    lastTouch = Date.now();
    const element = target(event);
    if (!element) { hide(); return; }
    if (element.closest('a, button')) return;
    if (current === element && !box.hidden) hide(); else show(element);
  });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') hide(); });
  window.addEventListener('scroll', () => { if (current) place(current); }, { passive: true });
})();
