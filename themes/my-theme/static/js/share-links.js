/* Link sharing for the share studio: the text that goes with a link, the tagged link itself and the
   share URLs of the platforms. Pure functions, no DOM access except in `canonicalUrl`, so
   tests/js/share-links.test.js can run them in node. share-card.js builds the buttons from this.

   Every shared link carries utm_source=share, utm_medium=<method> and utm_campaign=<kind>, so
   PostHog's pageview of the person who opens the link tells which way of sharing brings visitors.
   The canonical URL of the page stays untouched; only the copy that leaves the site is tagged. */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.fsShareLinks = api;
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';

  // `method` is the value of the share_method property in the share_link_* events.
  var PLATFORMS = [
    { method: 'whatsapp', label: 'WhatsApp', build: function (p) { return 'https://wa.me/?text=' + enc(p.text + ' ' + p.url); } },
    { method: 'telegram', label: 'Telegram', build: function (p) { return 'https://t.me/share/url?url=' + enc(p.url) + '&text=' + enc(p.text); } },
    { method: 'x', label: 'X', build: function (p) { return 'https://x.com/intent/post?text=' + enc(p.text) + '&url=' + enc(p.url); } },
    { method: 'facebook', label: 'Facebook', build: function (p) { return 'https://www.facebook.com/sharer/sharer.php?u=' + enc(p.url); } },
    { method: 'linkedin', label: 'LinkedIn', build: function (p) { return 'https://www.linkedin.com/sharing/share-offsite/?url=' + enc(p.url); } },
    { method: 'reddit', label: 'Reddit', build: function (p) { return 'https://www.reddit.com/submit?url=' + enc(p.url) + '&title=' + enc(p.text); } },
    { method: 'bluesky', label: 'Bluesky', build: function (p) { return 'https://bsky.app/intent/compose?text=' + enc(p.text + ' ' + p.url); } },
    { method: 'email', label: 'E-mail', build: function (p) { return 'mailto:?subject=' + enc(p.text) + '&body=' + enc(p.text + '\n\n' + p.url); } }
  ];

  function enc(value) {
    return encodeURIComponent(String(value == null ? '' : value));
  }

  function clean(value) {
    return String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
  }

  function join(parts, separator) {
    return parts.map(clean).filter(Boolean).join(separator);
  }

  // One line per card kind, built from the numbers on the page. No generated prose.
  function shareText(data) {
    var d = data || {};
    var where = join([d.league, d.season], ' ');
    switch (d.kind) {
      case 'game': {
        var played = d.homeGoals !== undefined && d.homeGoals !== '' && d.awayGoals !== undefined && d.awayGoals !== '';
        var score = played ? clean(d.home) + ' ' + d.homeGoals + ':' + d.awayGoals + ' ' + clean(d.away) : clean(d.home) + ' vs ' + clean(d.away);
        var decision = /OT|PS/.exec(clean(d.status));
        return join([score + (decision ? ' (' + decision[0] + ')' : ''), where], ' · ');
      }
      case 'team': {
        var rank = clean(d.rank) ? 'Rank ' + clean(d.rank) : '';
        var points = d.points || d.points === 0 ? d.points + ' pts' : '';
        var games = d.games ? d.games + ' games' : '';
        return join([clean(d.name), join([rank, points, games], ', '), where], ' · ');
      }
      case 'player': {
        var line = d.games ? d.goals + 'G ' + d.assists + 'A ' + d.points + 'P in ' + d.games + ' games' : '';
        return join([clean(d.name) + (clean(d.team) ? ' (' + clean(d.team) + ')' : ''), line, where], ' · ');
      }
      case 'table':
        return join([clean(d.league) + ' table', d.season, d.round ? 'after ' + d.round + ' games' : ''], ' · ');
      case 'leaderboard':
        return join([clean(d.title), d.division, d.season], ' · ');
      default:
        return clean(d.name || d.title || d.league);
    }
  }

  // `base` is the canonical URL of the page. Existing utm_* values are replaced, other parameters stay.
  function taggedUrl(base, method, kind) {
    var url;
    try {
      url = new URL(base);
    } catch (error) {
      return String(base || '');
    }
    url.hash = '';
    url.searchParams.set('utm_source', 'share');
    url.searchParams.set('utm_medium', method);
    url.searchParams.set('utm_campaign', kind || 'page');
    return url.toString();
  }

  // The canonical link of the page when it has one (preview and local builds do not), else the address bar.
  function canonicalUrl(doc, location) {
    var link = doc && doc.querySelector ? doc.querySelector('link[rel="canonical"]') : null;
    var href = link && link.getAttribute('href');
    if (href) return href;
    return location.origin + location.pathname;
  }

  // The list of platform links for a card: [{ method, label, href }].
  function platformLinks(data, base) {
    var text = shareText(data);
    return PLATFORMS.map(function (platform) {
      var url = taggedUrl(base, platform.method, data && data.kind);
      return { method: platform.method, label: platform.label, href: platform.build({ text: text, url: url }) };
    });
  }

  return { PLATFORMS: PLATFORMS, shareText: shareText, taggedUrl: taggedUrl, canonicalUrl: canonicalUrl, platformLinks: platformLinks };
});
