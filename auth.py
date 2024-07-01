import time, hmac, hashlib, binascii, json
from flask import Blueprint, render_template, request, redirect, jsonify, url_for, flash, session
from flask_login import login_user, login_required, current_user, logout_user
from datetime import datetime, timedelta
from passlib.hash import argon2
from functools import wraps
from random import uniform

from website_scripts import config, json_util, scripts, immutable, extensions, models

auth_views = Blueprint('auth', __name__)


def admin_required(func):
    """This decorator is used to check if the user is an admin."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        # Check if the user is an admin based on the role
        if current_user.is_authenticated and current_user.role == 'admin':
            return func(*args, **kwargs)
        
        flash('This page is restricted.', 'error')
        return redirect(url_for('views.home'))

    return decorated_function


def in_maintenance(func):
    """This decorator is used when the endpoint is in maintenance."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        # If the user is admin, maintenance is bypassed
        if current_user.is_authenticated and current_user.role == 'admin' and current_user.username == 'behindsecurity':
            return func(*args, **kwargs)
        
        return redirect(url_for('views.be_right_back'))

    return decorated_function


def captcha_required(func):
    """This decorator is used to check if the user needs to resolve a proof of life first."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        clearance = session.get('clearance', '')
        if clearance:
            now = datetime.now()
            
            time_difference = now - datetime.fromisoformat(clearance)
            if time_difference < timedelta(hours=config.CAPTCHA_CLEARANCE_HOURS):
                return func(*args, **kwargs)
        
        session['clearance_from'] = request.url
        return redirect(url_for('views.captcha'))

    return decorated_function


@auth_views.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('You are already logged in!')
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        # Checks if captcha token is valid
        token = request.form['cf-turnstile-response']
        if not scripts.valid_captcha(token):
            flash('Invalid captcha. Are you a robot?', 'error')
            return redirect(url_for('auth.register'))
        
        # Checks if email is valid
        email = request.form.get('email', '').lower().strip()
        if not scripts.is_valid_email(email):
            flash('Invalid email address.', 'error')
            return redirect(url_for('auth.register'))

        # Collects user input
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        hashed_email = scripts.sha256_hash_text(email)

        # Is email already present?
        email_lookup = models.User.query.filter_by(email=hashed_email).first()
        
        # Is username already present?
        username_lookup = models.User.query.filter_by(username=username).first()

        token_username_lookup = models.RegisterToken.query.filter_by(username=username).first()
        if token_username_lookup:
            now = datetime.now()
            created_at = datetime.fromisoformat(token_username_lookup.timestamp.isoformat())
            
            # Checks if the token is expired. If it's expired, we clear it from the database, commit change and return False
            time_difference = now - created_at
            if time_difference > timedelta(minutes=30):
                extensions.db.session.delete(token_username_lookup)
                extensions.db.session.commit()
                token_username_lookup = None

        if password != confirm_password:
            message = 'The passwords don\'t match.'
        elif not scripts.is_valid_username(username):
            message = 'Your username is invalid. The username must have at least 3 characters and 50 characters at most.'
        elif not scripts.is_strong_password(password):
            message = 'Password Policy: The password must have at least 8 characters and a maximum and 50 characters at most.'
        elif email_lookup:
            message = 'Email already exists.'
        elif username_lookup or token_username_lookup:
            message = 'Username already exists.'
        else:
            message = ''
        
        if message:
            flash(message, 'error')
            return redirect(url_for('auth.register'))

        # Sanitize username, just in case
        username = scripts.sanitize_input(username)

        # Tries to send a verification email to the user.
        send_token = scripts.handle_register_token(email, hashed_email, 
            username, argon2.hash(password))
        if not send_token:
            flash('We apologize, but something went wrong. Please, try again later.', 'error')
            scripts.log(f'[!] Not able to send verification token to {email}.')
            
            return redirect(url_for('auth.register'))

        flash(f'We sent an email with activation instructions to your address at {email}')
    
    return render_template('register.html')


@auth_views.route('/verify', methods=['GET'])
def verify():
    token = request.args.get('token', '')
    if not token or current_user.is_authenticated:
        return redirect(url_for('views.home'))

    if not scripts.has_md5_hash(token):
        flash('We apologize, but the token seems to be invalid.', 'error')
        return redirect(url_for('views.home'))

    # Tries to find the token in the database
    token_lookup = models.RegisterToken.query.filter_by(token=token).first()
    if not token_lookup:
        flash('We apologize, but the token was not found in our database. Try again.', 'error')
        return redirect(url_for('views.home'))

    now = datetime.now()
    created_at = datetime.fromisoformat(token_lookup.timestamp.isoformat())
    
    # Checks if the token is expired
    time_difference = now - created_at
    if time_difference > timedelta(minutes=30) or models.User.query.filter_by(email=token_lookup.email).first():
        extensions.db.session.delete(token_lookup)
        extensions.db.session.commit()
        
        flash('Either the token has expired or the user associated with this token already exists in our system. Try logging in or creating your account.', 'error')
        return redirect(url_for('views.home'))
    
    # Creates the new user and commits changes to the database
    new_user = models.User(user_id=token_lookup.user_id, username=token_lookup.username, password=token_lookup.password, role='user', email=token_lookup.email, avatar_url='https://infomundi.net/static/img/avatar.webp')
    extensions.db.session.add(new_user)
    
    extensions.db.session.delete(token_lookup)
    extensions.db.session.commit()

    flash(f'Your account has been verified, {token_lookup.username}! You may log in now!')
    return redirect(url_for('auth.login'))


@auth_views.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        flash(f'Hey {current_user.username}, you are already authenticated!')
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        turnstile = request.form['cf-turnstile-response']
        if not scripts.valid_captcha(turnstile):
            flash('Invalid captcha. Are you a robot?', 'error')
            return render_template('forgot_password.html')
        
        email = request.form.get('email', '').lower()
        if not email:
            flash('Something went wrong.', 'error')
            return render_template('forgot_password.html')

        # Sleeps for a random time in order to prevent user enumeration based on response time.
        time.sleep(uniform(1.0, 4.0))

        # Tries to send the recovery token to the user
        scripts.send_recovery_token(email, scripts.sha256_hash_text(email))

        # Generic error message to prevent user enumeration
        flash(f"If {email} is in our database, an email will be sent with instructions.")

    token = request.args.get('token', '')
    if token:
        result = scripts.check_recovery_token(token)
        if result:
            login_user(result)

            flash('Success! You may be able to change your password now.')
            return redirect(url_for('auth.password_change'))

        flash('We apologize, but the token is invalid.', 'error')
        
    return render_template('forgot_password.html')


@auth_views.route('/password_change', methods=['GET', 'POST'])
@login_required
def password_change():
    if request.method == 'POST':
        # Checks if captcha is valid
        token = request.form.get('cf-turnstile-response', '')
        if not scripts.valid_captcha(token):
            flash('Invalid captcha. Are you a robot?', 'error')
            return redirect(url_for('auth.password_change'))
        
        # Get form data
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        user = models.User.query.filter_by(email=current_user.email).first()
        if not current_user.in_recovery and not user.check_password(old_password):
            message = 'Incorrect old password.'
        elif new_password != confirm_password:
            message = 'Passwords must match!'
        elif not scripts.is_strong_password(new_password):
            message = "Password Policy: The password's character count must be between 8 and 50 characters."
        else:
            message = ''

        if message:
            flash(message, 'error')
            return redirect(url_for('auth.password_change'))
        
        # Update the user's password
        user.password = argon2.hash(new_password)
        user.in_recovery = False
        extensions.db.session.commit()
        
        logout_user()

        flash(f'Your password has been updated, {user.username}. You may log in now.')
        return redirect(url_for('auth.login'))
    
    return render_template('password_change.html')


@auth_views.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash('You are already logged in!')
        return redirect(url_for('views.home'))
    
    if request.method == 'POST':
        token = request.form.get('cf-turnstile-response', '')
        if not scripts.valid_captcha(token):
            flash('Invalid captcha. Are you a robot?', 'error')
            return redirect(url_for('auth.login'))

        email = request.form.get('email', '', type=str)
        password = request.form.get('password', '', type=str)

        if len(password) < 8 or not email:
            flash('Invalid credentials!', 'error')
            return redirect(url_for('auth.login'))

        # Hash the email address before querying
        user = models.User.query.filter_by(email=scripts.sha256_hash_text(email)).first()
        if user and user.check_password(password):
            # Save the timestamp of the last login
            user.last_login = datetime.now()
            extensions.db.session.commit()

            remember_me = bool(request.form.get('remember_me', ''))
            login_user(user, remember=remember_me)
            
            session.permanent = True
            session['email_address'] = email
            
            flash(f'Welcome back, {current_user.username}!')
            return redirect(url_for('views.home'))

        flash('Invalid credentials!', 'error')
    
    return render_template('login.html')


@auth_views.route('/commento')
@login_required
def commento():
    token = request.args.get("token", '', type=str)
    received_hmac_hex = request.args.get("hmac", '', type=str)

    if not token or not received_hmac_hex:
        return "Missing token or hmac", 400

    secret_key = binascii.unhexlify(config.COMMENTO_SSO_KEY)

    # Validate HMAC
    expected_hmac = hmac.new(secret_key, binascii.unhexlify(token), hashlib.sha256).digest()
    if not hmac.compare_digest(binascii.unhexlify(received_hmac_hex), expected_hmac):
        return "Invalid HMAC", 403

    payload = {
        "token": token,
        "email": session['email_address'],
        "name": current_user.username,
        "photo": current_user.avatar_url
    }

    # Generate HMAC for the response payload
    payload_json = json.dumps(payload, separators=(',', ':')).encode()
    response_hmac = hmac.new(secret_key, payload_json, hashlib.sha256).hexdigest()
    payload_hex = binascii.hexlify(payload_json).decode()

    # Redirect to Commento's SSO callback
    redirect_url = f"https://commento.infomundi.net/api/oauth/sso/callback?payload={payload_hex}&hmac={response_hmac}"
    return redirect(redirect_url, code=302)


@auth_views.route('/logout')
@login_required
def logout():
    flash(f'We hope to see you again soon, {current_user.username}.')

    # Removes email from the user's session. 
    # It would be creepy to see your email address in the contact form when you're logged out, wouldn't it?
    del session['email_address']
    session.permanent = False

    logout_user()
    return redirect(scripts.is_safe_url(request.headers.get('Referer', url_for('views.home'))))
