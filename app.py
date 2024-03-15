from flask import Flask, render_template, request
from flask_assets import Environment, Bundle
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from flask_talisman import Talisman
from flask_gzip import Gzip
from os import urandom

from website_scripts.config import APP_SECRET_KEY, MYSQL_USERNAME, MYSQL_PASSWORD
from website_scripts.extensions import db, login_manager
from website_scripts.models import User
from auth import auth_views
from views import views
from api import api


app = Flask(__name__, static_folder='static')
app.secret_key = APP_SECRET_KEY

# Session Cookie Configuration
app.config['SESSION_COOKIE_NAME'] = 'infomundi-session'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True

# SQLAlchemy Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{MYSQL_USERNAME}:{MYSQL_PASSWORD}@localhost/infomundi'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Uploads
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 Megabytes
app.config['UPLOAD_FOLDER'] = 'static/img/users/'

# Blueprints
app.register_blueprint(views, url_prefix='/')
app.register_blueprint(api, url_prefix='/api')
app.register_blueprint(auth_views, url_prefix='/auth')

# CSRF Configuration
csrf = CSRFProtect(app)
csrf.exempt('api.comments') # There's no need to protect this endpoint

# Login manager
login_manager.init_app(app)
login_manager.login_view = 'auth.login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


# Performance
gzip = Gzip(app)

assets = Environment(app)

# Base template bundles
css_base = Bundle(
    'css/main.css', 'css/navbar.css', 'css/ticker.css', 
    filters='cssmin', 
    output='gen/base_packed.css')
js_base = Bundle(
    'js/lazysizes.min.js', 'js/themeButton.js', 'js/triggerTooltip.js', 'js/tickerSpeedUp.js', 'js/initGoogleTranslate.js', 'js/triggerLiveToast.js', 'js/cookieConsent.js', 'js/autocomplete.js', 'js/maximusTranslation.js', 'js/scrollTopButton.js', 'js/hiddenNavbarScroll.js',
    filters='jsmin', 
    output='gen/base_packed.js')

assets.register('css_base', css_base)
assets.register('js_base', js_base)

# Home template bundles
js_home = Bundle(
    'js/amcharts/map.js', 'js/amcharts/worldLow.js', 'js/amcharts/animated.js', 'js/chart.js', 
    filters='jsmin', 
    output='gen/home_packed.js')
assets.register('js_home', js_home)

# News template bundles
js_news = Bundle(
    'js/submitSearch.js', 'js/newsCardHeader.js', 'js/languageMenu.js', 'js/timeAgo.js',
    filters='jsmin', 
    output='gen/news_packed.js')
assets.register('js_news', js_news)


# Security - CSP Rules
csp = {
    'default-src': [
        '\'self\'',
    ],
    'img-src': [
        '\'self\'',
        'data:',
        'https://talk.hyvor.com', # Comments reactions
        'https://media.tenor.com', # gifs
        'https://hyvor.com', # Comments user picture
        'https://www.gstatic.com', # google images for translate
        'https://fonts.gstatic.com', # google translate icon
        'https://hatscripts.github.io',
        'https://cdn.jsdelivr.net' # flag images
    ],
    'connect-src': [
        '\'self\'',
        'https://api.tenor.com', # Gifs
        'https://talk.hyvor.com', # Comments
        'wss://soketi.hyvor.com', # Comments real-time socket connection
        'https://commento.io', # Commento
        'https://cloudflareinsights.com',
        'https://ka-f.fontawesome.com',
        'https://translate.googleapis.com'
    ], 
    'frame-src': [
        'https://challenges.cloudflare.com'
    ],
    'script-src': [
        '\'self\'',
        '\'unsafe-inline\'',
        'https://cdn.commento.io', # Commento
        'https://talk.hyvor.com', # Comments
        'https://ajax.cloudflare.com',
        'https://static.cloudflareinsights.com',
        'https://challenges.cloudflare.com',
        'https://kit.fontawesome.com',
        'https://translate.google.com',
        'https://translate.googleapis.com',
        'https://translate-pa.googleapis.com'
    ],
    'style-src': [
        '\'self\'',
        '\'unsafe-inline\'',
        'https://cdn.commento.io', # Commento
        'https://fonts.googleapis.com',
        'https://www.gstatic.com'
    ],
    'font-src': [
        '\'self\'',
        'https://ka-f.fontawesome.com',
        'https://cdn.commento.io' # Commento
    ]
}

talisman = Talisman(app, content_security_policy=csp)


def detect_mobile(request) -> bool:
    """Uses a request object to check if the user is using a mobile device or not. If mobile, return True. Else, return False."""
    user_agent = request.user_agent.string

    mobile_keywords = ('Mobile', 'Android', 'iPhone', 'iPod', 'iPad', 'BlackBerry', 'Phone')

    # Check if any of the mobile keywords appear in the user agent string
    for keyword in mobile_keywords:
        if keyword in user_agent:
            return True

    # If none of the keywords were found, it's likely not a mobile device
    return False


@app.context_processor
def inject_user():
    """This function will run before each template is rendered. We'll provide some variables to every template."""
    return dict(is_mobile=detect_mobile(request))


@app.errorhandler(404)
@app.errorhandler(413)
@app.errorhandler(500)
def error_handler(error):
    error_code = getattr(error, 'code', 500)

    if error_code == 413:
        error_message = 'Your file is too large.'
    else:
        error_message = f"We apologize, but {'the page you are looking for might have been removed, had its name changed or is temporarily unavailable.' if error_code == 404 else 'the server encountered an error and could not finish your request. Our team will work to address this issue as soon as possible. Meanwhile, feel free to send an email to <contact@infomundi.net> telling details about the error.'}"
    
    return render_template('error.html', error_code=error_code, error_message=error_message, page='Error'), error_code


# Runs in debug mode if called directly!
if __name__ == '__main__':
    app.run(debug=True)
