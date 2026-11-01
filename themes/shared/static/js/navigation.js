// Both sites share the Explore menu; Stats also has an independent league menu.
(() => {
  const menus = Array.from(document.querySelectorAll('[data-nav-toggle]')).map((toggle) => ({
    toggle,
    panel: document.getElementById(toggle.getAttribute('aria-controls')),
  })).filter(({ panel }) => panel);

  const close = ({ toggle, panel }) => {
    panel.classList.remove('is-open');
    toggle.setAttribute('aria-expanded', 'false');
  };

  menus.forEach((menu) => {
    menu.toggle.addEventListener('click', () => {
      const open = menu.toggle.getAttribute('aria-expanded') !== 'true';
      menus.forEach(close);
      if (open) {
        menu.panel.classList.add('is-open');
        menu.toggle.setAttribute('aria-expanded', 'true');
      }
    });
  });

  document.addEventListener('click', (event) => {
    menus.forEach((menu) => {
      if (!menu.panel.contains(event.target) && !menu.toggle.contains(event.target)) close(menu);
    });
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    menus.forEach((menu) => {
      if (menu.panel.classList.contains('is-open')) {
        close(menu);
        menu.toggle.focus();
      }
    });
  });
})();
