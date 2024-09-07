import binascii
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, abort
from flask_login import login_user, login_required, current_user, logout_user
from datetime import datetime
from sqlalchemy import or_

from website_scripts import config, json_util, scripts, extensions, models, input_sanitization,\
 cloudflare_util, auth_util, hashing_util, qol_util, security_util, totp_util
from website_scripts.decorators import admin_required, in_maintenance, unauthenticated_only, verify_captcha

auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
@unauthenticated_only
@verify_captcha
def login():
    # If user is in totp process, redirect them to the correct page
    if session.get('user_id', ''):
        return redirect(url_for('auth.totp'))

    if request.method == 'GET':
        return render_template('login.html')

    email = request.form.get('email', '')
    password = request.form.get('password', '')
    session['remember_me'] = bool(request.form.get('remember_me', ''))

    # To avoid making unecessary queries to the database, first check to see if the credentials match our sandards
    if not input_sanitization.is_valid_email(email) or not input_sanitization.is_strong_password(password):
        flash('Invalid credentials!', 'error')
        return redirect(url_for('auth.login'))

    user = models.User.query.filter_by(email=hashing_util.sha256_hash_text(email)).first()
    if not user or not user.check_password(password):
        flash('Invalid credentials!', 'error')
        return render_template('login.html')

    session['key_value'] = auth_util.configure_key(user, password)

    # If user has totp enabled, we redirect them to the totp page without effectively logging them in the system
    if user.totp_secret:
        session['email_address'] = email
        session['user_id'] = user.user_id
        return redirect(url_for('auth.totp'))

    auth_util.perform_login_actions(user, email)
    flash(f'Welcome back, {user.username}!')
    return redirect(url_for('views.user_profile', username=user.username))


@auth.route('/totp', methods=['GET', 'POST'])
@unauthenticated_only
@verify_captcha
def totp():
    if not session.get('user_id', ''):
        abort(404)

    user = models.User.query.get(session['user_id'])
    if request.method == 'GET':
        return render_template('twofactor.html', user=user)
    
    # Get information from the form
    recovery_token = request.form.get('recovery_token', '').strip()
    code = request.form.get('code', '').strip()

    # Perform all necessary checks
    is_valid, message = totp_util.deal_with_it(user, code, recovery_token, session['key_value'])
    if not is_valid:
        flash(message, 'error')
        return redirect(url_for('auth.totp'))

    # Logs the user and performs some other actions
    auth_util.perform_login_actions(user, session['email_address'])
    
    # This is an indicator that the user has two factor, and we don't use it anywhere after this logic
    del session['user_id']

    flash(message)
    return redirect(url_for('views.user_profile', username=user.username))


@auth.route('/disable_totp', methods=['POST'])
@login_required
def disable_totp():
    current_password = request.form.get('current_password', '')
    if not current_user.check_password(current_password):
        flash('Invalid current password', 'error')
        return redirect(url_for('views.edit_user_settings'))

    code = request.form.get('code', '')
    
    # Get the user key information from their session
    key_salt, key_value = session['key_data']

    # Decrypt user's totp secret
    totp_secret = security_util.decrypt(current_user.totp_secret, initial_key=key_value)

    is_valid_totp = totp_util.verify_totp(totp_secret, code)
    if not is_valid_totp:
        flash('Invalid TOTP code!', 'error')
        return redirect(url_for('views.edit_user_settings'))

    # Removes the user's TOTP information from the database
    totp_util.remove_totp(current_user)

    flash('You removed your two factor authentication!')
    return redirect(url_for('views.edit_user_settings'))


@auth.route('/register', methods=['GET', 'POST'])
@unauthenticated_only
@verify_captcha
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    # Checks if email is valid
    email = request.form.get('email', '').strip()
    if not input_sanitization.is_valid_email(email):
        flash('We apologize, but your email address format is invalid.', 'error')
        return redirect(url_for('auth.register'))

    # Checks if username is valid
    username = request.form.get('username', '').strip()
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
    if not input_sanitization.is_strong_password(password):
        flash('Password must be 8-50 characters long, contain at least one uppercase letter, one lowercase letter, one number, and one special character.', 'error')
        return redirect(url_for('auth.register'))

    hashed_email = hashing_util.sha256_hash_text(email)
    
    user_lookup = models.User.query.filter(or_(
        models.User.email == hashed_email,
        models.User.username == username
    )).first()
    if user_lookup:
        # Make no mistake, we use this message here in order to prevent user enumeration
        flash(f'If everything went smoothly, you should soon receive instructions in your inbox at {email}')
        return redirect(url_for('auth.register'))

    # Tries to send a verification email to the user.
    send_token = auth_util.handle_register_token(email, hashed_email, username, hashing_util.argon2_hash_text(password))
    if not send_token:
        flash('We apologize, but something went wrong on our end. Please, try again later.', 'error')
        scripts.log(f'[!] Not able to send verification token to {email}.')
        
        return redirect(url_for('auth.register'))

    flash(f'If everything went smoothly, you should soon receive instructions in your inbox at {email}')
    return redirect(url_for('auth.register'))


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
        user = auth_util.check_recovery_token(recovery_token)
        if user:
            session['session_version'] = user.session_version
            login_user(user)

            flash('Success! You may be able to change your password now.')
            return redirect(url_for('auth.password_change'))

        flash('We apologize, but the token seems to be invalid.', 'error')
        return render_template('forgot_password.html')
        
    email = request.form.get('email', '')
    if not input_sanitization.is_valid_email(email):
        flash('We apologize, but your email address format is invalid.', 'error')
        return render_template('forgot_password.html')

    # Tries to send the recovery token to the user
    auth_util.send_recovery_token(email, hashing_util.sha256_hash_text(email))

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
    elif not input_sanitization.is_strong_password(new_password):
        message = "Password must be 8-50 characters long, contain at least one uppercase letter, one lowercase letter, one number, and one special character."
    else:
        message = ''

    if message:
        flash(message, 'error')
        return render_template('password_change.html')
        
    # Update the user's password
    current_user.set_password(new_password)
    
    # Make sure the user is not in recovery mode
    current_user.in_recovery = False

    # As the user password has changed, we can no longer decrypt the totp secret!
    current_user.totp_secret = None
    current_user.totp_recovery = None
    
    # Commits to the database
    extensions.db.session.commit()

    message = f"""Hello,

We wanted to inform you that the password for your Infomundi account has been successfully changed. If you made this change, there's nothing else you need to do.

The change was made from the following location:
- IP Address: {cloudflare_util.get_user_ip()}
- Country: {cloudflare_util.get_user_country()}

However, if you did not authorize this change, please take immediate action to secure your account. You can recover your account by clicking the link below:

https://infomundi.net/auth/forgot_password

If you encounter any issues or need further assistance, feel free to contact us using the form at:

https://infomundi.net/contact

Best regards,
The Infomundi Team"""
    subject = 'Infomundi - Password Change Notification'

    notifications.send_email()

    flash(f'Your password has been updated, {current_user.username}. You may log in now.')
    logout_user()
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
    display_name = input_sanitization.sanitize_text(user_info['name'])
    username = input_sanitization.create_username_out_of_display_name(display_name)
    hashed_email = hashing_util.sha256_hash_text(user_info['email'])
    
    # If the user is not already in the database, we create an entry for them
    user = models.User.query.filter_by(email=hashed_email).first()
    if not user:
        # Generate a super random password and argon2 hash it. 
        # The user can only log in using google integration or if they want to recover their account for some reason.
        random_hashed_password = hashing_util.argon2_hash_text(security_util.generate_nonce(24))
        user = models.User(user_id=security_util.generate_nonce(10), display_name=display_name,\
            username=username, password=random_hashed_password, email=hashed_email, avatar_url='https://infomundi.net/static/img/avatar.webp')
        extensions.db.session.add(user)
        extensions.db.session.commit()
    
    auth_util.perform_login_actions(user, user_info['email'])

    flash(f"Hello, {user.username}! Welcome to Infomundi!")
    return redirect(url_for('views.home'))


@auth.route('/logout', methods=['GET'])
@login_required
def logout():
    flash(f'We hope to see you again soon, {current_user.username}')

    session.clear()

    logout_user()
    return redirect(url_for('views.home'))
