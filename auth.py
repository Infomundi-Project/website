from flask import Blueprint, render_template, request, redirect, jsonify, url_for, flash, session
from flask_login import login_user, login_required, current_user, logout_user, UserMixin
from flask_httpauth import HTTPBasicAuth
from passlib.hash import argon2
from functools import wraps
from os import listdir

from website_scripts import config, json_util, scripts, immutable

auth_views = Blueprint('auth', __name__)
auth = HTTPBasicAuth()


class User(UserMixin):
    def __init__(self, email, username, password, role):
        self.email = email
        self.username = username
        self.password = password
        self.role = role

    def get_id(self):
        return self.email


def load_users():
    try:
        users_data = json_util.read_json(config.USERS_PATH)
    except Exception:
        return {}

    users = {}
    for email, data in users_data.items():
        user = User(email=email, username=data['username'], password=data['password'], role=data['role'])
        users[email] = user

    return users


def save_users(users):
    json_util.write_json({user.email: {'username': user.username, 'password': user.password, 'role': user.role} for user in users.values()}, config.USERS_PATH)


def verify_password(email: str, password: str, remember: bool):
    users = load_users()
    if email in users:
        user = users[email]
        if argon2.verify(password, user.password):
            login_user(user, remember=remember)
            
            flash(f'Welcome back, {current_user.username}!')
            return True

    return False


def admin_required(func):
    """This decorator is used to check if the user is an admin."""
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('You are not authenticated.', 'error')
            return redirect(url_for('views.home'))

        # Check if the user is an admin based on the role
        if current_user.role == 'admin':
            return func(*args, **kwargs)
        
        flash('This page is restricted.', 'error')
        return redirect(url_for('views.home'))

    return decorated_function


@auth_views.route('/register', methods=['GET', 'POST'])
def register():
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

        for character in immutable.SPECIAL_CHARACTERS:
            username.replace(character, '')

        users = load_users()
        if password != confirm_password:
            message = 'The passwords don\'t match.'
        elif len(username) > 30:
            message = 'Your username should not have more than 30 characters'
        elif not scripts.is_strong_password(password):
            message = 'Password Policy: The password must have at least 1 number, 8 characters minimum and a maximum of 50 characters.'
        elif email in users:
            message = 'Email already exists.'
        elif any(user.username == username.replace(' ', '') for user in users.values()):
            message = 'Username already exists'
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

        tokens = json_util.read_json(config.TOKENS_PATH)

        tokens[email]['username'] = username
        tokens[email]['password'] = argon2.hash(password)

        json_util.write_json(tokens, config.TOKENS_PATH)

        flash(f'We sent an email to {email}. Please, activate your account by clicking on the provided link.')
    
    return render_template('register.html', user=current_user, is_mobile=scripts.detect_mobile(request))


@auth_views.route('/verify', methods=['GET'])
def verify():
    token = request.args.get('token', '')
    if not token:
        return redirect(url_for('views.home'))

    tokens = json_util.read_json(config.TOKENS_PATH)

    for item in tokens:
        if tokens[item]['token'] == token:
            email = item
            username = tokens[item]['username']
            password = tokens[item]['password']
            break
    else:
        flash("We apologize, but we are unable to verify your account at the moment. Please, try again later.", 'error')
        return redirect(url_for('views.home'))

    del tokens[email]
    json_util.write_json(tokens, config.TOKENS_PATH)
    
    users = load_users()
    new_user = User(email=email, username=username, password=password, role='user')
    
    users[email] = new_user

    save_users(users)

    flash(f'Thanks for verifying your account! You may be able to sign in now.')
    return redirect(url_for('auth.login'))


@auth_views.route('/login', methods=['GET', 'POST'])
def login():
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

        # Verify password is responsible for handling user login.
        if verify_password(email, password, bool(request.form.get('remember_me', ''))):
            if current_user.role != 'admin':
                return redirect(url_for('views.home'))
            return redirect(url_for('auth.admin'))

        flash('Invalid credentials!', 'error')
    
    return render_template('login.html', user=current_user, is_mobile=scripts.detect_mobile(request))


@auth_views.route('/password_change', methods=['GET', 'POST'])
@login_required
def password_change():
    if request.method == 'POST':
        token = request.form.get('cf-turnstile-response', '')
        if not scripts.valid_captcha(token):
            flash('Invalid captcha. Are you a robot?', 'error')
            return redirect(url_for('auth.login'))
        
        old_password = request.form.get('old_password', '')
            
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
            
        if not old_password or not new_password or not confirm_password:
            flash('We apologize, but something went wrong. Try again later.', 'error')
            scripts.log('[!] User had issues when changing password: old_password, new_password or confirm_password.')
            return redirect(url_for('auth.password_change'))
        
        users = load_users()
        if not argon2.verify(old_password, users[current_user.email].password):
            message = 'Incorrect old password.'
        elif new_password != confirm_password:
            message = 'New password and confirmation do not match.'
        elif not scripts.is_strong_password(new_password):
            message = 'Password Policy: The password must have at least 1 number, 8 characters minimum and a maximum of 50 characters.'
        else:
            message = ''

        if message:
            flash(message, 'error')
            return redirect(url_for('auth.password_change'))
        
        # Update the user's password
        users[current_user.email].password = argon2.hash(new_password)
        save_users(users)
        
        flash('Password changed successfully.')
    
    return render_template('password_change.html', user=current_user, is_mobile=scripts.detect_mobile(request))


@auth_views.route('/admin')
@admin_required
def admin():
    return render_template('admin.html', user=current_user, is_mobile=scripts.detect_mobile(request))


@auth_views.route('/get_feed_info', methods=['POST'])
@admin_required
def get_feed_info():
    country_name = request.form['country_name'].lower()
    
    categories = []
    possibilities = []
    percentage = 0

    countries = config.COUNTRY_LIST
    for country in countries:
        if len(country_name) == 2: # user typed country code instead
            if country['code'].lower() == country_name:
                country_code = country_name
                country_name = country['name']
                percentage = 100
                break
            else:
                continue
        
        percentage = scripts.string_similarity(country_name, country['name'].lower())
        if percentage >= 90:
            country_code = country['code'].lower()
            country_name = country['name']
            break
        elif percentage >= 50:
            possibilities.append(country['name'])

    if percentage < 80:
        message = 'Could not find the country you are looking for. '
        if len(possibilities) >= 1:
            message += f"Here are some options based on your search: {', '.join(possibilities)}"
        flash(message, "error")
        return redirect(url_for('auth.admin'))
    
    # Checks available categories for the specified country (general, politics, technology and so on)
    for file in listdir(config.FEEDS_PATH):
        file = file.replace(".json", "")
        if file.split('_')[0] == country_code:
            categories.append(file)

    data = {
        "country_name": country_name,
        "country_code": country_code,
        "feeds": {}
    }
    
    for category in categories:
        feeds = json_util.read_json(f'{config.FEEDS_PATH}/{category}')
        category_name = category.split('_')[1]
        data['feeds'][category_name] = []
        for feed in feeds:
            entry = {
                f"{feed['site']}": feed['url']
            }
            data['feeds'][category_name].append(entry)
    
    if len(data['feeds']) == 0:
        flash(f"There are no entries for {country_name}", "error")
        return redirect(url_for('auth.admin'))
    
    return data


@auth_views.route('/search_comments', methods=['POST'])
@admin_required
def search_comments():
    search_text = request.form['search_text']
    
    search_results = []
    comments = json_util.read_json(config.COMMENTS_PATH)
    for news_id in comments:
        # Skips 'enabled' key as it would trigger a key error below in comment['text']
        if news_id == 'enabled': continue
        
        for comment in comments[news_id]:
            if search_text in comment['text']:
                search_results.append(comment)
    
    if not search_results:
        flash('No comments found with the provided filter.', 'error')
        return redirect(url_for('auth.admin'))
    
    return render_template('admin.html', search_text=search_text, search_results=search_results, user=current_user)


@auth_views.route('/logout')
@login_required
def logout():
    flash(f'We hope to see you again soon, {current_user.username}.')

    logout_user()
    referer = request.headers.get('Referer', url_for('views.home'))
    return redirect(referer)