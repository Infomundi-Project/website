import binascii, json, hmac, hashlib
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, abort, make_response
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
@in_maintenance
def login():
    # If user is in totp process, redirect them to the correct page
    if session.get('user_id', ''):
        return redirect(url_for('auth.totp'))

    if request.method == 'GET':
        return render_template('login.html')

    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    session['remember_me'] = bool(request.form.get('remember_me', ''))

    # To avoid making unecessary queries to the database, first check to see if the credentials match our sandards
    if not input_sanitization.is_valid_email(email) or not input_sanitization.is_strong_password(password):
        flash('Invalid credentials!', 'error')
        return redirect(url_for('auth.login'))

    user = auth_util.search_user_email_in_database(email)
    if not user or not user.check_password(password):
        flash('Invalid credentials!', 'error')
        return render_template('login.html')

    session['key_value'] = auth_util.configure_key(user, password)

    # If user has totp enabled, we redirect them to the totp page without effectively performing log in actions
    if user.totp_secret:
        session['email_address'] = email
        session['user_id'] = user.user_id
        session['in_totp_process'] = True
        return redirect(url_for('auth.totp'))

    auth_util.perform_login_actions(user, email)
    flash(f'Welcome back, {user.username}!')
    return redirect(url_for('views.user_profile', username=user.username))


@auth.route('/totp', methods=['GET', 'POST'])
@verify_captcha
def totp():
    if not session.get('in_totp_process', ''):
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
    
    # Deletes variables related to the totp process
    del session['user_id']
    del session['in_totp_process']

    flash(message)
    return redirect(url_for('views.user_profile', username=user.username))


@auth.route('/reset_totp', methods=['GET'])
def reset_totp():
    if not session.get('in_totp_process', ''):
        return abort(404)

    del session['in_totp_process']
    del session['user_id']

    return redirect(url_for('views.home'))


@auth.route('/disable_totp', methods=['POST'])
@login_required
def disable_totp():
    totp_util.remove_totp(current_user)

    flash('You removed your two factor authentication!')
    return redirect(url_for('views.edit_user_settings', username=current_user.username))


@auth.route('/register', methods=['GET', 'POST'])
@unauthenticated_only
@verify_captcha
@in_maintenance
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
        flash('Password and confirm password must match!', 'error')
        return redirect(url_for('auth.register'))

    # Checks if password is strong enough
    if not input_sanitization.is_strong_password(password):
        flash('Password must be 8-100 characters long, contain at least one uppercase letter, one lowercase letter, one number, and one special character.', 'error')
        return redirect(url_for('auth.register'))

    email_lookup = auth_util.search_user_email_in_database(email)
    username_lookup = auth_util.search_username_in_database(username)

    if not (email_lookup and username_lookup):
        send_token = auth_util.handle_register_token(email, auth_util.hash_user_email_using_salt(email), username, hashing_util.argon2_hash_text(password))
        if not send_token:
            flash('We apologize, but something went wrong on our end. Please, try again later.', 'error')
            scripts.log(f'[!] Not able to send verification token to {email}.')
            
            return redirect(url_for('auth.register'))

    flash(f'If everything went smoothly, you should soon receive instructions in your inbox at {email}')
    return redirect(url_for('auth.register'))


@auth.route('/invalidate_sessions', methods=['POST'])
@login_required
def invalidate_sessions():
    # Change state in the database
    current_user.session_version += 1
    # Change user's session version in the session cookie so they won't have to log in again
    session['session_version'] = current_user.session_version
    # Commit changes to the database
    extensions.db.session.commit()
    
    flash('All sessions have been invalidated.')
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
    if not qol_util.is_date_within_threshold_minutes(created_at, 30) or models.User.query.filter_by(email=token_lookup.email).first():
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
        if not user:
            flash('We apologize, but the token seems to be invalid.', 'error')
            return render_template('forgot_password.html')    
        
        # We don't need to log the user in yet. Save the user id to the session cookie to use in the password_change endpoint.
        session['user_id'] = user.user_id

        # Set user in recovery mode
        user.in_recovery = True
        extensions.db.session.commit()

        flash('Success! You may be able to change your password now.')
        return redirect(url_for('auth.password_change'))
        
    email = request.form.get('email', '').lower().strip()
    if not input_sanitization.is_valid_email(email):
        flash('We apologize, but your email address format is invalid.', 'error')
        return render_template('forgot_password.html')

    # Tries to send the recovery token to the user
    auth_util.send_recovery_token(email)

    # Generic message to prevent user enumeration
    flash(f"If {email} is in our database, an email will be sent with instructions.")
    return render_template('forgot_password.html')


@auth.route('/password_change', methods=['GET', 'POST'])
@unauthenticated_only
def password_change():
    if not session.get('user_id', ''):
        return abort(404)

    user = models.User.query.get(session['user_id'])
    if not user.in_recovery:
        return abort(404)

    if request.method == 'GET':
        return render_template('password_change.html', username=user.username)
    
    # Get form data
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    if new_password != confirm_password:
        message = 'Passwords must match!'
    elif not input_sanitization.is_strong_password(new_password):
        message = "Password must be 8-50 characters long, contain at least one uppercase letter, one lowercase letter, one number, and one special character."
    elif models.CommonPasswords.query.get(new_password):
        message = 'Your password is too common, please, make sure to create a unique one.'
    else:
        message = ''

    if message:
        flash(message, 'error')
        return render_template('password_change.html', username=user.username)
    
    auth_util.change_password(user, new_password)
    
    # ????????
    if session.get('user_id', ''):
        del session['user_id']

    flash('Your password has been changed! You may log in now.')
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

    if not auth_util.send_delete_token(user_email):
        flash('You already have a delete token associated with your account.', 'error')
        return redirect(url_for('views.user_redirect'))

    flash(f"We've sent an email with instructions to your email address at {session.get('obfuscated_email_address', '')}.")
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
    hashed_email = auth_util.hash_user_email_using_salt(user_info['email'])
    
    # If the user is not already in the database, we create an entry for them
    user = auth_util.search_user_email_in_database(user_info['email'])
    if not user:
        # Generate a super random password and argon2 hash it. 
        # The user can only log in using google integration or if they want to recover their account for some reason.
        random_hashed_password = hashing_util.argon2_hash_text(security_util.generate_nonce())
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
    
    response = auth_util.perform_logout_actions()
    return response
