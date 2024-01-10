from flask import Blueprint, request, redirect, jsonify, url_for, flash, session
from flask_login import current_user
from random import choice
from time import time

from website_scripts import config, json_util, scripts
from auth import admin_required

api = Blueprint('api', __name__)


@api.route('/get-description', methods=['GET'])
def get_description():
    card_id = request.args.get('id')
    category = request.args.get('category')

    if not scripts.valid_category(category):
        return {}

    cache = json_util.read_json(f'{config.CACHE_PATH}/{category}')
    for story in cache['stories']:
        if story['id'] == card_id:
            data = {}
            data['title'] = story['title']
            data['description'] = story['description']
            data['publisher'] = story['publisher']
            break
    else:
        data = {}

    return jsonify(data)


@api.route('/get_country_code', methods=['GET'])
def get_country_code():
    """Get the country code based on the selected country name.

    Argument: str
    	GET 'country' parameter. A simple string, for example 'Brazil'.

	Return: dict
		Returns the country code of the specified country in a json format (using jsonify). An example would be:

		{
			'countryCode': 'BR'
		}
    """

    selected_country = request.args.get('country', '')
    
    if not selected_country:
        return redirect(url_for('views.home'))
    
    code = [x['code'] for x in config.COUNTRY_LIST if x['name'].lower() == selected_country.lower()]

    return jsonify({"countryCode": code[0]})


@api.route('/autocomplete', methods=['GET'])
def autocomplete():
    """Autocomplete endpoint for country names.

    Argument: str
    	GET 'query' parameter. A simple string, for example 'Bra'.

    Return: list
    	Returns a list of countries relevant to the query. An example would be:

    	['Brazil', 'Gibraltar']
    """

    query = request.args.get('query', '').lower()
    
    if len(query) < 2:
        return redirect(url_for('views.home'))
    
    results = [x['name'] for x in config.COUNTRY_LIST if query in x['name'].lower()]
    return jsonify(results)


@api.route('/add_comment', methods=['POST'])
def add_comment():
    referer = request.headers.get('Referer', url_for('views.home'))
    
    comments = json_util.read_json(config.COMMENTS_PATH)
    if not comments['enabled']:
        flash('We apologize, but comments are temporarily disabled. Please try again later.', 'error')
        return redirect(referer)
    
    # Retrieve token from post data with key 'cf-turnstile-response'
    token = request.form['cf-turnstile-response']
    if not scripts.valid_captcha(token):
        flash('Invalid captcha! Are you a robot?', 'error')
        return redirect(referer)

    # Checks if user is on cooldown
    entered_comments_at = session.get('entered_comments_at', '')

    if not entered_comments_at:
        flash('There was an error processing your comment. Please make sure your browser supports cookies.', 'error')
        return redirect(referer)

    elapsed_time = time() - entered_comments_at
    cooldown_time = 7
    
    if elapsed_time < cooldown_time:
        remaining_time = int(cooldown_time - elapsed_time)
        flash(f'Hold up! Wait a couple of seconds, we need to make sure you are not a robot. Cooldown: {remaining_time}', 'error')
        return redirect(referer)

    # Gets data from the form
    name = current_user.username if current_user.is_authenticated else request.form['name']
    comment_text = request.form['comment']

    # Shady users may edit the request using a tool like burpsuite to bypass the form restriction. We can't trust user input.
    if len(comment_text) > 300 or len(name) > 30:
        flash('Please limit your input accordingly.', 'error')
        return redirect(referer)

    # Checks if the user needs a random name.
    is_random_name = False
    if not name:
        name = choice(config.NICKNAME_LIST)
        is_random_name = True
    
    # Checks if the news really exist. We can't trust user input.
    news_id = request.form.get('id', '')
    category = request.form.get('category', '')

    if not scripts.valid_category(category) or not news_id:
        flash('We apologize, but there was an error. Please try again later.', 'error')
        return redirect(referer)

    cache = json_util.read_json(f"{config.CACHE_PATH}/{category}")

    stories_ids = [x['id'] for x in cache['stories']]
    if news_id not in stories_ids:
        flash('We apologize, but there was an error. Please try again later.', 'error')
        return redirect(referer)

    new_comment = {
        'name': name,
        'random_name': is_random_name,
        'is_admin': True if current_user.is_authenticated and current_user.role == 'admin' else False,
        'is_logged_in': True if current_user.is_authenticated else False,
        'text': comment_text,
        'link': session.get('last_visited_news', ''),
        'id': scripts.generate_id()
    }

    if news_id not in comments:
        comments[news_id] = []

    comments[news_id].append(new_comment)
    json_util.write_json(comments, f'{config.COMMENTS_PATH}')
    
    scripts.check_in_badlist(new_comment)
    
    flash('Thank you for your comment! Sharing your opinion is safe with us.')
    return redirect(referer)


"""
						[+] ADMIN-REQUIRED ENDPOINTS [+]
"""


@api.route('/add_news', methods=['POST'])
@admin_required
def add_news():
    country = request.form['country'].lower()
    category = request.form['category']
    site = request.form['site']
    url = request.form['url']
    
    countries = config.COUNTRY_LIST
    for entry in countries:
        if entry['name'].lower() == country:
            country_code = entry['code'].lower()
            break
    else:
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

    flash(f'Success! Added {url} feed to {country}!')
    return redirect(url_for('auth.admin'))


@api.route('/get_comments_status', methods=['GET'])
@admin_required
def get_comments_status():
    comments = json_util.read_json(config.COMMENTS_PATH)

    return jsonify({'enabled': comments['enabled']})


@api.route('/disable_comments', methods=['POST'])
@admin_required
def disable_comments():
    comments = json_util.read_json(config.COMMENTS_PATH)
    comments['enabled'] = False if request.form['flexSwitchCheckChecked'] == "false" else True
    
    json_util.write_json(comments, config.COMMENTS_PATH)
    return jsonify({'status': 'Success'})


@api.route('/delete_comment', methods=['POST'])
@admin_required
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
    
    flash(f'We could not find any comment associated with the ID {comment_id}.', 'error')
    
    return redirect(url_for('auth.admin'))
