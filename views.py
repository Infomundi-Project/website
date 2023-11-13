from flask import Blueprint, render_template, request, redirect, jsonify, url_for, flash
from flask_login import current_user
from random import choice
from time import time

from website_scripts import scripts, config, json_util

views = Blueprint('views', __name__)

@views.route('/', methods=['GET'])
def home():
    """Render the homepage."""
    statistics = scripts.get_statistics()
    return render_template('homepage.html', page='Home', statistics=statistics, user=current_user)

@views.route('/contact', methods=['GET'])
def contact():
    """Render the contact page."""
    referer = request.headers.get('Referer', url_for('views.home'))
    
    flash('We apologize, but this page is currently unavailable. Please try again later!', 'error')
    return redirect(referer)

@views.route('/about', methods=['GET'])
def about():
    """Render the about page."""
    referer = request.headers.get('Referer', url_for('views.home'))
    
    flash('We apologize, but this page is currently unavailable. Please try again later!', 'error')
    return redirect(referer)

# Endpoint to return multiple RSS feeds as json
@views.route('/news', methods=['GET'])
def get_latest_feed():
    """Serving the /news endpoint. This function allows three GET parameters and uses them to filter by country, news category, and page number. It reads the cache information from the respective cache file and renders the rss_template.html template."""

    # Get the 'filter' parameter from the request or use 'general' if not provided
    page_num = request.args.get('page', '1') # If page is not provided in the GET request parameters, set it to 1.
    country_filter = request.args.get('country', f"{choice(['br', 'us', 'ca', 'es', 'ro', 'ly', 'ru', 'in', 'za', 'au'])}").lower() # If no country, picks a random one.
    news_filter = request.args.get('section', 'general').lower() # If no section, set it to general
    
    selected_filter = country_filter + "_" + news_filter

    # Check if the selected category is valid
    if not scripts.valid_category(selected_filter):
        flash('We apologize, but there is no support available for the country you selected. If you would like to recommend sources, please send us an email at contact@infomundi.net.', 'error')
        return redirect(url_for('views.home'))

    # Searches for the country full name
    countries = config.COUNTRY_LIST
    for item in countries:
        if item['code'].lower() == country_filter:
            country_name = item['name']

    query = request.args.get('query', '').lower()
    try:
        # Read the cache for the selected filter
        cache = json_util.read_json(f"{config.CACHE_PATH}/{selected_filter}")
    except FileNotFoundError:
        # Handle cache reading error
        flash('We apologize, but something went wrong. Please try again later. In the meantime, feel free to explore other countries!', 'error')
        return redirect(url_for('views.home'))
    except KeyError:
        # Handle page not found in cache
        page_num = 1

    cache_pages = [x for x in cache if 'page' in x]
    if query: # query will change code logic, but I think its better to adapt everything - @behindsecurity
        found_stories_via_query = []
        for page in cache_pages:
            found_stories_via_query.extend([story for story in cache[page] if query in story['title'] or query in story['description']])
    
        if not found_stories_via_query:
            flash('No stories were found with the provided term.', 'error')
            referer = request.headers.get('Referer', url_for('views.home'))
            return redirect(referer)

        cache[f'page_{page_num}'] = found_stories_via_query

    # Get number of comments
    comments = json_util.read_json(config.COMMENTS_PATH)
    for story in cache[f'page_{page_num}']:
        story['total_comments'] = len(comments[story['id']]) if story['id'] in comments else 0
    
    # Set to send to the template
    supported_categories = scripts.get_supported_categories(country_filter)
    page_num = int(page_num) # Set the page to integer to work properly with rss_template.html
    total_pages = len(cache_pages) if not query else 0 # Else is 0 because rss_template.html should not render the pagination if the query is set
    return render_template('rss_template.html', feeds=cache[f'page_{page_num}'], total_pages=total_pages, country_name=country_name, 
        news_filter=news_filter, page_num=page_num, selected_filter=selected_filter, country_code=country_filter, supported_categories=supported_categories, page='News', user=current_user)

@views.route('/get-country-code', methods=['GET'])
def get_country_code():
    """Get the country code based on the selected country name."""
    selected_country = request.args.get('country', '')
    
    if not selected_country:
        return redirect(url_for('views.home'))
    
    code = [x['code'] for x in config.COUNTRY_LIST if x['name'].lower() == selected_country.lower()]

    # Return the country code as JSON
    return jsonify({"countryCode": code[0]})

@views.route('/autocomplete', methods=['GET'])
def autocomplete():
    """Autocomplete endpoint for country names."""
    query = request.args.get('query', '')
    
    if not query:
        return redirect(url_for('views.home'))
    
    countries = [x['name'] for x in config.COUNTRY_LIST]
    results = [country for country in countries if query.lower() in country.lower()]
    return jsonify(results)

@views.route('/comments', methods=['GET'])
def comments():
    """Render comments for a specific news item."""
    referer = request.headers.get('Referer', url_for('views.home'))

    news_id = request.args.get('id', '').lower()
    category = request.args.get('category', '').lower()
    page_number = request.args.get('page', '1')

    comments = json_util.read_json(config.COMMENTS_PATH)
    cache = json_util.read_json(f"{config.CACHE_PATH}/{category}")
    
    if not scripts.valid_category(category) or not category or not news_id or not page_number:
        message = 'We apologize, but there was an error. Please try again later.'
    elif not comments['enabled']:
        message = 'We apologize, but comments are temporarily disabled. You can try again later.'
    elif f'page_{page_number}' not in cache:
        message = 'We apologize, but the story was not found. Fell free to explore other stories!'
    else:
        message = ''

    if message:
        flash(message, 'error')
        return redirect(referer)

    news_link = ''
    for story in cache[f'page_{page_number}']:
        if story['id'] == news_id:
            news_link = story['link']
            if 'infomundi' in story['media_content']['url']:
                preview_data = scripts.get_link_preview(news_link)
                story['media_content']['url'] = preview_data['image']
                json_util.write_json(cache, f"{config.CACHE_PATH}/{category}")
            else:
                preview_data = {}
                preview_data['image'] = story['media_content']['url']
            preview_data['description'] = scripts.remove_html_tags(story['description'])
            preview_data['title'] = story['title']
            break
        
    if not news_link:
        flash('We apologize, but there was an error. Please try again later.', 'error')
        return redirect(referer)

    if news_id not in comments.keys():
        comments[news_id] = []
        post_comments = False
    else:
        post_comments = comments[news_id]
    
    return render_template('comments.html', page='Comments', comments=post_comments, news_link=news_link, id=news_id, preview_data=preview_data, user=current_user)

@views.route('/add_comment', methods=['POST'])
def add_comment():
    """Add a new comment."""
    referer = request.headers.get('Referer', url_for('views.home'))
    
    comments = json_util.read_json(config.COMMENTS_PATH)
    if not comments['enabled']:
        flash('We apologize, but comments are temporarily disabled. Please try again later.', 'error')
        return redirect(referer)
    
    name = current_user.id if current_user.is_authenticated else request.form['name']
    comment_text = request.form['comment']
    token = request.form['h-captcha-response'] # Retrieve token from post data with key 'h-captcha-response'

    if not scripts.valid_captcha(token):
        flash('Invalid captcha! Are you a robot?', 'error')
        return redirect(referer)

    # Checks user input length
    if len(comment_text) > 300 or len(name) > 20:
        flash('Please limit your input accordingly.', 'error')
        return redirect(referer)

    # Checks if the user needs a random name
    is_random_name = False
    if not name: # If user didn't provide a name (empty string)
        name_list = json_util.read_json('/var/www/infomundi/data/json/nicknames')
        name = choice(name_list)
        is_random_name = True
    
    # Remove punctuation based on a blacklist
    punctuation = {'~', '+', '[', '\\', '@', '{', '|', '&', '<', '`', '}', '_', '=', ']', '>'}
    for p in punctuation:
        comment_text = comment_text.replace(p, '')
        name = name.replace(p, '')
    
    # Checks if news_id is a valid md5 hash
    news_id = request.form['id']
    if len(news_id) != 32 or not (all(c.isdigit() or c.lower() in 'abcdef' for c in news_id)):
        return "<center><h1>Blocked by InfoMundi</h1></center> <br> <center><h3>Message from the Admin: What is hidden must remain hidden.</h3></center>"

    new_comment = {
        'name': name,
        'random_name': is_random_name,
        'is_admin': current_user.is_authenticated,
        'text': comment_text,
        'id': scripts.create_comment_id()
    }

    if news_id not in comments.keys():
        comments[news_id] = []
    comments[news_id].append(new_comment)
    
    json_util.write_json(comments, f'{config.COMMENTS_PATH}') # Saving the comment
    flash('Thank you for your comment! Sharing your opinion is safe with us.')
    return redirect(referer)
