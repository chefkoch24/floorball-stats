AUTHOR = 'Felix'
SITENAME = 'Floorball Stats'
SITEURL = ''

PATH = 'content'

TIMEZONE = 'Europe/Berlin'

DEFAULT_LANG = 'de'
THEME = 'themes/my-theme/'

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

ARTICLE_PATHS = ['teams']


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
    ('Berlin Rockets', '/berlin-rockets.html'),
    ('Blau Weiss Schenefeld', '/blau-weiss-schenefeld.html'),
    ('DJK Holzbüttgen', '/djk-holzbuettgen.html'),
    ('ETV Piranhhas Hamburg', '/etv-piranhhas-hamburg.html'),
    ('Floor Fighters Chemnitz', '/floor-fighters-chemnitz.html'),
    ('MFBC Leipzig', '/mfbc-leipzig.html'),
    ('Red Devils Wernigerode', '/red-devils-wernigerode.html'),
    ('SSF Dragons Bonn', '/ssf-dragons-bonn.html'),
    ('TV Schriesheim', '/tv-schriesheim.html'),
    ('UHC Sparkasse Weißenfels', '/uhc-sparkasse-weissenfels.html'),
    ('Unihockey Igels Dresden', '/unihockey-igels-dresden.html'),
    ('VFL Red Hocks Kaufering', '/vfl-red-hocks-kaufering.html'),
)
