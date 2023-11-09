import json
from flask import Blueprint, render_template, request, redirect, jsonify, url_for, flash
from flask_login import login_user, login_required, current_user, logout_user, UserMixin
from passlib.hash import argon2
from flask_httpauth import HTTPBasicAuth
from website_scripts.config import *
from website_scripts.scripts import *

auth_views = Blueprint('auth', __name__)

auth = HTTPBasicAuth()

# Custom user class for Flask-Login
class User(UserMixin):
    pass

# Load user credentials from a JSON file
def load_users():
    try:
        with open('/var/www/infomundi/data/json/users.json', 'r') as file:
            users = json.load(file)
    except FileNotFoundError:
        users = {}
    
    return users

# Save user credentials to a JSON file
def save_users(users):
    with open('/var/www/infomundi/data/json/users.json', 'w') as file:
        json.dump(users, file, indent=2)

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
    return render_template('admin.html', username=current_user.id)

# Registration route
@auth_views.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('The passwords does not match.', 'danger')
            return render_template('register.html')

        if len(username) > 30:
            flash('The length of your username should not be plus 30 characters long', 'danger')
            return render_template('register.html')

        if not is_strong_password(password):
            flash('Password Policy: The password must have at least 1 lowercase character, 1 uppercase character, 1 digit, 1 special character, 10 characters minimum and a maximum of 50 characters.', 'danger')
            return render_template('register.html')

        users = load_users()
        if username not in users:
            # Hash the password using Argon2 before saving
            hashed_password = argon2.hash(password)
            users[username] = hashed_password
            save_users(users)
            flash('Account created!', 'success')
            return redirect(url_for('auth.login'))

        flash('Username already exists', 'danger')
        return render_template('register.html')

    return render_template('register.html')

# Login route
@auth_views.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        token = request.form['h-captcha-response']
        
        if not valid_captcha(token):
            flash('Invalid captcha', 'danger')
            return render_template('login.html')

        users = load_users()
        if username in users:
            if argon2.verify(password, users[username]):
                user = User()
                user.id = username
                login_user(user)
                return redirect(url_for('auth.admin'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

# Get feed info
@auth_views.route('/get_feed_info', methods=['POST'])
@login_required
def get_feed_info():
    country_name = request.form['country_name'].lower()
    categories = []
    countries = COUNTRY_LIST
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
            percentage = string_similarity(country_name, country['name'].lower())
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
        flash(message, "danger")
        return redirect(url_for('auth.admin'))
    
    for file in listdir(FEEDS_PATH):
        file = file.replace(".json", "")
        if file.split('_')[0] == country_code:
            categories.append(file)

    data = {
        "country_name": country_name,
        "country_code": country_code,
        "feeds": {}
    }
    
    for category in categories:
        feeds = read_json(f'{FEEDS_PATH}/{category}')
        category_name = category.split('_')[1]
        data['feeds'][category_name] = []
        for feed in feeds:
            entry = {
                f"{feed['site']}": feed['url']
            }
            data['feeds'][category_name].append(entry)
    if len(data['feeds']) == 0:
        flash(f"There are no entries for {country_name}", "danger")
        return redirect(url_for('auth.admin'))
    return data

@auth_views.route('/disable_comments', methods=['POST'])
@login_required
def disable_comments():
    comments = read_json(COMMENTS_PATH)
    status = 'enabled'
    comments['enabled'] = True
    category = 'success'
    
    if request.form['flexSwitchCheckChecked'] == "false":
        comments['enabled'] = False
        status = 'disabled'
        category = 'danger'
    
    write_json(comments, COMMENTS_PATH)
    
    return jsonify({'status': status, 'category': category})

@auth_views.route('/get_comments_status', methods=['GET'])
@login_required
def get_comments_status():
    comments = read_json(COMMENTS_PATH)
    return jsonify({'enabled': comments['enabled']})

# Logout route
@auth_views.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

# Add News Entry route
@auth_views.route('/add_news', methods=['POST'])
@login_required
def add_news():
    country = request.form['country'].lower()
    category = request.form['category']
    site = request.form['site']
    url = request.form['url']

    # Create or append to the JSON file
    countries = COUNTRY_LIST
    country_code = ''
    for entry in countries:
        if entry['name'].lower() == country:
            country_code = entry['code'].lower()

    if country_code == '':
        flash('Could not find the country.', 'danger')
        return redirect(url_for('auth.admin'))
    filename = f"{FEEDS_PATH}/{country_code}_{category.lower()}.json"
    entry = {"site": site, "url": url}

    try:
        with open(filename, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        data = []

    data.append(entry)
    with open(filename, 'w') as file:
        json.dump(data, file, indent=2)
    flash('News entry added successfully', 'success')
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
            flash('Incorrect old password', 'danger')
        elif new_password != confirm_password:
            flash('New password and confirmation do not match', 'danger')
        elif not is_strong_password(new_password):
            flash('Password Policy: The password must have at least 1 lowercase character, 1 uppercase character, 1 digit, 1 special character, 10 characters minimum and a maximum of 50 characters.', 'danger')
        else:
            # Update the user's password
            users[current_user.id] = argon2.hash(new_password)
            save_users(users)
            flash('Password changed successfully', 'success')
            return redirect(url_for('auth.admin'))
    return render_template('password_change.html')

# Search Comments route
@auth_views.route('/search_comments', methods=['POST'])
@login_required
def search_comments():
    search_text = request.form['search_text']
    comments = read_json(COMMENTS_PATH)
    search_results = []
    for news_id in comments:
        index = 0
        if news_id == 'enabled': continue
        for comment in comments[news_id]:
            if search_text in comment['text']:
                search_results.append(comments[news_id][index])
            index += 1
    if len(search_results) == 0:
        flash('No comments found with the provided filter', 'danger')
    return render_template('admin.html', search_text=search_text, search_results=search_results)

# Delete Comments route
@auth_views.route('/delete_comment', methods=['POST'])
@login_required
def delete_comment():
    comment_id = request.form['comment_id']
    comments = read_json(COMMENTS_PATH)
    for news_id in comments:
        if news_id == 'enabled': continue
        for comment in comments[news_id]:
            if comment_id == comment['id']:
                new_comments = comments
                new_comments[news_id].remove(comment)
                flash('Comment deleted successfully', 'success')
                break
    try:
        write_json(new_comments, 'data/comments')
    except:
        flash('Comment not found.', 'danger')
    return render_template('admin.html')
