"""Pelican settings for floorballconnect.com, the main Floorball Connect site.

It shares the design system with the stats site (themes/my-theme) through themes/connect,
but is a separate, small build: no league data, only the collections in connect/data
(sticks, blades, drills, ...) and a few pages. Build with `make connect-html`.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))

SITENAME = 'Floorball Connect'
SITEURL = ''
STATS_URL = 'https://stats.floorballconnect.com'
# Newsletter: MailerLite form with double opt-in (the form the Softr site used).
MAILERLITE_FORM = 'https://assets.mailerlite.com/jsonp/1555021/forms/163099056744171464/subscribe'
SUBSTACK_URL = 'https://floorballconnect.substack.com/'
CONTACT_EMAIL = 'hello@floorballconnect.com'
SOCIAL_LINKS = [
    ('Instagram', 'https://www.instagram.com/floorballconnect/'),
    ('TikTok', 'https://www.tiktok.com/@floorballconnect'),
    ('YouTube', 'https://www.youtube.com/@FloorballConnect'),
]
FOLLOWERS = '7,500+'

PATH = os.path.join(HERE, 'content')
OUTPUT_PATH = os.path.join(HERE, 'output')
THEME = os.path.join(HERE, '..', 'themes', 'connect')
PLUGIN_PATHS = [os.path.join(HERE, 'plugins')]
# connect_pages: list and detail pages from connect/data/*.json
PLUGINS = ['connect_pages']
COLLECTIONS_DATA = os.path.join(HERE, 'data')

TIMEZONE = 'Europe/Berlin'
DEFAULT_LANG = 'en'

# No blog: pages and collections only.
ARTICLE_PATHS = []
DIRECT_TEMPLATES = ['index']
PAGE_PATHS = ['pages']
PAGE_URL = '{slug}/'
PAGE_SAVE_AS = '{slug}/index.html'
AUTHOR_SAVE_AS = AUTHORS_SAVE_AS = ''
CATEGORY_SAVE_AS = CATEGORIES_SAVE_AS = ''
TAG_SAVE_AS = TAGS_SAVE_AS = ''
ARCHIVES_SAVE_AS = ''
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

STATIC_PATHS = ['images', 'extra']
EXTRA_PATH_METADATA = {
    'extra/_redirects': {'path': '_redirects'},
    'extra/robots.txt': {'path': 'robots.txt'},
}

RELATIVE_URLS = False
DELETE_OUTPUT_DIRECTORY = True

# Reviews are submitted through Tally; the forms write into the Notion review databases.
REVIEW_FORMS = {
    'sticks': 'https://tally.so/r/gDdWLN',
    'blades': 'https://tally.so/r/81ajpY',
}

FAQ = [
    ('What is Floorball Connect?',
     'Floorball Connect is a platform that connects the global Floorball world. Our goal is to make it easier for players, fans, coaches and clubs to discover and share everything happening in the world of Floorball, also outside social media.'),
    ('Who is Floorball Connect for?',
     'Created by the Floorball community for the Floorball community: whether you are a player looking for training ideas, a coach searching for resources, a club seeking visibility, or a fan following international tournaments. Floorball Connect is built to bring us all together.'),
    ('How is Floorball Connect different from other Floorball sites?',
     'We strongly believe that a platform like Floorball Connect is missing globally: one place to find Floorball information, from equipment reviews to live streams and league stats.'),
    ('Can I contribute?',
     'Yes. The Floorball landscape is scattered across countless platforms and channels, so we invite everyone to share their content with us, whether it is a podcast, video, article or training material. We help bring it all together so the community can easily discover it in one place.'),
    ('What are the future plans?',
     'Our vision is to grow into the central hub for the global Floorball community. We want to help players, coaches, clubs and creators connect, learn and be discovered. This may include community features, advanced stats and digital tools tailored for Floorball.'),
    ('How much does it cost?',
     'Floorball Connect is free. To sign up for the newsletter we need nothing but your email address.'),
    ('I did not receive an email?',
     'Please check your inbox for a confirmation email; it may take a few minutes. If it is not there, check your spam or promotions folder. Still nothing? Send a quick message to hello@floorballconnect.com and we will make sure you are subscribed.'),
]
