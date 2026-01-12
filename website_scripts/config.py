from os import environ, getenv

from . import json_util

# -----------> General App <-----------
SESSION_COOKIE_NAME = environ["SESSION_COOKIE_NAME"]  # e.g. infomundi-session
WEBSITE_ROOT = environ["WEBSITE_ROOT"]  # e.g. /app (inside docker container)
BASE_URL = environ[
    "BASE_URL"
]  # e.g. https://infomundi.net (without the trailing slash)
LOCAL_ROOT = environ["LOCAL_ROOT"]  # e.g. /opt/infomundi/website
SEARCH_NEWS_DEBUG = str(getenv("FLASK_DEBUG", "")).lower() in ("1", "true")

# -----------> Secret Keys <-----------
TURNSTILE_SITE_KEY = environ["TURNSTILE_SITE_KEY"]
TURNSTILE_SECRET_KEY = environ["TURNSTILE_SECRET_KEY"]
OPENAI_API_KEY = environ["OPENAI_API_KEY"]
ENCRYPTION_KEY = environ["ENCRYPTION_KEY"]
SECRET_KEY = environ["SECRET_KEY"]
HMAC_KEY = environ["HMAC_KEY"]

# -----------> Files <-----------
PRESIDENTS_DATA = json_util.read_json(f"{WEBSITE_ROOT}/assets/data/json/presidents")
HDI_DATA = json_util.read_json(f"{WEBSITE_ROOT}/assets/data/json/hdi_data")

# -----------> Folders <-----------
COUNTRIES_DATA_PATH = f"{WEBSITE_ROOT}/assets/data/json/countries_data"

# -----------> Inputs <-----------
MIN_MESSAGE_LEN = 5
MAX_MESSAGE_LEN = 1000
MESSAGE_LENGTH_RANGE = (MIN_MESSAGE_LEN, MAX_MESSAGE_LEN)

MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 50
PASSWORD_LENGTH_RANGE = (MIN_PASSWORD_LEN, MAX_PASSWORD_LEN)

MIN_USERNAME_LEN = 3
MAX_USERNAME_LEN = 25
USERNAME_LENGTH_RANGE = (MIN_USERNAME_LEN, MAX_USERNAME_LEN)

# -----------> Profile Customization <-----------
MIN_DESCRIPTION_LEN = 0
MAX_DESCRIPTION_LEN = 1500
DESCRIPTION_LENGTH_RANGE = (MIN_DESCRIPTION_LEN, MAX_DESCRIPTION_LEN)

MIN_DISPLAY_NAME_LEN = 0
MAX_DISPLAY_NAME_LEN = 40
DISPLAY_NAME_LENGTH_RANGE = (MIN_DISPLAY_NAME_LEN, MAX_DISPLAY_NAME_LEN)

# -----------> Clearance <-----------
CAPTCHA_CLEARANCE_HOURS = 12

# -----------> Email <-----------
SMTP_USERNAME = "noreply@infomundi.net"
SMTP_PASSWORD = environ["SMTP_PASSWORD"]
SMTP_SERVER = environ["SMTP_SERVER"]
SMTP_PORT = environ["SMTP_PORT"]

# -----------> Databases <-----------
MYSQL_DATABASE = environ["MYSQL_DATABASE"]
MYSQL_HOST = environ["MYSQL_HOST"]
MYSQL_USERNAME = environ["MYSQL_USERNAME"]
MYSQL_PASSWORD = environ["MYSQL_PASSWORD"]

REDIS_DATABASE = 0
REDIS_HOST = environ["REDIS_HOST"]
REDIS_PORT = 6379
REDIS_PASSWORD = environ["REDIS_PASSWORD"]
REDIS_CONNECTION_STRING = (
    f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DATABASE}"
)

# -----------> Cloudflare R2 <-----------
R2_ENDPOINT = environ["R2_ENDPOINT"]
R2_SECRET = environ["R2_SECRET"]
R2_TOKEN = environ["R2_TOKEN"]
R2_ACCESS_KEY = environ["R2_ACCESS_KEY"]
BUCKET_BASE_URL = "https://bucket.infomundi.net"
BUCKET_NAME = "infomundi"


# -----------> Google OAuth <-----------
GOOGLE_CLIENT_ID = environ["GOOGLE_CLIENT_ID"]
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
GOOGLE_CLIENT_SECRET = environ["GOOGLE_CLIENT_SECRET"]


# -----------> Webhook <-----------
WEBHOOK_URL = environ["WEBHOOK_URL"]
