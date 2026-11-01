// Both sites share the Explore menu; Stats also has an independent league menu.
(() => {
  const menus = [];
  document.querySelectorAll('[data-nav-toggle]').forEach((toggle) => {
    const panel = document.getElementById(toggle.getAttribute('aria-controls'));
    if (!panel) return;
    let menu = menus.find((entry) => entry.panel === panel);
    if (!menu) { menu = { panel, toggles: [] }; menus.push(menu); }
    menu.toggles.push(toggle);
  });

  const close = ({ toggles, panel }) => {
    panel.classList.remove('is-open');
    toggles.forEach((toggle) => toggle.setAttribute('aria-expanded', 'false'));
  };

  menus.forEach((menu) => menu.toggles.forEach((toggle) => {
    toggle.addEventListener('click', () => {
      const open = toggle.getAttribute('aria-expanded') !== 'true';
      menus.forEach(close);
      if (open) {
        menu.panel.classList.add('is-open');
        menu.toggles.forEach((trigger) => trigger.setAttribute('aria-expanded', 'true'));
      }
    });
  }));

  document.addEventListener('click', (event) => {
    menus.forEach((menu) => {
      if (!menu.panel.contains(event.target) && !menu.toggles.some((toggle) => toggle.contains(event.target))) close(menu);
    });
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    menus.forEach((menu) => {
      if (menu.panel.classList.contains('is-open')) {
        close(menu);
        const trigger = menu.toggles.find((toggle) => toggle.offsetParent !== null)
          || document.querySelector('[aria-controls="mainNav"]');
        if (trigger) trigger.focus();
      }
    });
  });
})();
