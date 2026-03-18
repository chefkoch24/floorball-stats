from pelican.plugins import more_categories, jinja_filters

SITENAME = 'Floorball Stats'
SITEURL = ''
PLUGINS = [
    jinja_filters,
    more_categories
]

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

ARTICLE_PATHS = ['22-23-regular-season/teams', '22-23-regular-season/liga', '22-23-playoffs/teams', '22-23-playoffs/liga',
                 '23-24-regular-season/teams', '23-24-regular-season/liga', '23-24-playoffs/teams', '23-24-playoffs/liga',
                 '24-25-regular-season/teams', '24-25-regular-season/liga', '24-25-playoffs/teams', '24-25-playoffs/liga',
                 '25-26-regular-season/teams',
                 '25-26-regular-season/liga',
                 '25-26-regular-season/games',
                 'se-25-26-regular-season/teams',
                 'se-25-26-regular-season/liga',
                 'se-25-26-regular-season/games',
                 'se-25-26-playoffs/teams',
                 'se-25-26-playoffs/liga',
                 'se-25-26-playoffs/games',
                 'fi-25-26-regular-season/teams',
                 'fi-25-26-regular-season/liga',
                 'fi-25-26-regular-season/games',
                 'lv-25-26-regular-season/teams',
                 'lv-25-26-regular-season/liga',
                 'lv-25-26-regular-season/games',
                 'lv-25-26-playoffs/teams',
                 'lv-25-26-playoffs/liga',
                 'lv-25-26-playoffs/games',
                 'sk-25-26-regular-season/teams',
                 'sk-25-26-regular-season/liga',
                 'sk-25-26-regular-season/games',
                 'sk-25-26-playoffs/teams',
                 'sk-25-26-playoffs/liga',
                 'sk-25-26-playoffs/games',
                 'cz-25-26-regular-season/teams',
                 'cz-25-26-regular-season/liga',
                 'cz-25-26-regular-season/games',
                 'cz-25-26-playoffs/teams',
                 'cz-25-26-playoffs/liga',
                 'cz-25-26-playoffs/games',
                 'ch-25-26-regular-season/teams',
                 'ch-25-26-regular-season/games',
                 'ch-25-26-regular-season/liga',
                 'ch-25-26-playoffs/teams',
                 'ch-25-26-playoffs/games',
                 'ch-25-26-playoffs/liga',
                 #'25-26-playoffs/teams', '25-26-playoffs/liga'
                 ] # add season links here for teams and liga
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

# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True

MENUITEMS = (
    ('Regular Season 22-23', '/category/22-23-regular-season.html'),
    ('Playoffs 22-23', '/category/22-23-playoffs.html'),
    ('Regular Season 23-24', '/category/23-24-regular-season.html'),
    ('Playoffs 23-24', '/category/23-24-playoffs.html'),
    ('Regular Season 24-25', '/category/24-25-regular-season.html'),
    ('Playoffs 24-25', '/category/24-25-playoffs.html'),
    ('Regular Season 25-26', '/category/25-26-regular-season.html'),
    ('Sweden Regular Season 25-26', '/category/se-25-26-regular-season.html'),
    ('Sweden Playoffs 25-26', '/category/se-25-26-playoffs.html'),
    ('Czech Republic Regular Season 25-26', '/category/cz-25-26-regular-season.html'),
    ('Czech Republic Playoffs 25-26', '/category/cz-25-26-playoffs.html'),
    ('Switzerland Regular Season 25-26', '/category/ch-25-26-regular-season.html'),
    ('Switzerland Playoffs 25-26', '/category/ch-25-26-playoffs.html'),
    ('Finland Regular Season 25-26', '/category/fi-25-26-regular-season.html'),
    ('Latvia Regular Season 25-26', '/category/lv-25-26-regular-season.html'),
    ('Slovakia Regular Season 25-26', '/category/sk-25-26-regular-season.html'),
    # add season links here
)

def string_in_category_path(article, string_to_check):
    # Get the article's category path as a list of strings
    categories = [c.shortname for c in article.categories]
    categories = [c.split('-') for c in categories]
    categories = [item for sublist in categories for item in sublist]
    # Check if the string is in the category path
    return string_to_check in categories

def category2string(slug):
    slug = slug.split('-')
    if slug[0] in {'se', 'sweden'}:
        label = 'Sweden'
        rest = slug[1:]
        if len(rest) >= 2 and rest[0].isdigit() and rest[1].isdigit():
            return f"{label} {rest[0]}/{rest[1]} " + " ".join([s.capitalize() for s in rest[2:]])
        return f"{label} " + " ".join([s.capitalize() for s in rest])
    if slug[0] in {'ch', 'switzerland'}:
        label = 'Switzerland'
        rest = slug[1:]
        if len(rest) >= 2 and rest[0].isdigit() and rest[1].isdigit():
            return f"{label} {rest[0]}/{rest[1]} " + " ".join([s.capitalize() for s in rest[2:]])
        return f"{label} " + " ".join([s.capitalize() for s in rest])
    if slug[0] in {'cz', 'czech'}:
        label = 'Czech Republic'
        rest = slug[1:]
        if len(rest) >= 2 and rest[0].isdigit() and rest[1].isdigit():
            return f"{label} {rest[0]}/{rest[1]} " + " ".join([s.capitalize() for s in rest[2:]])
        return f"{label} " + " ".join([s.capitalize() for s in rest])
    if slug[0] in {'fi', 'finland'}:
        label = 'Finland'
        rest = slug[1:]
        if len(rest) >= 2 and rest[0].isdigit() and rest[1].isdigit():
            return f"{label} {rest[0]}/{rest[1]} " + " ".join([s.capitalize() for s in rest[2:]])
        return f"{label} " + " ".join([s.capitalize() for s in rest])
    if slug[0] in {'lv', 'latvia'}:
        label = 'Latvia'
        rest = slug[1:]
        if len(rest) >= 2 and rest[0].isdigit() and rest[1].isdigit():
            return f"{label} {rest[0]}/{rest[1]} " + " ".join([s.capitalize() for s in rest[2:]])
        return f"{label} " + " ".join([s.capitalize() for s in rest])
    if slug[0] in {'sk', 'slovakia'}:
        label = 'Slovakia'
        rest = slug[1:]
        if len(rest) >= 2 and rest[0].isdigit() and rest[1].isdigit():
            return f"{label} {rest[0]}/{rest[1]} " + " ".join([s.capitalize() for s in rest[2:]])
        return f"{label} " + " ".join([s.capitalize() for s in rest])
    slug = [s.capitalize() for s in slug]
    return f'{slug[0]}/' + " ".join(slug[1:])

def category2title(slug):
    slug = slug.split('-')
    return " ".join(slug)

def category2breadcrumb(slug):
    parts = slug.split('-')
    country_map = {
        'se': 'Sweden',
        'sweden': 'Sweden',
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
    }

    country = country_map.get(parts[0], 'Germany')
    is_prefixed_country = parts[0] in country_map
    season_parts = parts[1:3] if is_prefixed_country else parts[0:2]
    phase_parts = parts[3:] if is_prefixed_country else parts[2:]
    phase_label = " ".join([part.capitalize() for part in phase_parts]) if phase_parts else "Season"

    if len(season_parts) == 2 and season_parts[0].isdigit() and season_parts[1].isdigit():
        season = f"{season_parts[0]}/{season_parts[1]}"
        return f"{country} {phase_label} {season}"

    return country


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
    'string_in_category_path': string_in_category_path,
    'category2string': category2string,
    'category2title': category2title,
    'category2breadcrumb': category2breadcrumb,
    'fmt2': fmt2,
    'fmt_int': fmt_int,
} # reversed for descending order

JINJA_ENVIRONMENT = {
    'finalize': finalize_rendered_value,
}
