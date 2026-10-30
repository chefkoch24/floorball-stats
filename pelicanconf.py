from pelican.plugins import more_categories, jinja_filters
from datetime import datetime, time
import os
import re
import zlib

SITENAME = 'Floorball Stats'
SITEURL = ''
FEEDBACK_EMAIL = 'hello@floorballconnect.com'
# The main site (connect/) and its newsletter, linked from the menu and the footer.
CONNECT_URL = 'https://www.floorballconnect.com'
NEWSLETTER_URL = 'https://floorballconnect.substack.com/'
# Payment link for the support banner (Ko-fi, Stripe Payment Link, ...); banner stays hidden while empty
SUPPORT_URL = os.environ.get('SUPPORT_URL', '')
PLUGIN_PATHS = ['plugins']
PLUGINS = [
    jinja_filters,
    more_categories,
    'sitemap',
    # og:image share cards and team .ics calendars for the current season
    'share_assets',
    # team rosters on team pages, team links on player pages
    'rosters',
    # cross-league leaderboards for the leaders page
    'leaders',
    # clutch stats, scoring duos, Elo power ratings and season projections
    'insights',
    # deploy previews only: builds the main site (connect/) into /connect-preview/
    'connect_preview',
]
DIRECT_TEMPLATES = ['index', 'tags', 'categories', 'authors', 'archives', 'leaders']

PATH = 'content'
PAGE_PATHS = ['pages']
PAGE_URL = '{slug}.html'
PAGE_SAVE_AS = '{slug}.html'

TIMEZONE = 'Europe/Berlin'
USE_FOLDER_AS_CATEGORY = False
DEFAULT_LANG = 'de'
THEME = 'themes/my-theme/'

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

# Club seasons shown on the site, newest first. CURRENT_SEASON drives the
# navigation and "Today's Games"; older seasons stay reachable from the home
# page. Season rollover: prepend the new season here and bump CURRENT_SEASON
# in the Makefile (plus the new config/leagues/*-<season>*.json files).
SEASONS = ['26-27', '25-26']
CURRENT_SEASON = SEASONS[0]
SEASON_PHASES = ['regular-season', 'playoffs']

# Category prefix per league (Germany has none), in navigation order.
# `division` drives the men/women switch in the navigation and the home page groups.
DIVISIONS = [('men', 'Men'), ('women', 'Women')]
LEAGUES = [
    {'prefix': 'se-', 'name': 'Sweden', 'title': 'Sweden · SSL', 'division': 'men'},
    {'prefix': 'fi-', 'name': 'Finland', 'title': 'Finland · F-Liiga', 'division': 'men'},
    {'prefix': 'cz-', 'name': 'Czech Republic', 'title': 'Czech Republic · ČEZ Extraliga', 'division': 'men'},
    {'prefix': 'ch-', 'name': 'Switzerland', 'title': 'Switzerland · L-UPL', 'division': 'men'},
    {'prefix': 'sk-', 'name': 'Slovakia', 'title': 'Slovakia · Extraliga mužov', 'division': 'men'},
    {'prefix': 'lv-', 'name': 'Latvia', 'title': 'Latvia · ELVI līga vīriešiem', 'division': 'men'},
    {'prefix': '', 'name': 'Germany', 'title': 'Germany · 1. FBL Herren', 'division': 'men'},
    {'prefix': 'sew-', 'name': 'Sweden', 'title': 'Sweden · SSL Damer', 'division': 'women'},
    {'prefix': 'fiw-', 'name': 'Finland', 'title': 'Finland · F-Liiga Naiset', 'division': 'women'},
    {'prefix': 'czw-', 'name': 'Czech Republic', 'title': 'Czech Republic · ČEZ Extraliga žen', 'division': 'women'},
    {'prefix': 'chw-', 'name': 'Switzerland', 'title': 'Switzerland · L-UPL Damen', 'division': 'women'},
    {'prefix': 'skw-', 'name': 'Slovakia', 'title': 'Slovakia · Extraliga žien', 'division': 'women'},
    {'prefix': 'lvw-', 'name': 'Latvia', 'title': 'Latvia · ELVI līga sievietēm', 'division': 'women'},
    {'prefix': 'dew-', 'name': 'Germany', 'title': 'Germany · 1. FBL Damen', 'division': 'women'},
]
# International club competitions: one knockout phase per season, category
# "<prefix><season>-playoffs" (configs in config/leagues/iff-champions-cup-*-playoffs.json).
COMPETITIONS = [
    {'prefix': 'cc-', 'name': 'Champions Cup', 'title': 'IFF Champions Cup', 'division': 'men', 'phase': 'playoffs'},
    {'prefix': 'ccw-', 'name': 'Champions Cup', 'title': 'IFF Champions Cup Women', 'division': 'women', 'phase': 'playoffs'},
]
WOMEN_LEAGUE_PREFIXES = [
    league['prefix'] for league in LEAGUES + COMPETITIONS if league['division'] == 'women'
]

ARTICLE_PATHS = ['22-23-regular-season/teams', '22-23-regular-season/liga', '22-23-playoffs/teams', '22-23-playoffs/liga',
                 '23-24-regular-season/teams', '23-24-regular-season/liga', '23-24-playoffs/teams', '23-24-playoffs/liga',
                 '24-25-regular-season/teams', '24-25-regular-season/liga', '24-25-playoffs/teams', '24-25-playoffs/liga',
                 ] + [
                 f"{league['prefix']}{season}-{phase}/{kind}"
                 for season in SEASONS
                 for league in LEAGUES
                 for phase in SEASON_PHASES
                 for kind in ('teams', 'liga', 'games')
                 ] + [
                 f"{competition['prefix']}{season}-{competition['phase']}/{kind}"
                 for season in SEASONS
                 for competition in COMPETITIONS
                 for kind in ('teams', 'liga', 'games')
                 ] + [
                 'wfc-2024-regular-season/teams',
                 'wfc-2024-regular-season/games',
                 'wfc-2024-regular-season/liga',
                 'wfc-2024-playoffs/teams',
                 'wfc-2024-playoffs/games',
                 'wfc-2024-playoffs/liga',
                 'players',
                 'player-stats',
                 ]
STATIC_PATHS = ARTICLE_PATHS

# Blogroll
LINKS = (('Pelican', 'https://getpelican.com/'),
         ('Python.org', 'https://www.python.org/'),
         ('Jinja2', 'https://palletsprojects.com/p/jinja/'),
         ('You can modify those links in your config file', '#'),)

# Social widget
SOCIAL = (('You can add links in your config file', '#'),
          ('Another social link', '#'),)

DEFAULT_PAGINATION = False

SITEMAP = {
    "format": "xml",
    "priorities": {
        "articles": 1.0,
        "indexes": 0.8,
        "pages": 0.4,
    },
    "changefreqs": {
        "articles": "daily",
        "indexes": "weekly",
        "pages": "monthly",
    },
}

# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True

MENUITEMS = tuple(
    [
        ('Regular Season 22-23', '/category/22-23-regular-season.html'),
        ('Playoffs 22-23', '/category/22-23-playoffs.html'),
        ('Regular Season 23-24', '/category/23-24-regular-season.html'),
        ('Playoffs 23-24', '/category/23-24-playoffs.html'),
        ('Regular Season 24-25', '/category/24-25-regular-season.html'),
        ('Playoffs 24-25', '/category/24-25-playoffs.html'),
    ]
    + [
        (f"{league['title']} {phase.replace('-', ' ').title()} {season}",
         f"/category/{league['prefix']}{season}-{phase}.html")
        for season in reversed(SEASONS)
        for league in LEAGUES
        for phase in SEASON_PHASES
    ]
    + [('IFF WFC 2024', '/wfc-2024.html')]
)

def string_in_category_path(article, string_to_check):
    # Get the article's category path as a list of strings
    categories = [c.shortname for c in article.categories]
    categories = [c.split('-') for c in categories]
    categories = [item for sublist in categories for item in sublist]
    # Check if the string is in the category path
    return string_to_check in categories

# Category slug prefix -> display label (Germany has no prefix).
COUNTRY_LABELS = {
    'se': 'Sweden',
    'sweden': 'Sweden',
    'sew': 'Sweden Women',
    'chw': 'Switzerland Women',
    'czw': 'Czech Republic Women',
    'fiw': 'Finland Women',
    'lvw': 'Latvia Women',
    'skw': 'Slovakia Women',
    'dew': 'Germany Women',
    'ch': 'Switzerland',
    'switzerland': 'Switzerland',
    'cz': 'Czech Republic',
    'czech': 'Czech Republic',
    'fi': 'Finland',
    'finland': 'Finland',
    'lv': 'Latvia',
    'latvia': 'Latvia',
    'sk': 'Slovakia',
    'slovakia': 'Slovakia',
    'cc': 'IFF Champions Cup',
    'ccw': 'IFF Champions Cup Women',
}

def category2string(slug):
    slug = slug.split('-')
    is_players = bool(slug) and slug[-1] == 'players'
    if is_players:
        slug = slug[:-1]
    if not slug:
        return 'Players'
    label = COUNTRY_LABELS.get(slug[0])
    if label:
        rest = slug[1:]
        if len(rest) >= 2 and rest[0].isdigit() and rest[1].isdigit():
            base = f"{label} {rest[0]}/{rest[1]} " + " ".join([s.capitalize() for s in rest[2:]])
            return f"{base} Player Stats" if is_players else base
        base = f"{label} " + " ".join([s.capitalize() for s in rest])
        return f"{base} Player Stats" if is_players else base
    if slug[0] in {'wfc', 'iff'}:
        if len(slug) >= 2 and slug[1].isdigit():
            base = (f"IFF WFC {slug[1]} " + " ".join([s.capitalize() for s in slug[2:]])).strip()
            return f"{base} Player Stats" if is_players else base
        base = ("IFF WFC " + " ".join([s.capitalize() for s in slug[1:]])).strip()
        return f"{base} Player Stats" if is_players else base
    slug = [s.capitalize() for s in slug]
    base = f'{slug[0]}/' + " ".join(slug[1:])
    return f"{base} Player Stats" if is_players else base

def _slug_parts(slug):
    if isinstance(slug, list):
        if not slug:
            return []
        # Pelican metadata can surface duplicated list values like
        # ['Playoffs', 'Playoffs']; use the first non-empty entry.
        for part in slug:
            text = str(part).strip()
            if text:
                slug = text
                break
        else:
            return []
    if slug is None:
        return []
    text = str(slug).strip()
    if not text:
        return []
    return [part for part in text.split('-') if part]


def category2title(slug):
    parts = _slug_parts(slug)
    return " ".join(parts)

def category2breadcrumb(slug):
    parts = _slug_parts(slug)
    is_players = bool(parts) and parts[-1] == 'players'
    if is_players:
        parts = parts[:-1]
    if not parts:
        return 'Players'
    country_map = {**COUNTRY_LABELS, 'wfc': 'IFF WFC', 'iff': 'IFF WFC'}

    country = country_map.get(parts[0], 'Germany')
    is_prefixed_country = parts[0] in country_map
    season_parts = parts[1:3] if is_prefixed_country else parts[0:2]
    phase_parts = parts[3:] if is_prefixed_country else parts[2:]
    phase_label = " ".join([part.capitalize() for part in phase_parts]) if phase_parts else "Season"

    if len(season_parts) == 2 and season_parts[0].isdigit() and season_parts[1].isdigit():
        season = f"{season_parts[0]}/{season_parts[1]}"
        base = f"{country} {phase_label} {season}"
        return f"{base} Player Stats" if is_players else base

    return f"{country} Player Stats" if is_players else country


def category_slugs(categories):
    """Slugs of all generated category pages (Pelican's `categories` context)."""
    slugs = set()
    for entry in categories or []:
        category = entry[0] if isinstance(entry, (list, tuple)) else entry
        slug = getattr(category, 'slug', None)
        if slug:
            slugs.add(slug)
    return slugs

# Words that name the club type rather than the club; skipped for monogram initials.
CREST_SKIP_WORDS = {
    'ibk', 'ibf', 'fbc', 'fc', 'if', 'uhc', 'sk', 'fbk', 'ik', 'ib', 'fbs', 'sv', 'tsv', 'ssf', 'etv', 'mfbc',
    'fk', 'sc', 'uhv', 'fb', 'nts', 'mkšs', 'šk', 'ftc', 'gms', 'florbal', 'floorball', 'unihockey', 'innebandy',
    'salibandy', 'team', 'club',
}


def team_initials(name):
    """Two or three letters for a team's monogram crest ("Thorengruppen IBK" -> "THO")."""
    words = re.findall(r"[^\W\d_]+", str(name or ''))
    core = [word for word in words if word.lower() not in CREST_SKIP_WORDS] or words
    if not core:
        return '?'
    if len(core) == 1:
        return core[0][:3].upper()
    return ''.join(word[0] for word in core[:3]).upper()


def crest_index(name):
    """Stable crest colour 1-8 for a team name, the same on every page and build."""
    return zlib.crc32(str(name or '').strip().lower().encode('utf-8')) % 8 + 1


def team_url(team, category):
    """URL of a team's page in a season phase, the slug generate_markdown.py writes."""
    from unidecode import unidecode

    fragment = unidecode(str(team or '')).lower().replace('&', ' and ')
    fragment = re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', fragment)).strip('-')
    return f"{fragment}-{category}-{category}.html"


def league_context(slug):
    """League entry, season and phase for a category slug such as "sew-26-27-regular-season"."""
    slug = str(slug or '')
    for league in sorted(LEAGUES + COMPETITIONS, key=lambda item: -len(item['prefix'])):
        for season in SEASONS:
            head = f"{league['prefix']}{season}-"
            if slug.startswith(head):
                return {**league, 'season': season, 'season_label': season.replace('-', '/'), 'phase': slug[len(head):]}
    return None


_NATIONAL_TEAM_PAGES = None


def _load_national_team_pages():
    """(division, season, team title) -> (slug, league) for every regular-season team page."""
    pages = {}
    content_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), PATH)
    for league in LEAGUES:
        for season in SEASONS:
            folder = os.path.join(content_root, f"{league['prefix']}{season}-regular-season", 'teams')
            if not os.path.isdir(folder):
                continue
            for filename in os.listdir(folder):
                if not filename.endswith('.md'):
                    continue
                meta = {}
                with open(os.path.join(folder, filename), encoding='utf-8') as handle:
                    for line in handle:
                        key, _, value = line.partition(':')
                        if key in ('Title', 'Slug'):
                            meta[key] = value.strip()
                        if len(meta) == 2:
                            break
                if 'Title' in meta and 'Slug' in meta:
                    pages[(league['division'], season, meta['Title'].lower())] = (meta['Slug'], league)
    return pages


def national_team_page(team, category_slug):
    """The club's national league team page for a Champions Cup team, or None."""
    global _NATIONAL_TEAM_PAGES
    context = league_context(category_slug)
    if not context or context['prefix'] not in {competition['prefix'] for competition in COMPETITIONS}:
        return None
    if _NATIONAL_TEAM_PAGES is None:
        _NATIONAL_TEAM_PAGES = _load_national_team_pages()
    found = _NATIONAL_TEAM_PAGES.get((context['division'], context['season'], str(team or '').strip().lower()))
    if not found:
        return None
    slug, league = found
    return {'url': f"{slug}.html", 'title': league['title'], 'season': context['season_label']}


def sort_by_rank(articles):
    # Artikel mit rank Attribut
    ranked_articles = [a for a in articles if hasattr(a, 'rank') and a.rank is not None]
    # Artikel ohne rank Attribut
    unranked_articles = [a for a in articles if not hasattr(a, 'rank') or a.rank is None]

    # Sortiere nur die Artikel mit rank
    try:
        sorted_ranked = sorted(ranked_articles, key=lambda article: float(article.rank))
        return sorted_ranked + unranked_articles
    except (ValueError, TypeError):
        return articles

def fmt2(value, default='n.a.'):
    if value is None or value == '':
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return f"{float(value):.2f}"
    if isinstance(value, str):
        try:
            parsed = float(value)
            return f"{parsed:.2f}"
        except (ValueError, TypeError):
            return value
    return value

def fmt_int(value, default='n.a.'):
    if value is None or value == '' or value == 'None':
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return value
    return value

def fmt_time(value, default='TBD'):
    if value is None or value == '' or value == 'None':
        return default
    if isinstance(value, time):
        return value.strftime('%H:%M')
    if isinstance(value, datetime):
        return value.strftime('%H:%M')
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return default
        if len(cleaned) >= 5 and cleaned[2] == ':' and cleaned[:2].isdigit() and cleaned[3:5].isdigit():
            return cleaned[:5]
        return cleaned
    return value

def finalize_rendered_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, str):
        try:
            parsed = float(value)
            return value if parsed.is_integer() else f"{parsed:.2f}"
        except (ValueError, TypeError):
            return value
    return value

JINJA_FILTERS = {
    'sort_by_rank': sort_by_rank,
    'category_slugs': category_slugs,
    'string_in_category_path': string_in_category_path,
    'category2string': category2string,
    'category2title': category2title,
    'category2breadcrumb': category2breadcrumb,
    'fmt2': fmt2,
    'fmt_int': fmt_int,
    'fmt_time': fmt_time,
    'team_initials': team_initials,
    'crest_index': crest_index,
    'league_context': league_context,
    'national_team_page': national_team_page,
    'team_url': team_url,
} # reversed for descending order

JINJA_ENVIRONMENT = {
    'finalize': finalize_rendered_value,
}
