import binascii
import hashlib
import hmac
import json

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from flask_login import login_user, login_required, current_user, logout_user
from datetime import datetime, timedelta
from sqlalchemy import or_

from website_scripts import config, json_util, scripts, immutable, extensions, models, input_sanitization,\
 cloudflare_util, auth_util, hashing_util
from website_scripts.decorators import admin_required, in_maintenance, unauthenticated_only, verify_captcha

auth = Blueprint('auth', __name__)


@auth.route('/register', methods=['GET', 'POST'])
@unauthenticated_only
@verify_captcha
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    # Checks if email is valid
    email = request.form.get('email', '')
    if not input_sanitization.is_valid_email(email):
        flash('We apologize, but your email address format is invalid.', 'error')
        return redirect(url_for('auth.register'))

    # Checks if username is valid
    username = request.form.get('username', '')
    if not input_sanitization.is_valid_username(username):
        flash('We apologize, but your username is invalid. Must be 3-25 characters long and contain only letters, numbers, underscores, or hyphens.', 'error')
        return redirect(url_for('auth.register'))

    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    # Checks if the passwords match
    if password != confirm_password:
        flash('The passwords don\'t match.', 'error')
        return redirect(url_for('auth.register'))

    # Checks if password is strong enough
    if not scripts.is_strong_password(password):
        flash('Password Policy: The password must be 8-50 characters.', 'error')
        return redirect(url_for('auth.register'))

    hashed_email = hashing_util.sha256_hash_text(email)
    
    user_lookup = models.User.query.filter(or_(
        models.User.email == hashed_email,
        models.User.username == username
    )).first()
    if user_lookup:
        flash(f'We apologize, but there has been an error.', 'error')
        return redirect(url_for('auth.register'))

    # Tries to send a verification email to the user.
    send_token = auth_util.handle_register_token(email, hashed_email, username, hashing_util.argon2_hash_text(password))
    if not send_token:
        flash('We apologize, but something went wrong. Please, try again later.', 'error')
        scripts.log(f'[!] Not able to send verification token to {email}.')
        
        return redirect(url_for('auth.register'))

    flash(f'We sent an email with activation instructions to your address at {email}')
    return render_template('register.html')


@auth.route('/invalidate_sessions', methods=['POST'])
@login_required
def invalidate_sessions():
    current_password = request.form.get('current_password', '')
    if not current_user.check_password(current_password):
        flash('Invalid current password', 'error')
        return redirect(url_for('views.user_redirect'))

    try:
        # Change state in the database
        current_user.session_version += 1
        # Change user's session version in the session cookie so they won't have to log in again
        session['session_version'] = current_user.session_version
        # Commit changes to the database
        extensions.db.session.commit()
        flash('All sessions have been invalidated.')
    except Exception:
        extensions.db.session.rollback()
        flash('An error occurred while invalidating sessions.', 'error')
    
    return redirect(url_for('views.user_redirect'))


@auth.route('/verify', methods=['GET'])
@unauthenticated_only
def verify():
    token = request.args.get('token', '')
    if not input_sanitization.is_md5_hash(token):
        flash('We apologize, but the token seems to be invalid.', 'error')
        return redirect(url_for('views.home'))

    # Tries to find the token in the database
    token_lookup = models.RegisterToken.query.filter_by(token=token).first()
    if not token_lookup:
        flash('We apologize, but the token seems to be invalid.', 'error')
        return redirect(url_for('views.home'))

    # Checks if the token is expired or the user already exist
    created_at = datetime.fromisoformat(token_lookup.timestamp.isoformat())
    if not qol_util.is_within_threshold_minutes(created_at, 30) or models.User.query.filter_by(email=token_lookup.email).first():
        extensions.db.session.delete(token_lookup)
        extensions.db.session.commit()
        
        flash('Either the token has expired or the user associated with this token already exists in our system. Try logging in or creating your account.', 'error')
        return redirect(url_for('views.home'))
    
    # Creates the new user and commits changes to the database
    new_user = models.User(user_id=token_lookup.user_id, username=token_lookup.username, password=token_lookup.password, email=token_lookup.email, avatar_url='https://infomundi.net/static/img/avatar.webp')
    extensions.db.session.add(new_user)
    
    extensions.db.session.delete(token_lookup)
    extensions.db.session.commit()

    flash(f'Your account has been verified, {token_lookup.username}! You may log in now!')
    return redirect(url_for('auth.login'))


@auth.route('/forgot_password', methods=['GET', 'POST'])
@unauthenticated_only
@verify_captcha
def forgot_password():
    if request.method == 'GET':
        recovery_token = request.args.get('token', '')
        if not recovery_token:
            return render_template('forgot_password.html')
        
        # Checks if the token is valid
        result = auth_util.check_recovery_token(recovery_token)
        if result:
            login_user(result)

            flash('Success! You may be able to change your password now.')
            return redirect(url_for('auth.password_change'))

        flash('We apologize, but the token seems to be invalid.', 'error')
        return render_template('forgot_password.html')
        
    email = request.form.get('email', '')
    if not input_sanitization.is_valid_email(email):
        flash('We apologize, but your email address format is invalid.', 'error')
        return render_template('forgot_password.html')

    # Tries to send the recovery token to the user
    auth_util.send_recovery_token(email, scripts.sha256_hash_text(email))

    # Generic error message to prevent user enumeration
    flash(f"If {email} is in our database, an email will be sent with instructions.")
    return render_template('forgot_password.html')


@auth.route('/password_change', methods=['GET', 'POST'])
@login_required
@verify_captcha
def password_change():
    if request.method == 'GET':
        return render_template('password_change.html')
    
    # Get form data
    old_password = request.form.get('old_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    # If the user is in recovery mode, they should bypass the old password check
    if not current_user.in_recovery and not current_user.check_password(old_password):
        message = 'Incorrect old password.'
    elif new_password != confirm_password:
        message = 'Passwords must match!'
    elif not scripts.is_strong_password(new_password):
        message = "Password Policy: The password should be 8-50 characers long."
    else:
        message = ''

    if message:
        flash(message, 'error')
        return render_template('password_change.html')
        
    # Update the user's password
    current_user.set_password(new_password)
    
    # Make sure the user is not in recovery mode
    current_user.in_recovery = False
    
    # Commits to the database
    extensions.db.session.commit()
        
    logout_user()

    flash(f'Your password has been updated, {user.username}. You may log in now.')
    return redirect(url_for('auth.login'))


@auth.route('/delete', methods=['GET', 'POST'])
@login_required
def account_delete():
    user_email = session.get('email_address', '')

    if request.method == 'GET':
        token = request.args.get('token', '')
        if not auth_util.delete_account(user_email, token):
            flash('Something went wrong, perhaps your token is invalid or expired', 'error')
            return redirect(url_for('views.user_redirect'))

        flash('Your account has been deleted.')
        return redirect(url_for('views.user_redirect'))

    current_password = request.form.get('current_password', '')
    if not auth_util.send_delete_token(user_email, current_password):
        flash('Something went wrong. Perhaps your current password is incorrect or you already have a token associated with your account.', 'error')
        return redirect(url_for('views.user_redirect'))

    flash(f"We've sent an email with instructions to {user_email}.")
    return redirect(url_for('views.user_redirect'))


@auth.route('/login', methods=['GET', 'POST'])
@unauthenticated_only
@verify_captcha
def login():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form.get('email', '')
    password = request.form.get('password', '')

    if not input_sanitization.is_valid_email(email) or not scripts.is_strong_password(password):
        flash('Invalid credentials!', 'error')
        return redirect(url_for('auth.login'))

    # Hash the email address before querying
    user = models.User.query.filter_by(email=hashing_util.sha256_hash_text(email)).first()
    if user and user.check_password(password):
        # Save the timestamp of the last login
        user.last_login = datetime.now()
        extensions.db.session.commit()

        remember_me = bool(request.form.get('remember_me', ''))
        login_user(user, remember=remember_me)
            
        # Make the email address last in the session
        session.permanent = True
        session['email_address'] = email
        session['obfuscated_email_address'] = input_sanitization.obfuscate_email(email)
        session['session_version'] = user.session_version
            
        flash(f'Welcome back, {current_user.username}!')
        return redirect(url_for('views.home'))

    flash('Invalid credentials!', 'error')
    return render_template('login.html')


@auth.route('/commento', methods=['GET'])
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


@auth.route('/google_redirect', methods=['GET'])
@unauthenticated_only
def google_redirect():
    nonce = g.nonce
    session['nonce'] = nonce

    redirect_uri = url_for('auth.google_callback', _external=True)
    return extensions.google.authorize_redirect(redirect_uri, nonce=nonce)


@auth.route('/google', methods=['GET'])
@unauthenticated_only
def google_callback():
    token = extensions.google.authorize_access_token()
    user_info = extensions.google.parse_id_token(token, nonce=session['nonce'])

    # Get user details
    display_name = user_info['name']
    username = input_sanitization.create_username_out_of_display_name(display_name)
    hashed_email = hashing_util.sha256_hash_text(user_info['email'])
    
    # If the user is not already in the database, we create an entry for them
    user = models.User.query.filter_by(email=hashed_email).first()
    if not user:
        # Generate a super random password and argon2 hash it. 
        # The user can only log in using google integration or if they want to recover their account for some reason.
        random_hashed_password = hashing_util.argon2_hash_text(security_util.generate_nonce(24))
        user = models.User(user_id=scripts.generate_id(), display_name=display_name, username=username, password=random_hashed_password, email=hashed_email, avatar_url='https://infomundi.net/static/img/avatar.webp')
        extensions.db.session.add(user)
        extensions.db.session.commit()
    
    session['email_address'] = user_info['email']
    session['obfuscated_email_address'] = input_sanitization.obfuscate_email(email)
    session['session_version'] = user.session_version
    login_user(user, remember=True)

    flash(f"Hello, {user.username}! Welcome to Infomundi!")
    return redirect(url_for('views.home'))


@auth.route('/logout', methods=['GET'])
@login_required
def logout():
    flash(f'We hope to see you again soon, {current_user.username}')

    # Removes email from the user's session. 
    # It'd be creepy to see your email address in the contact form when you're logged out, wouldn't it?
    if 'email_address' in session:
        del session['email_address']
    session.permanent = False

    logout_user()
    return redirect(url_for('views.home'))
