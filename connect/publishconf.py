import os
import sys

# First on the path, so the stats site's pelicanconf.py in the repository root never wins.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pelicanconf import *  # noqa: E402,F403

SITEURL = 'https://www.floorballconnect.com'
# Netlify deploy previews and branch deploys link to themselves, not to the live site.
if os.environ.get('CONTEXT') in ('deploy-preview', 'branch-deploy') and os.environ.get('DEPLOY_PRIME_URL'):
    SITEURL = os.environ['DEPLOY_PRIME_URL'].rstrip('/')
