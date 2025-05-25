from flask import (
    Flask,
    render_template,
    request,
    send_from_directory,
    abort,
    g,
    session,
    flash,
    Response,
    jsonify,
)
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_login import current_user, logout_user
from flask_assets import Environment, Bundle
from htmlmin import minify as html_minify
from flask_wtf.csrf import CSRFProtect
from datetime import timedelta
from os import path as os_path

from website_scripts import (
    config,
    extensions,
    input_sanitization,
    security_util,
    hashing_util,
    qol_util,
    models,
    friends_util,
    notifications,
)
from views import views
from auth import auth
from api import api


app = Flask(__name__, static_folder="static")
app.config["WTF_CSRF_SECRET_KEY"] = config.SECRET_KEY
app.config["SECRET_KEY"] = config.SECRET_KEY

app.config["PREFERRED_URL_SCHEME"] = "https"

# Session Cookie Configuration
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=15)
app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=15)
app.config["SESSION_COOKIE_NAME"] = config.SESSION_COOKIE_NAME
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = True

# SQLAlchemy Configuration
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{config.MYSQL_USERNAME}:{config.MYSQL_PASSWORD}@{config.MYSQL_HOST}/{config.MYSQL_DATABASE}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
extensions.db.init_app(app)

# Cache
app.config["CACHE_REDIS_URL"] = config.REDIS_CONNECTION_STRING
app.config["CACHE_REDIS_DB"] = config.REDIS_DATABASE
app.config["CACHE_REDIS_HOST"] = config.REDIS_HOST
app.config["CACHE_REDIS_PORT"] = config.REDIS_PORT
app.config["CACHE_TYPE"] = "RedisCache"
extensions.cache.init_app(app)

# Uploads
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 Megabytes
app.config["UPLOAD_FOLDER"] = "static/img/users/"

# Blueprints
app.register_blueprint(auth, url_prefix="/auth")
app.register_blueprint(api, url_prefix="/api")
app.register_blueprint(views, url_prefix="/")

# Google OAuth
extensions.oauth.init_app(app)

# Rate Limiting
extensions.limiter.init_app(app)

socketio = SocketIO(app, cors_allowed_origins="*")  # Allow appropriate origins


@socketio.on("connect")
def handle_connect():
    """On client connect, join a personal room for private messaging."""
    if current_user.is_authenticated:
        room = f"user_{current_user.id}"
        join_room(room)
    else:
        return False  # Reject connection if not logged in


@socketio.on("disconnect")
def handle_disconnect():
    """On disconnect, optionally handle any cleanup."""
    if current_user.is_authenticated:
        room = f"user_{current_user.id}"
        leave_room(room)


@socketio.on("send_message")
def handle_send_message(data):
    """
    Handle an outgoing encrypted message.
    `data`: {'to': <friend_public_id>, 'message': <ciphertext_base64>}
    Saves the message and forwards it to the recipient.
    """
    if not current_user.is_authenticated:
        return
    friend_uuid = data.get("to")
    ciphertext = data.get("message")
    friend = models.User.query.filter_by(
        public_id=security_util.uuid_string_to_bytes(friend_uuid)
    ).first()
    if not friend:
        return

    # Makes sure the users are friends
    friendship_status = friends_util.get_friendship_status(current_user.id, friend.id)[
        0
    ]
    if friendship_status != "accepted":
        return

    # Store the encrypted message in the database
    new_msg = models.Message(
        sender_id=current_user.id, receiver_id=friend.id, content_encrypted=ciphertext
    )
    extensions.db.session.add(new_msg)
    extensions.db.session.commit()
    notifications.post_webhook("sending message")
    # Emit the message to the receiver's room for real-time delivery
    emit(
        "receive_message",
        {
            "from": current_user.get_public_id(),
            "message": ciphertext,
            "timestamp": new_msg.timestamp.isoformat(),
        },
        room=f"user_{friend.id}",
    )


@socketio.on("typing")
def handle_typing(data):
    """
    data = {'to': <friend_public_id>, 'typing': bool}
    Forward the typing signal to the recipient’s personal room.
    """
    if not current_user.is_authenticated:
        return

    friend_uuid = data.get("to")
    is_typing = bool(data.get("typing", True))

    friend = models.User.query.filter_by(
        public_id=security_util.uuid_string_to_bytes(friend_uuid)
    ).first()
    if not friend:
        return

    friendship_status = friends_util.get_friendship_status(current_user.id, friend.id)[
        0
    ]
    if friendship_status != "accepted":
        return

    emit(
        "typing",
        {"from": current_user.get_public_id(), "typing": is_typing},
        room=f"user_{friend.id}",
    )


@app.route("/<filename>")
def serve_file(filename):
    if filename not in (
        "ads.txt",
        "favicon.ico",
        "robots.txt",
        "security.txt",
        "pubkey.asc",
        "sitemap.xml",
        "countries.xml",
    ):
        abort(404)

    if filename.endswith(".xml"):
        mimetype = "text/xml"
    elif filename == "favicon.ico":
        mimetype = "image/x-icon"
    else:
        mimetype = "text/plain"

    return send_from_directory(
        os_path.join(app.root_path, "static"), filename, mimetype=mimetype
    )


# CSRF Configuration
csrf = CSRFProtect(app)
csrf.exempt("api.story_reaction")  # Remove protection to story reaction api

# Login manager
extensions.login_manager.init_app(app)
extensions.login_manager.login_view = "auth.login"


@extensions.login_manager.user_loader
def load_user(user_id):
    return extensions.db.session.get(models.User, user_id)


@app.before_request
def set_nonce():
    # Generates nonce to be used in the CSP
    g.nonce = security_util.generate_nonce()


@app.before_request
@extensions.cache.cached(
    timeout=300,
    key_prefix=(
        current_user.id if (current_user and current_user.is_authenticated) else "guest"
    ),
)
def check_session_version():
    # We check the session version every 5 minutes, to see if session is valid.
    if current_user.is_authenticated:
        user = extensions.db.session.get(models.User, current_user.id)

        session_version = session.get("session_version")
        if session_version and session_version != user.session_version:
            flash(f"We hope to see you again soon, {current_user.username}")

            if "email_address" in session:
                del session["email_address"]
            session.permanent = False

            logout_user()


@app.after_request
def add_headers(response):
    nonce = g.get("nonce", "")

    # Sets the CSP header to include the nonce
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' https://*.infomundi.net; "
        "img-src https: data:; "
        "connect-src 'self' wss://*.infomundi.net https://*.infomundi.net https://pagead2.googlesyndication.com https://csi.gstatic.com https://translate.googleapis.com https://translate-pa.googleapis.com https://cloudflareinsights.com; "
        "frame-src 'self' https://*.infomundi.net https://challenges.cloudflare.com https://translate.googleapis.com https://googleads.g.doubleclick.net https://tpc.googlesyndication.com https://pagead2.googlesyndication.com https://www.google.com; "
        f"script-src 'self' 'strict-dynamic' 'nonce-{nonce}'; "
        "style-src 'self' 'unsafe-inline' https://*.infomundi.net https://fonts.googleapis.com https://www.gstatic.com; "
        "base-uri 'self' https://*.infomundi.net; "
        "font-src 'self' https://fonts.gstatic.com https://*.infomundi.net; "
        "frame-ancestors 'self' https://*.infomundi.net"
    )

    if request.path.startswith("/static"):
        # Set Cache-Control header for static files
        response.headers["Cache-Control"] = "public, max-age=2592000"  # 30 days

    return response


@app.after_request
def minify_html(response: Response) -> Response:
    if response.content_type == "text/html; charset=utf-8":
        response.set_data(
            html_minify(
                response.get_data(as_text=True),
                remove_comments=True,
                remove_empty_space=True,
            )
        )
    return response


# base.html
css_base = Bundle(
    "css/main.css",
    "css/navbar.css",
    "css/ticker.css",
    "fontawesome/css/all.min.css",
    "fontawesome/css/fontawesome.min.css",
    "css/libs/cookieconsent.css",
    filters="cssmin",
    output="gen/base_packed.css",
)
# base.html
js_base = Bundle(
    "js/libs/lazysizes.min.js",
    "js/themeButton.js",
    "js/triggerTooltip.js",
    "js/tickerSpeedUp.js",
    "js/triggerLiveToast.js",
    "js/autocomplete.js",
    "js/scrollTopButton.js",
    "js/hiddenNavbarScroll.js",
    "js/libs/cookieconsent-3.0.1.js",
    "js/cookieConsent.js",
    "js/linkSafety.js",
    "js/autoSubmitCaptcha.js",
    "js/captchaWaitSubmit.js",
    "js/renderFriendsModal.js",
    filters="jsmin",
    output="gen/base_packed.js",
)
# homepage.html
js_home = Bundle(
    "js/amcharts/map.js",
    "js/amcharts/worldLow.js",
    "js/amcharts/animated.js",
    "js/chart.js",
    filters="jsmin",
    output="gen/home_packed.js",
)
# news.html
js_news = Bundle("js/renderStories.js", filters="jsmin", output="gen/news_packed.js")

assets = Environment(app)
assets.register("css_base", css_base)
assets.register("js_base", js_base)
assets.register("js_home", js_home)
assets.register("js_news", js_news)


@app.context_processor
def inject_variables():
    """This function will run before each template is rendered. We'll provide some variables to every template."""
    return dict(
        is_mobile=qol_util.is_mobile(request),
        nonce=g.get("nonce", ""),
        referer=input_sanitization.is_safe_url(request.headers.get("referer", "")),
        is_light_mode=False if request.cookies.get("theme", "") == "dark" else True,
    )


@app.errorhandler(500)
@app.errorhandler(429)
@app.errorhandler(404)
def error_handler(error):
    # Gets the error code, defaults to 500
    error_code = getattr(error, "code", 500)

    if error_code == 404:
        title = "Page Not Found"
        description = "It seems you've stumbled upon a page that even the ancient Greek philosophers couldn't find! Our esteemed statue is deep in thought, pondering over an ancient scroll, but the wisdom to locate this page eludes even him."
        image_path = "/static/img/illustrations/scroll.webp"

        buttons_enabled = True
    elif error_code == 429:
        return (
            jsonify(
                {
                    "response": f"We need to breath! Your lightning-fast requests have exceeded the rate limit. The limit is: {str(error.description)}",
                }
            ),
            429,
        )
    else:
        title = "Internal Server Error"
        description = "While we pick up the pieces, why not explore other parts of the site? We'll have this page standing tall again soon!"
        image_path = "/static/img/illustrations/ruins.webp"

        buttons_enabled = True

    contents = (title, description, image_path)
    return (
        render_template(
            "error.html",
            contents=contents,
            buttons_enabled=buttons_enabled,
            error_code=error_code,
        ),
        error_code,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0")
