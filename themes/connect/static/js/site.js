// Floorball Connect: theme toggle, the Explore menu and filtering on collection pages.
(() => {
  const root = document.documentElement;
  const header = document.querySelector('.site-header');
  const updateHeaderOffset = () => {
    if (header) root.style.setProperty('--site-header-height', `${header.offsetHeight}px`);
  };
  updateHeaderOffset();
  window.addEventListener('resize', updateHeaderOffset, { passive: true });

  // Theme: same storage key as the stats site, so both sites keep the reader's choice.
  const toggle = document.querySelector('.theme-toggle');
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const stored = () => { try { return localStorage.getItem('fs_theme'); } catch (error) { return null; } };
  const setTheme = (theme, persist) => {
    root.setAttribute('data-theme', theme);
    root.style.colorScheme = theme;
    if (persist) { try { localStorage.setItem('fs_theme', theme); } catch (error) {} }
    if (toggle) {
      const dark = theme === 'dark';
      toggle.textContent = dark ? 'Light' : 'Dark';
      toggle.setAttribute('aria-pressed', dark ? 'true' : 'false');
      toggle.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
    }
  };
  setTheme(root.getAttribute('data-theme') || (media.matches ? 'dark' : 'light'), false);
  if (toggle) toggle.addEventListener('click', () => setTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark', true));
  media.addEventListener('change', (event) => { if (!stored()) setTheme(event.matches ? 'dark' : 'light', false); });

  // Explore menu.
  const menuToggle = document.querySelector('.menu-toggle');
  const nav = document.getElementById('mainNav');
  if (menuToggle && nav) {
    const close = () => { nav.classList.remove('is-open'); menuToggle.setAttribute('aria-expanded', 'false'); };
    menuToggle.addEventListener('click', () => {
      const open = menuToggle.getAttribute('aria-expanded') !== 'true';
      menuToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      nav.classList.toggle('is-open', open);
    });
    document.addEventListener('click', (event) => {
      if (nav.classList.contains('is-open') && !nav.contains(event.target) && !menuToggle.contains(event.target)) close();
    });
    document.addEventListener('keydown', (event) => { if (event.key === 'Escape') close(); });
  }

  // Collection pages: a search box and facet chips filter the cards in place.
  const list = document.querySelector('[data-filter-list]');
  if (!list) return;
  const items = [...list.querySelectorAll('[data-filter-item]')];
  const search = document.querySelector('[data-filter-search]');
  const chips = [...document.querySelectorAll('[data-filter-facet]')];
  const count = document.querySelector('[data-filter-count]');
  const empty = document.querySelector('[data-filter-empty]');
  let facet = '';
  const apply = () => {
    const query = (search ? search.value : '').trim().toLowerCase();
    let shown = 0;
    items.forEach((item) => {
      const facets = (item.dataset.facets || '').split('|');
      const match = (!facet || facets.includes(facet)) && (!query || item.dataset.search.includes(query));
      item.hidden = !match;
      if (match) shown += 1;
    });
    if (count) count.textContent = shown;
    if (empty) empty.hidden = shown > 0;
  };
  chips.forEach((chip) => chip.addEventListener('click', () => {
    facet = chip.dataset.filterFacet;
    chips.forEach((other) => other.setAttribute('aria-pressed', other === chip ? 'true' : 'false'));
    apply();
  }));
  if (search) search.addEventListener('input', apply);
})();
