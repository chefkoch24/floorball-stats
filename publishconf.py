# This file is only used if you use `make publish` or
# explicitly specify it as your config file.

import os
import sys
sys.path.append(os.curdir)
from pelicanconf import *

# If your site is available via HTTPS, make sure SITEURL begins with https://
SITEURL = 'https://stats.floorballconnect.com'
# The main site (connect/) is built with this site and served on its own domain from
# /connect-site/ (plugins/connect_site.py): add www.floorballconnect.com and
# floorballconnect.com as domains of this Netlify site.
CONNECT_BUILD_DIR = 'connect-site'
CONNECT_BUILD_URL = CONNECT_URL
CONNECT_HOST = 'www.floorballconnect.com'
CONNECT_APEX = 'floorballconnect.com'
# Netlify deploy previews and branch deploys link to themselves, not to the live site.
if os.environ.get('CONTEXT') in ('deploy-preview', 'branch-deploy') and os.environ.get('DEPLOY_PRIME_URL'):
    SITEURL = os.environ['DEPLOY_PRIME_URL'].rstrip('/')
    # Previews show the main site under /connect-preview/ and leave the domains alone.
    CONNECT_BUILD_DIR = 'connect-preview'
    CONNECT_URL = CONNECT_BUILD_URL = SITEURL + '/connect-preview'
    CONNECT_HOST = CONNECT_APEX = ''
    NEWSLETTER_URL = CONNECT_URL + '/subscribe/'
RELATIVE_URLS = False

FEED_ALL_ATOM = 'feeds/all.atom.xml'
CATEGORY_FEED_ATOM = 'feeds/{slug}.atom.xml'

DELETE_OUTPUT_DIRECTORY = True


# Following items are often useful when publishing

#DISQUS_SITENAME = ""
#GOOGLE_ANALYTICS = ""

SEO_PREVIEW = os.environ.get('CONTEXT') in ('deploy-preview', 'branch-deploy')
