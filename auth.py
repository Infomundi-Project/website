from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    g,
    abort,
)
from flask_login import login_required, current_user, logout_user
from datetime import datetime

from website_scripts import (
    extensions,
    models,
    input_sanitization,
    auth_util,
    hashing_util,
    qol_util,
    security_util,
    decorators,
)

auth = Blueprint("auth", __name__)


@auth.route("/login", methods=["GET", "POST"])
@decorators.unauthenticated_only
@decorators.verify_turnstile
@extensions.limiter.limit("20/minute")
def login():
    # If user is in totp process, redirect them to the correct page
    if session.get("in_twofactor_process", ""):
        return redirect(url_for("auth.totp"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    session["remember_me"] = request.form.get("remember_me", "") == "yes"

    # To avoid making unecessary queries to the database, first check to see if the credentials match our standards
    if not input_sanitization.is_valid_email(
        email
    ) or not input_sanitization.is_strong_password(password):
        flash("Invalid credentials!", "error")
        return render_template("login.html")

    user = auth_util.search_user_email_in_database(email)
    if not user or not user.check_password(password) or not user.is_enabled:
        flash("Invalid credentials!", "error")
        return render_template("login.html")

    # If user has totp enabled, we redirect them to the totp page without effectively performing log in actions
    if user.is_totp_enabled or user.is_mail_twofactor_enabled:
        session["email_address"] = email
        session["username"] = user.username
        session["user_id"] = user.id
        session["in_twofactor_process"] = True
        return redirect(url_for("auth.totp"))

    auth_util.perform_login_actions(user, email)
    flash(f"Welcome back, {user.username}!")
    return redirect(url_for("views.user_profile", username=user.username))


@auth.route("/totp", methods=["GET", "POST"])
@decorators.check_twofactor
def totp():
    user = extensions.db.session.get(models.User, session["user_id"])

    if session.get("is_valid_twofactor", ""):
        auth_util.perform_login_actions(user, session["email_address"])
        del session["is_valid_twofactor"]
        return redirect(url_for("views.user_profile", username=user.username))

    if request.method == "GET":
        return render_template("twofactor.html", user=user)


@auth.route("/reset_totp", methods=["GET"])
def reset_totp():
    if not session.get("in_twofactor_process", ""):
        return abort(404)

    del session["in_twofactor_process"]
    del session["user_id"]

    return redirect(url_for("views.home"))


@auth.route("/disable_totp", methods=["POST"])
@login_required
def disable_totp():
    current_user.purge_totp()
    flash("You removed your two factor authentication!")
    return redirect(url_for("views.edit_user_settings"))


@auth.route("/register", methods=["GET", "POST"])
@decorators.unauthenticated_only
@decorators.verify_turnstile
def register():
    if request.method == "GET":
        return render_template("register.html")

    # Checks if email is valid
    email = request.form.get("email", "").strip()
    if not input_sanitization.is_valid_email(email):
        flash("We apologize, but your email address format is invalid.", "error")
        return redirect(url_for("auth.register"))

    # Checks if username is valid
    username = request.form.get("username", "").strip()
    if not input_sanitization.is_valid_username(username):
        flash(
            "We apologize, but your username is invalid. Must be 3-25 characters long and contain only letters, numbers, underscores, or hyphens.",
            "error",
        )
        return redirect(url_for("auth.register"))

    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if password != confirm_password:
        flash("Password and confirm password must match!", "error")
        return redirect(url_for("auth.register"))

    if not input_sanitization.is_strong_password(password):
        flash(
            "We apologize, but the password does not meet complexity requirements.",
            "error",
        )
        return redirect(url_for("auth.register"))

    auth_util.handle_register_token(email, username, password)

    flash(
        f"If everything went smoothly, you should soon receive instructions in your inbox at {email}"
    )
    return redirect(url_for("auth.register"))


@auth.route("/verify", methods=["GET"])
@decorators.unauthenticated_only
def verify():
    token = request.args.get("token", "")
    if not token:
        flash("Invalid token", "error")
        return redirect(url_for("auth.register"))

    user = models.User.query.filter_by(
        register_token=security_util.uuid_string_to_bytes(token)
    ).first()
    if not user:
        flash("We apologize, but the token seems to be invalid.", "error")
        return redirect(url_for("views.home"))

    # Checks if the token is expired
    created_at = datetime.fromisoformat(user.register_token_timestamp.isoformat())
    if not qol_util.is_date_within_threshold_minutes(created_at, 30):
        extensions.db.session.delete(user)
        extensions.db.session.commit()

        flash(
            "We apologize, but the token has expired. Please, try registering your account again.",
            "error",
        )
        return redirect(url_for("auth.register"))

    user.enable()
    flash(f"Your account has been verified, {user.username}! You may log in now!")
    return redirect(url_for("auth.login"))


@auth.route("/invalidate_sessions", methods=["POST"])
@login_required
def invalidate_sessions():
    current_user.session_version += 1
    session["session_version"] = (
        current_user.session_version
    )  # So the user won't have to log in again
    extensions.db.session.commit()

    flash("All sessions have been invalidated.")
    return redirect(url_for("views.user_redirect"))


@auth.route("/forgot_password", methods=["GET", "POST"])
@decorators.unauthenticated_only
@decorators.verify_turnstile
def forgot_password():
    if request.method == "GET":
        recovery_token = request.args.get("token", "")
        if not recovery_token:
            return render_template("forgot_password.html")

        user = auth_util.check_recovery_token(recovery_token)
        if not user:
            flash("We apologize, but the token seems to be invalid.", "error")
            return render_template("forgot_password.html")

        auth_util.perform_login_actions(
            user, security_util.decrypt(user.email_encrypted)
        )
        decorators.set_session_trusted()

        flash("Success! You may be able to change your password now.")
        return redirect(url_for("views.edit_user_settings"))

    email = request.form.get("email", "").lower().strip()
    if not input_sanitization.is_valid_email(email):
        flash("We apologize, but your email address format is invalid.", "error")
        return render_template("forgot_password.html")

    # Tries to send the recovery token to the user
    auth_util.send_recovery_token(email)

    # Generic message to prevent user enumeration
    flash(
        f"If {email} happens to be in our database, an email will be sent with instructions."
    )
    return render_template("forgot_password.html")


@auth.route("/delete", methods=["GET", "POST"])
@login_required
def account_delete():
    user_email = session.get("email_address", "")

    if request.method == "GET":
        token = request.args.get("token", "")
        if not auth_util.delete_account(user_email, token):
            flash(
                "Something went wrong, perhaps your token is invalid or expired",
                "error",
            )
            return redirect(url_for("views.user_redirect"))

        flash("Your account has been deleted.")
        return redirect(url_for("views.user_redirect"))

    if not auth_util.send_delete_token(user_email):
        flash("You already have a delete token associated with your account.", "error")
        return redirect(url_for("views.user_redirect"))

    flash(
        f"We've sent an email with instructions to your email address at {session.get('obfuscated_email_address', '')}."
    )
    return redirect(url_for("views.user_redirect"))


@auth.route("/google_redirect", methods=["GET"])
@decorators.unauthenticated_only
def google_redirect():
    nonce = g.nonce
    session["nonce"] = nonce

    redirect_uri = url_for("auth.google_callback", _external=True)
    return extensions.google.authorize_redirect(redirect_uri, nonce=nonce)


@auth.route("/google", methods=["GET"])
@decorators.unauthenticated_only
def google_callback():
    token = extensions.google.authorize_access_token()
    user_info = extensions.google.parse_id_token(token, nonce=session["nonce"])

    # Get user details
    display_name = input_sanitization.sanitize_text(user_info["name"])
    username = input_sanitization.create_username_out_of_display_name(display_name)
    email_fingerprint = hashing_util.generate_hmac_signature(
        user_info["email"], as_bytes=True
    )
    email_encrypted = security_util.encrypt(user_info["email"])

    # If the user is not already in the database, we create an entry for them
    user = auth_util.search_user_email_in_database(user_info["email"])
    if not user:
        # The user can only log in using google integration
        user = models.User(
            public_id=security_util.generate_uuid_bytes(),
            display_name=display_name,
            username=username,
            password=hashing_util.string_to_argon2_hash(security_util.generate_nonce()),
            email_fingerprint=email_fingerprint,
            email_encrypted=email_encrypted,
            is_thirdparty_auth=True,
            is_enabled=True,
        )
        extensions.db.session.add(user)
        extensions.db.session.commit()

    auth_util.perform_login_actions(user, user_info["email"])

    flash(f"Hello, {user.username}! Welcome to Infomundi!")
    return redirect(url_for("views.home"))


@auth.route("/logout", methods=["GET"])
@login_required
def logout():
    flash(f"We hope to see you again soon, {current_user.username}")
    session.permanent = False
    session.clear()
    logout_user()
    return redirect(url_for("auth.login"))
