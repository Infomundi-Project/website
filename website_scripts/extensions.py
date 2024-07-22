from authlib.integrations.flask_client import OAuth
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_caching import Cache

from .config import REDIS_CONNECTION_STRING
from .cloudflare_util import get_user_ip

login_manager = LoginManager()
db = SQLAlchemy()
cache = Cache()

limiter = Limiter(
    key_func=get_user_ip,
    storage_uri=REDIS_CONNECTION_STRING
)

# Google OAuth
GOOGLE_CLIENT_ID = '785668376905-3mg53g7tod24g7hi5ams2gteq7752tl8.apps.googleusercontent.com'
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
GOOGLE_CLIENT_SECRET = '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'

oauth = OAuth()

google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    authorize_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_token_params=None,
    authorize_redirect_uri=None,
    authorize_scope='openid profile email',
    base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',  # This is only needed if using openId to fetch user info
    client_kwargs={'scope': 'openid profile email'},
    server_metadata_url=GOOGLE_DISCOVERY_URL
)
