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

  // Live stats on the home page, from the stats site's connect-feed.json. The block stays
  // hidden when the feed cannot be loaded; the stats teaser below it is the fallback.
  const live = document.querySelector('[data-live-stats]');
  if (live) {
    const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const crest = (n, initials) => `<span class="fs-crest fs-crest--sm" data-crest="${escape(n)}" aria-hidden="true">${escape(initials)}</span>`;
    const pad = (n) => String(n).padStart(2, '0');
    const now = new Date();
    const todayKey = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    let feed = null;
    let division = (() => { try { return localStorage.getItem('fs_division') === 'women' ? 'women' : 'men'; } catch (error) { return 'men'; } })();

    const renderGames = () => {
      const games = feed.games.filter((game) => game.division === division);
      let shown = games.filter((game) => game.date === todayKey);
      let label = `${shown.length} game${shown.length === 1 ? '' : 's'} today`;
      if (!shown.length) {
        const next = games.map((game) => game.date).filter((day) => day > todayKey).sort()[0];
        shown = next ? games.filter((game) => game.date === next) : [];
        label = shown.length ? `Next matchday: ${shown[0].day}` : 'No games scheduled right now.';
      }
      live.querySelector('[data-live-games-label]').textContent = label;
      live.querySelector('[data-live-games]').innerHTML = shown.map((game) => {
        const played = game.state === 'played' && game.homeGoals !== null && game.awayGoals !== null;
        const homeLost = played && game.homeGoals < game.awayGoals;
        const awayLost = played && game.awayGoals < game.homeGoals;
        const status = played
          ? `<span class="fs-status fs-status--final">Final${game.decision ? ' · ' + escape(game.decision) : ''}</span>`
          : `<span class="fs-status">${escape(game.time)}</span>`;
        const scores = played
          ? `<span class="${homeLost ? 'fs-match__loser' : ''}">${game.homeGoals}</span><span class="${awayLost ? 'fs-match__loser' : ''}">${game.awayGoals}</span>`
          : (game.homeChance ? `<span class="fc-chance">${escape(game.homeChance)}</span><span class="fc-chance">${escape(game.awayChance)}</span>` : '<span class="fs-match__loser">–</span><span class="fs-match__loser">–</span>');
        return `<a class="fs-match" href="${escape(game.url)}">
          <div class="fs-match__meta"><span>${escape(game.league)}</span>${status}</div>
          <div class="fs-match__teams">
            <span class="${homeLost ? 'fs-match__loser' : ''}"><span class="fs-team">${crest(game.homeCrest, game.homeInitials)}<span>${escape(game.home)}</span></span></span>
            <span class="${awayLost ? 'fs-match__loser' : ''}"><span class="fs-team">${crest(game.awayCrest, game.awayInitials)}<span>${escape(game.away)}</span></span></span>
          </div>
          <div class="fs-match__scores">${scores}</div>
        </a>`;
      }).join('');
    };

    const renderPower = () => {
      live.querySelector('[data-live-power]').innerHTML = (feed.power[division] || []).map((league) => `
        <a class="fc-league" href="${escape(league.url)}">
          <span class="fs-label">${escape(league.country)}</span>
          <strong>${escape(league.league)}</strong>
          <ol>${league.teams.slice(0, 3).map((team) => `
            <li><span class="fc-league__rank fs-num">${team.rank}</span><span class="fs-team">${crest(team.crest, team.initials)}<span>${escape(team.team)}</span></span><span class="fc-league__rating fs-num">${team.rating}</span></li>`).join('')}
          </ol>
        </a>`).join('');
    };

    const renderLeaders = () => {
      const board = (feed.leaders[division] || []).find((entry) => entry.key === 'points');
      live.querySelector('[data-live-leaders]').innerHTML = board ? board.entries.map((entry) => `
        <li>
          <span class="fc-league__rank fs-num">${entry.rank}</span>
          ${crest(entry.crest, entry.initials)}
          <span class="fc-leader__who">${entry.url ? `<a href="${escape(entry.url)}">${escape(entry.name)}</a>` : escape(entry.name)}<small>${escape(entry.team)} · ${escape(entry.code)}</small></span>
          <span class="fc-leader__value fs-num">${escape(entry.value)}<small>${escape(board.unit)}</small></span>
        </li>`).join('') : '';
    };

    const render = () => {
      live.querySelectorAll('[data-live-division]').forEach((button) => button.setAttribute('aria-pressed', button.dataset.liveDivision === division ? 'true' : 'false'));
      renderGames();
      renderPower();
      renderLeaders();
    };
    live.querySelectorAll('[data-live-division]').forEach((button) => button.addEventListener('click', () => {
      division = button.dataset.liveDivision;
      try { localStorage.setItem('fs_division', division); } catch (error) {}
      render();
    }));
    fetch(live.dataset.liveStats)
      .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
      .then((data) => { feed = data; render(); live.hidden = false; })
      .catch(() => {});
  }

  // Newsletter sign-up: MailerLite answers with JSON, so errors show next to the field and
  // a successful sign-up goes on to the "check your inbox" page (double opt-in).
  document.querySelectorAll('[data-signup]').forEach((form) => {
    const message = form.querySelector('[data-signup-message]');
    const button = form.querySelector('button[type="submit"]');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (button) button.disabled = true;
      if (message) message.textContent = 'Signing you up…';
      try {
        const response = await fetch(form.action, { method: 'POST', body: new FormData(form) });
        const result = await response.json();
        if (result.success) {
          if (window.posthog && posthog.capture) posthog.capture('newsletter_signup', { form: form.id });
          window.location.href = form.dataset.success;
          return;
        }
        const errors = result.errors && result.errors.fields ? Object.values(result.errors.fields).flat() : [];
        if (message) message.textContent = errors[0] || 'That did not work. Please check your email address.';
      } catch (error) {
        if (message) message.textContent = 'We could not reach the sign-up service. Please try again in a moment.';
      }
      if (button) button.disabled = false;
    });
  });

  // Share buttons: the phone's share sheet where there is one, else copy the link.
  document.querySelectorAll('[data-share]').forEach((button) => button.addEventListener('click', async () => {
    const data = { title: button.dataset.shareTitle || document.title, url: window.location.href };
    try {
      if (navigator.share) { await navigator.share(data); return; }
      await navigator.clipboard.writeText(data.url);
      const label = button.textContent;
      button.textContent = 'Link copied';
      setTimeout(() => { button.textContent = label; }, 1800);
    } catch (error) {}
  }));

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
