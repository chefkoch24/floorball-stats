from pelican.plugins import more_categories, jinja_filters
from functools import partial

SITENAME = 'Floorball Stats'
SITEURL = ''
PLUGINS = [
    jinja_filters,
    more_categories
]

PATH = 'content'

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
                 '25-26-regular-season/teams', '25-26-regular-season/liga', '25-26-playoffs/teams', '25-26-playoffs/liga',
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
    ('Regular Season 25-26', '/category/25-26-regular-season.html')
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
    slug = [s.capitalize() for s in slug]
    return f'{slug[0]}/' + " ".join(slug[1:])

def category2title(slug):
    slug = slug.split('-')
    return " ".join(slug)


JINJA_FILTERS = {
    'sort_by_rank': partial(sorted,
        key=lambda article: float(article.rank)),
    'string_in_category_path': string_in_category_path,
    'category2string': category2string,
    'category2title': category2title,
} # reversed for descending order
