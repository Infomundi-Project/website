from flask import flash, redirect, url_for, session, request, abort, jsonify
from flask_login import current_user
from datetime import datetime
from functools import wraps

from . import extensions, qol_util, cloudflare_util, config, models


def admin_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and current_user.role == "admin":
            return func(*args, **kwargs)

        return abort(404)

    return decorated_function


def api_login_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated:
            return func(*args, **kwargs)

        return jsonify({"message": "You must be logged in."}), 403

    return decorated_function


def unauthenticated_only(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        # Check if the user is an authenticated
        if not current_user.is_authenticated:
            return func(*args, **kwargs)

        flash("You are already authenticated!", "error")
        return redirect(url_for("views.home"))

    return decorated_function


def in_maintenance(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        # If the user is admin, maintenance is bypassed
        if current_user.is_authenticated and current_user.role == "admin":
            return func(*args, **kwargs)

        return redirect(url_for("views.be_right_back"))

    return decorated_function


def captcha_required(func):
    """This decorator is used to check if the user needs to resolve a proof of life first."""

    @wraps(func)
    def decorated_function(*args, **kwargs):
        clearance = session.get("clearance", "")
        if clearance:
            timestamp = datetime.fromisoformat(clearance)
            if qol_util.is_date_within_threshold_minutes(
                timestamp, config.CAPTCHA_CLEARANCE_HOURS, is_hours=True
            ):
                return func(*args, **kwargs)

        session["clearance_from"] = request.url
        return redirect(url_for("views.captcha"))

    return decorated_function


def verify_captcha(func):
    """This decorator is used to check if a captcha token is valid"""

    @wraps(func)
    def decorated_function(*args, **kwargs):
        if request.method == "POST":
            token = request.form.get("cf-turnstile-response", "")
            if not cloudflare_util.is_valid_captcha(token):
                flash("Invalid captcha. Are you a robot?", "error")
                return redirect(request.url)

        # If captcha is valid, return the function as usual
        return func(*args, **kwargs)

    return decorated_function


def sensitive_area(func):
    """This decorator is used to check if the user is allowed to access their account's sensitive area"""

    @wraps(func)
    def decorated_function(*args, **kwargs):
        is_trusted_session = session.get("is_trusted_session", "")
        if is_trusted_session:
            return func(*args, **kwargs)

        return redirect(url_for("views.sensitive"))

    return decorated_function


def check_twofactor(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if request.method == "POST":
            user = extensions.db.session.get(models.User, session["user_id"])

            recovery_token = request.form.get("recovery_token", "").strip()
            password = request.form.get("password", "").strip()
            code = request.form.get("code", "").strip()

            if user.is_totp_enabled:
                is_valid = user.check_totp(code, recovery_token)
            elif user.is_mail_twofactor_enabled:
                is_valid = user.check_mail_twofactor(code, recovery_token)
            else:
                is_valid = user.check_password(password)

            if not is_valid:
                flash("Invalid credentials!", "error")
                return redirect(request.url)

            if session.get("in_twofactor_process", ""):
                del session["in_twofactor_process"]

            session["is_valid_twofactor"] = True

        return func(*args, **kwargs)

    return decorated_function
