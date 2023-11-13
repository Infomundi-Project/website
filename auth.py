from flask import Blueprint, render_template, request, redirect, jsonify, url_for, flash
from flask_login import login_user, login_required, current_user, logout_user, UserMixin
from flask_httpauth import HTTPBasicAuth
from passlib.hash import argon2
from os import listdir

from website_scripts import config, json_util, scripts

auth_views = Blueprint('auth', __name__)

auth = HTTPBasicAuth()

# Custom user class for Flask-Login
class User(UserMixin):
    pass

# Load user credentials from a JSON file
def load_users():
    try:
        users = json_util.read_json(config.USERS_PATH)
    except FileNotFoundError:
        users = {}
    
    return users

# Save user credentials to a JSON file
def save_users(users):
    json_util.write_json(users, config.USERS_PATH)

# Custom authentication decorator
@auth.verify_password
def verify_password(username, password):
    users = load_users()
    if username in users and argon2.verify(password, users[username]):
        user = User()
        user.id = username
        login_user(user)
        return True

# Protected endpoint
@auth_views.route('/admin')
@login_required
def admin():
    return render_template('admin.html', user=current_user)

# Registration route
@auth_views.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        users = load_users()
        if password != confirm_password:
            message = 'The passwords don\'t match.'
        elif len(username) > 30:
            message = 'Your username should not have more than 30 characters'
        elif not scripts.is_strong_password(password):
            message = 'Password Policy: The password must have at least 1 lowercase character, 1 uppercase character, 1 digit, 1 special character, 10 characters minimum and a maximum of 50 characters.'
        elif username in users:
            message = 'Username already exists.'
        else:
            message = ''
        
        if message:
            flash(message, 'error')
            return redirect(url_for('auth.register'))

        # Hash the password using Argon2 before saving
        users[username] = argon2.hash(password)
        save_users(users)
        
        flash('Account created!')
    return render_template('register.html', user=current_user)

# Login route
@auth_views.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        token = request.form['h-captcha-response']
        
        if not scripts.valid_captcha(token):
            flash('Invalid captcha', 'error')
            return redirect(url_for('auth.register'))

        users = load_users()
        if username in users:
            if argon2.verify(password, users[username]):
                user = User()
                user.id = username
                login_user(user)
                return redirect(url_for('auth.admin'))
        flash('Invalid credentials', 'error')
    return render_template('login.html', user=current_user)

# Get feed info
@auth_views.route('/get_feed_info', methods=['POST'])
@login_required
def get_feed_info(): # Needs refactoring
    country_name = request.form['country_name'].lower()
    categories = []
    countries = config.COUNTRY_LIST
    percentage = 0
    for country in countries:
        if len(country_name) == 2: # user typed country code instead
            if country['code'].lower() == country_name:
                country_code = country_name
                country_name = country['name']
                percentage = 100
                break
            else:
                continue
        else:
            possibilities = []
            percentage = scripts.string_similarity(country_name, country['name'].lower())
            if percentage >= 80:
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

@auth_views.route('/disable_comments', methods=['POST'])
@login_required
def disable_comments():
    comments = json_util.read_json(config.COMMENTS_PATH)
    comments['enabled'] = False if request.form['flexSwitchCheckChecked'] == "false" else True
    
    json_util.write_json(comments, config.COMMENTS_PATH)
    return jsonify({'status': 'Success'})

@auth_views.route('/get_comments_status', methods=['GET'])
@login_required
def get_comments_status():
    comments = json_util.read_json(config.COMMENTS_PATH)
    return jsonify({'enabled': comments['enabled']})

# Add News Entry route
@auth_views.route('/add_news', methods=['POST'])
@login_required
def add_news():
    country = request.form['country'].lower()
    category = request.form['category']
    site = request.form['site']
    url = request.form['url']

    country_code = ''
    
    countries = config.COUNTRY_LIST
    for entry in countries:
        if entry['name'].lower() == country:
            country_code = entry['code'].lower()

    if not country_code:
        flash('Could not find the country!', 'error')
        return redirect(url_for('auth.admin'))

    filename = f"{config.FEEDS_PATH}/{country_code}_{category.lower()}"
    try:
        data = json_util.read_json(filename)
    except FileNotFoundError:
        data = []

    entry = {"site": site, "url": url}
    data.append(entry)
    json_util.write_json(data, filename)

    flash('Success!')
    return redirect(url_for('auth.admin'))

@auth_views.route('/password_change', methods=['GET', 'POST'])
@login_required
def password_change():
    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        users = load_users()
        if not argon2.verify(old_password, users[current_user.id]):
            message = 'Incorrect old password.'
        elif new_password != confirm_password:
            message = 'New password and confirmation do not match.'
        elif not scripts.is_strong_password(new_password):
            message = 'Password Policy: The password must have at least 1 lowercase character, 1 uppercase character, 1 digit, 1 special character, 10 characters minimum and a maximum of 50 characters.'
        else:
            message = ''

        if not message:
            flash(message, 'error')
            return redirect(url_for('auth.password_change'))
        
        # Update the user's password
        users[current_user.id] = argon2.hash(new_password)
        save_users(users)
        
        flash('Password changed successfully.')
    return render_template('password_change.html', user=current_user)

# Search Comments route
@auth_views.route('/search_comments', methods=['POST'])
@login_required
def search_comments():
    search_text = request.form['search_text']
    search_results = []
    
    # Searches if the text is seen in any comment
    comments = json_util.read_json(config.COMMENTS_PATH)
    for news_id in comments:
        if news_id == 'enabled': continue
        for comment in comments[news_id]:
            if search_text in comment['text']:
                search_results.append(comment)
    
    if not search_results:
        flash('No comments found with the provided filter.', 'error')
        return redirect(url_for('auth.admin'))
    
    return render_template('admin.html', search_text=search_text, search_results=search_results, user=current_user)

# Delete Comments route
@auth_views.route('/delete_comment', methods=['POST'])
@login_required
def delete_comment():
    comment_id = request.form['comment_id']
    
    comments = json_util.read_json(config.COMMENTS_PATH)
    for news_id in comments:
        if news_id == 'enabled': continue
        for comment in comments[news_id]:
            if comment_id == comment['id']:
                new_comments = comments
                new_comments[news_id].remove(comment)
                json_util.write_json(new_comments, config.COMMENTS_PATH)
                flash('Comment deleted successfully.')
                return redirect(url_for('auth.admin'))
    
    flash('Comment not found.', 'error')
    return redirect(url_for('auth.admin'))

# Logout route
@auth_views.route('/logout')
@login_required
def logout():
    logout_user()
    referer = request.headers.get('Referer', url_for('views.home'))
    return redirect(referer)