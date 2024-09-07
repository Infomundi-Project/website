import os
from flask import Flask, render_template, request, send_from_directory, abort, g, session, flash, redirect, url_for
from flask_login import LoginManager, current_user, logout_user
from flask_assets import Environment, Bundle
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from datetime import timedelta

from website_scripts.config import MYSQL_USERNAME, MYSQL_PASSWORD, REDIS_CONNECTION_STRING, SECRET_KEY
from website_scripts.extensions import db, login_manager, cache, oauth, limiter
from website_scripts.input_sanitization import is_safe_url
from website_scripts.security_util import generate_nonce
from website_scripts.decorators import admin_required
from website_scripts.qol_util import is_mobile
from website_scripts.models import User

from views import views
from auth import auth
from api import api


app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = SECRET_KEY
app.config['WTF_CSRF_SECRET_KEY'] = app.config['SECRET_KEY']  # Optional but recommended

app.config['PREFERRED_URL_SCHEME'] = 'https'

# Session Cookie Configuration
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=15)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=15)
app.config['SESSION_COOKIE_NAME'] = 'infomundi-session'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True

# SQLAlchemy Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{MYSQL_USERNAME}:{MYSQL_PASSWORD}@localhost/infomundi'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Cache
app.config['CACHE_TYPE'] = 'RedisCache'
app.config['CACHE_REDIS_HOST'] = 'localhost'
app.config['CACHE_REDIS_PORT'] = 6379
app.config['CACHE_REDIS_DB'] = 0
app.config['CACHE_REDIS_URL'] = REDIS_CONNECTION_STRING
cache.init_app(app)

# Rate Limiting
limiter.init_app(app)

# Uploads
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 Megabytes
app.config['UPLOAD_FOLDER'] = 'static/img/users/'

# Blueprints
app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(api, url_prefix='/api')
app.register_blueprint(views, url_prefix='/')

# Google OAuth
oauth.init_app(app)


def is_safe_path(basedir, path, follow_symlinks=False):
    # Resolves the absolute path and ensures it is within the base directory
    if follow_symlinks:
        return os.path.realpath(path).startswith(basedir)
    return os.path.abspath(path).startswith(basedir)


@app.route('/download-backup/<filename>', methods=['GET'])
@admin_required
def download_backup(filename):
    BACKUP_DIRECTORY = '/var/www/infomundi/backups'
    try:
        # Securely join the directory and the requested file
        file_path = os.path.join(BACKUP_DIRECTORY, filename)
        
        # Ensure the file is within the backup directory
        if is_safe_path(BACKUP_DIRECTORY, file_path) and (filename.endswith('.enc') or filename == 'backup_log.txt'):
            # Ensure the file exists
            if os.path.exists(file_path):
                return send_from_directory(BACKUP_DIRECTORY, filename, as_attachment=True)
            else:
                abort(404)  # Not Found

        # If not valid, abort
        abort(403)

    except Exception as e:
        # Internal Server Error
        abort(500)


@app.route('/ads.txt')
def ads_txt():
    return send_from_directory(os.path.join(app.root_path, 'static'),
        'ads.txt', mimetype='text/plain')


@app.route('/robots.txt')
def robots_txt():
    return send_from_directory(os.path.join(app.root_path, 'static'),
        'robots.txt', mimetype='text/plain')


@app.route('/security.txt')
def security_txt():
    return send_from_directory(os.path.join(app.root_path, 'static'),
        'security.txt', mimetype='text/plain')


@app.route('/pubkey.asc')
def pubkey_asc():
    return send_from_directory(os.path.join(app.root_path, 'static'),
        'pubkey.asc', mimetype='text/plain')


# CSRF Configuration
csrf = CSRFProtect(app)
# Remove protection to endpoint --> csrf.exempt('api.comments')

# Login manager
login_manager.init_app(app)
login_manager.login_view = 'auth.login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.before_request
def set_nonce():
    g.nonce = generate_nonce()


@app.before_request
@cache.cached(timeout=60, key_prefix=current_user.user_id if (current_user and current_user.is_authenticated) else 'guest') # 1 minute
def check_session_version():
    if current_user.is_authenticated:
        user = User.query.get(current_user.user_id)
        
        session_version = session.get('session_version')
        if session_version and session_version != user.session_version:
            flash(f'We hope to see you again soon, {current_user.username}')

            if 'email_address' in session:
                del session['email_address']
            session.permanent = False

            logout_user()


@app.after_request
def add_csp_header(response):
    nonce = g.get('nonce', '')

    # https://pagead2.googlesyndication.com https://tpc.googlesyndication.com https://commento.infomundi.net https://static.cloudflareinsights.com https://translate-pa.googleapis.com https://translate.googleapis.com https://challenges.cloudflare.com https://ajax.cloudflare.com https://kit.fontawesome.com https://translate.google.com; 
    # Sets the CSP header to include the nonce
    response.headers['Content-Security-Policy'] = (
        "default-src 'self' https://*.infomundi.net; "
        "img-src https: data:; "

        "connect-src 'self' wss://*.infomundi.net https://*.infomundi.net https://pagead2.googlesyndication.com https://csi.gstatic.com https://translate.googleapis.com https://translate-pa.googleapis.com https://cloudflareinsights.com; "

        "frame-src 'self' https://*.infomundi.net https://challenges.cloudflare.com https://translate.googleapis.com https://googleads.g.doubleclick.net https://tpc.googlesyndication.com https://pagead2.googlesyndication.com https://www.google.com; "
        
        f"script-src 'self' 'strict-dynamic' 'nonce-{nonce}'; "

        "style-src 'self' 'unsafe-inline' https://*.infomundi.net https://fonts.googleapis.com https://www.gstatic.com; "
        
        "base-uri 'self' https://*.infomundi.net; "
        "font-src 'self' https://*.infomundi.net"
    )
    
    return response


@app.after_request
def add_cache_header(response):
    if request.path.startswith('/static'):
        # Set Cache-Control header for static files
        response.headers['Cache-Control'] = 'public, max-age=2592000'  # 30 days

    return response


# base.html
css_base = Bundle(
    'css/main.css', 'css/navbar.css', 'css/ticker.css', 
    filters='cssmin', 
    output='gen/base_packed.css')
# base.html
js_base = Bundle(
    'js/lazysizes.min.js', 'js/themeButton.js', 'js/triggerTooltip.js', 'js/tickerSpeedUp.js', 'js/initGoogleTranslate.js', 'js/triggerLiveToast.js', 'js/autocomplete.js', 'js/maximusTranslation.js', 'js/scrollTopButton.js', 'js/hiddenNavbarScroll.js', 'js/libs/cookieconsent-3.0.1.js', 'js/cookieConsent.js', 'js/linkSafety.js',
    filters='jsmin', 
    output='gen/base_packed.js')
# homepage.html
js_home = Bundle(
    'js/amcharts/map.js', 'js/amcharts/worldLow.js', 'js/amcharts/animated.js', 'js/chart.js', 
    filters='jsmin', 
    output='gen/home_packed.js')
# rss_template.html
js_news = Bundle(
    'js/submitSearch.js', 'js/languageMenu.js', 
    filters='jsmin', 
    output='gen/news_packed.js')

assets = Environment(app)
assets.register('css_base', css_base)
assets.register('js_base', js_base)
assets.register('js_home', js_home)
assets.register('js_news', js_news)


@app.context_processor
def inject_variables():
    """This function will run before each template is rendered. We'll provide some variables to every template."""
    referer = is_safe_url(request.headers.get('referer', ''))
    return dict(is_mobile=is_mobile(request), nonce=g.get('nonce', ''), referer=referer)


@app.errorhandler(404)
@app.errorhandler(429)
@app.errorhandler(500)
def error_handler(error):
    # Gets the error code, defaults to 500
    error_code = getattr(error, 'code', 500)

    if error_code == 404:
        title = 'Page Not Found'
        description = "It seems you've stumbled upon a page that even the ancient Greek philosophers couldn't find! Our esteemed statue is deep in thought, pondering over an ancient scroll, but the wisdom to locate this page eludes even him."
        image_path = 'https://infomundi.net/static/img/illustrations/scroll.webp'

        buttons_enabled = True
    elif error_code == 429:
        title = 'Too Many Requests'
        description = f"Even Greek gods can’t handle this much paperwork! It looks like our server is feeling a bit overwhelmed. Give it a moment to catch its breath, and try again soon. Trust us, it’s working hard to process all your requests!"
        image_path = 'https://infomundi.net/static/img/illustrations/struggling.webp'

        buttons_enabled = False
    elif error_code == 500:
        title = "Internal Server Error"
        description = "While we pick up the pieces, why not explore other parts of the site? We'll have this page standing tall again soon!"
        image_path = 'https://infomundi.net/static/img/illustrations/ruins.webp'

        buttons_enabled = True
    
    contents = (title, description, image_path)
    return render_template('error.html', contents=contents, buttons_enabled=buttons_enabled, error_code=error_code), error_code


if __name__ == '__main__':
    app.run(debug=False)
