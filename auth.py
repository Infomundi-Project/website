from flask import Blueprint, render_template, request, redirect, jsonify, url_for, flash, session
from flask_login import login_user, login_required, current_user, logout_user
from flask_httpauth import HTTPBasicAuth
from passlib.hash import argon2
from datetime import datetime, timedelta
from functools import wraps
from os import listdir

from website_scripts import config, json_util, scripts, immutable, extensions, models

auth_views = Blueprint('auth', __name__)
auth = HTTPBasicAuth()


def admin_required(func):
    """This decorator is used to check if the user is an admin."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('You are not authenticated.', 'error')
            return redirect(url_for('views.home'))

        # Check if the user is an admin based on the role
        if current_user.email.endswith('@infomundi.net'):
            return func(*args, **kwargs)
        
        flash('This page is restricted.', 'error')
        return redirect(url_for('views.home'))

    return decorated_function


def in_maintenance(func):
    """This decorator is used to check if the user is an admin."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('views.maintenance'))

        # Check if the user is an admin based on the role
        if current_user.email.endswith('@infomundi.net'):
            return func(*args, **kwargs)
        else:
            return redirect(url_for('views.maintenance'))

    return decorated_function


@auth_views.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('You are already logged in!')
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        token = request.form['cf-turnstile-response']
        if not scripts.valid_captcha(token):
            flash('Invalid captcha. Are you a robot?', 'error')
            return redirect(url_for('auth.register'))
        
        email = request.form.get('email', '')
        if not scripts.is_valid_email(email):
            flash('Invalid email address.', 'error')
            return redirect(url_for('auth.register'))

        username = request.form.get('username', '')
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')


        # Is email already present?
        email_lookup = models.User.query.filter_by(email=email).first()
        
        # Is username already present?
        username_lookup = models.User.query.filter_by(username=username).first()
        
        if password != confirm_password:
            message = 'The passwords don\'t match.'
        elif len(username) > 30 or len(username) < 3 or not scripts.is_valid_username(username):
            message = 'Your username is invalid.'
        elif not scripts.is_strong_password(password):
            message = 'Password Policy: The password must have at least 1 number, 8 characters minimum and a maximum of 50 characters.'
        elif email_lookup:
            message = 'Email already exists.'
        elif username_lookup:
            message = 'Username already exists.'
        else:
            message = ''
        
        if message:
            flash(message, 'error')
            return redirect(url_for('auth.register'))

        send_token = scripts.send_verification_token(email, username)
        if not send_token:
            flash('We apologize, but something went wrong. Please, try again later.')
            scripts.log(f'[!] Not able to send verification token to {email}.')
            return redirect(url_for('auth.register'))

        now = datetime.now()
        tokens = json_util.read_json(config.TOKENS_PATH)

        tokens[email]['username'] = username
        tokens[email]['password'] = argon2.hash(password)
        tokens[email]['user_id'] = scripts.generate_id()
        
        # Save creation timestamp so we can delete it after X minutes
        tokens[email]['timestamp'] = now.isoformat()

        json_util.write_json(tokens, config.TOKENS_PATH)

        flash(f'We sent an email to {email}. Please, activate your account by clicking on the provided link.')
    
    return render_template('register.html', user=current_user)


@auth_views.route('/verify', methods=['GET'])
def verify():
    token = request.args.get('token', '')
    if not token or current_user.is_authenticated:
        return redirect(url_for('views.home'))

    tokens = json_util.read_json(config.TOKENS_PATH)

    to_delete = []
    now = datetime.now()
    
    for key, value in tokens.items():
        created_at = datetime.fromisoformat(value['timestamp'])
        time_difference = now - created_at
        if time_difference > timedelta(minutes=30):
            to_delete.append(key)
        
        if value['token'] == token:
            email = key
            username = value['username']
            password = value['password']
            user_id = value['user_id']
            break
    else:
        flash("We apologize, but we are unable to verify your account at the moment. Please, try again later.", 'error')
        return redirect(url_for('views.home'))

    for item in to_delete:
        del tokens[item]

    del tokens[email]
    json_util.write_json(tokens, config.TOKENS_PATH)
    
    new_user = models.User(user_id=user_id, username=username, password=password, role='admin' if email.endswith('@infomundi.net') else 'user', email=email, avatar_url='https://infomundi.net/static/img/avatar.webp')
    extensions.db.session.add(new_user)
    extensions.db.session.commit()

    login_user(new_user)

    flash(f'Your account has been verified, {username}! Thank you!')
    return redirect(url_for('views.home'))


@auth_views.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        flash('You are authenticated!')
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        turnstile = request.form['cf-turnstile-response']
        if not scripts.valid_captcha(turnstile):
            flash('Invalid captcha. Are you a robot?', 'error')
            return redirect(url_for('auth.forgot_password'))
        
        email = request.form.get('email', '').lower()
        if not email:
            flash('Something went wrong.', 'error')
            return redirect(url_for('auth.forgot_password'))

        user = models.User.query.filter_by(email=email).first()
        if user:
            result = scripts.send_forgot_password_token(email)
            if result:
                flash('Success! Check your email.')
            else:
                flash('We apologize, but an error has ocurred.', 'error')
        else:
            flash('We apologize, but an error has ocurred.', 'error')
        
        return redirect(url_for('auth.forgot_password'))
    else:
        token = request.args.get('token', '')
        if token:
            result = scripts.send_forgot_password_token(token=token)
            if result:
                user = models.User.query.filter_by(email=result).first()
                session['email_address'] = result
                session['username'] = user.username
                session['forgot_password'] = True
                
                flash('Success! You may be able to change your password now.')
                return redirect(url_for('auth.password_change'))
            else:
                flash('An error has ocurred.', 'error')
        
        return render_template('forgot_password.html', user=current_user)


@auth_views.route('/password_change', methods=['GET', 'POST'])
def password_change():
    forgot_password = session.get('forgot_password', '')
    if current_user.is_authenticated or forgot_password: 
        pass
    else:
        flash('This page is restricted!', 'error')
        return redirect(url_for('views.home'))

    if request.method == 'POST':
        token = request.form.get('cf-turnstile-response', '')
        if not scripts.valid_captcha(token):
            flash('Invalid captcha. Are you a robot?', 'error')
            return redirect(url_for('auth.login'))
        
        old_password = request.form.get('old_password', '')

        if forgot_password:
            old_password = 'something!'
        
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not old_password or not new_password or not confirm_password:
            flash('We apologize, but something went wrong. Try again later.', 'error')
            return redirect(url_for('auth.password_change'))
        
        if forgot_password:
            user = models.User.query.filter_by(email=session.get('email_address', '')).first()
        else:
            user = models.User.query.filter_by(email=current_user.email).first()

        if not forgot_password and not user.check_password(old_password):
            message = 'Incorrect old password.'
        elif new_password != confirm_password:
            message = 'Passwords must match!'
        elif not scripts.is_strong_password(new_password):
            message = 'Password Policy: The password must have at least 8 characters minimum and a maximum of 50 characters.'
        else:
            message = ''

        if message:
            flash(message, 'error')
            return redirect(url_for('auth.password_change'))
        
        # Update the user's password
        user.password = argon2.hash(new_password)
        extensions.db.session.commit()
        
        if forgot_password:
            del session['forgot_password']
            del session['email_address']
            del session['username']
        
        flash('Your password has been updated.')
        if forgot_password:
            return redirect(url_for('auth.login'))
    
    return render_template('password_change.html', user=current_user)


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

        email = request.form.get('email', '')
        password = request.form.get('password', '')

        if len(password) < 8 or not email:
            flash('Invalid credentials!', 'error')
            return redirect(url_for('auth.login'))

        user = models.User.query.filter_by(email=email).first()
        remember_me = bool(request.form.get('remember_me', ''))
        
        if user and user.check_password(password):
            login_user(user, remember=remember_me)
            flash(f'Welcome back, {current_user.username}!')
            return redirect(url_for('views.home'))
        else:
            flash('Invalid credentials!', 'error')
    
    return render_template('login.html', user=current_user)


@auth_views.route('/logout')
@login_required
def logout():
    flash(f'We hope to see you again soon, {current_user.username}.')

    logout_user()
    return redirect(url_for('views.home'))