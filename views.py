from time import time
from flask import Blueprint, render_template, request, redirect, jsonify, url_for, flash
from random import choice
from re import search as search_regex

from website_scripts.scripts import *
from website_scripts.config import *

views = Blueprint('views', __name__)

@views.route('/', methods=['GET'])
def home():
    """Render the homepage."""
    statistics = get_statistics() # from website_scripts.scripts
    return render_template('homepage.html', page='Home', statistics=statistics)

@views.route('/contact', methods=['GET'])
def contact():
    """Render the contact page."""
    referer = request.headers.get("Referer")
    flash('Currently unavailable as we work on it. Our fault!', 'error')
    return redirect(referer)

@views.route('/about', methods=['GET'])
def about():
    """Render the about page."""
    referer = request.headers.get("Referer")
    flash('Currently unavailable as we work on it. Our fault!', 'error')
    return redirect(referer)

# Endpoint to return multiple RSS feeds as json
@views.route('/news', methods=['GET'])
def get_latest_feed():
    """Serving the /news endpoint. This function allows three GET parameters and uses them to filter by country, news category, and page number.
    It reads the cache information from the respective cache file and renders the rss_template.html template."""

    # Get the 'filter' parameter from the request or use 'general' if not provided
    page_num = request.args.get('page') if request.args.get('page') is not None else '1'
    country_filter = request.args.get('country').lower() if request.args.get('country') is not None else choice(['br', 'us', 'ca', 'es', 'ro', 'ly', 'ru', 'in', 'za', 'au'])
    news_filter = request.args.get('section').lower() if request.args.get('section') is not None else 'general'
    
    selected_filter = country_filter + "_" + news_filter
    message = ''

    # Check if the selected category is valid
    if not valid_category(selected_filter):
        flash("We're sorry, but there is currently no support for the country you selected. Send us an email at contact@infomundi.net if you want to recommend news sources from the selected country.", 'error')
        return redirect(url_for('views.home'))

    countries = COUNTRY_LIST
    for item in countries:
        if item['code'].lower() == country_filter:
            country_name = item['name']

    now = time()
    try:
        # Read the cache for the selected filter
        cache = read_json(f"{CACHE_PATH}/{selected_filter}")
    except Exception as err:
        # Handle cache reading error
        flash("We're sorry, but something went wrong. You can try again later. Meanwhile, check out other countries!", 'error')
        return redirect(url_for('views.home'))

    total_pages = len(cache.keys()) - 1
    try:
        err = cache[f'page_{page_num}']
    except KeyError:
        # Handle page not found in cache
        page_num = 1

    for news in cache[f'page_{page_num}']:
        comments = read_json(COMMENTS_PATH)
        if comments.get(news['id']):
            news['total_comments'] = len(comments[news['id']])
        else:
            news['total_comments'] = 0
    supported_categories = get_supported_categories(country_filter)
    return render_template('rss_template.html', feeds=cache[f'page_{page_num}'], total_pages=total_pages, country_name=country_name, 
        news_filter=news_filter.title(), page_num=page_num, selected_filter=selected_filter, country_code=country_filter, supported_categories=supported_categories, page='News')

@views.route('/get-country-code', methods=['GET'])
def get_country_code():
    """Get the country code based on the selected country name."""
    selected_country = request.args.get('country', '')
    
    if selected_country == '':
        return redirect(url_for('views.home'))
    
    countries_file = COUNTRY_LIST
    code = [x['code'] for x in countries_file if x['name'].lower() == selected_country.lower()]

    # Return the country code as JSON
    return jsonify({"countryCode": code[0]})

@views.route('/autocomplete', methods=['GET'])
def autocomplete():
    """Autocomplete endpoint for country names."""
    query = request.args.get('query', '')
    
    if query == '':
        return redirect(url_for('views.home'))
    
    countries_file = COUNTRY_LIST
    countries = [x['name'] for x in countries_file]
    results = [country for country in countries if query.lower() in country.lower()]
    return jsonify(results)

@views.route('/comments', methods=['GET'])
def comments():
    """Render comments for a specific news item."""
    news_id = request.args.get('id', '').lower()
    category = request.args.get('category', '').lower()

    referer = request.headers.get("Referer")
    if not valid_category(category) or category == '':
        flash('Try again later.', 'error')
        return redirect(referer)

    cache = read_json(f"{CACHE_PATH}/{category}")
    news_link = ''
    for i in cache:
        if 'page' in i:
            for item in cache[i]:
                if item['id'] == news_id:
                    news_link = item['link']
                    if 'infomundi' in item['media_content']['url']:
                        preview_data = get_link_preview(news_link)
                        item['media_content']['url'] = preview_data['image']
                        write_json(cache, f"{CACHE_PATH}/{category}")
                    else:
                        preview_data = {}
                        preview_data['image'] = item['media_content']['url']
                    preview_data['description'] = item['description']
                    preview_data['title'] = item['title']
    
    if news_link == '':
        flash('There was an error. Please, try again later.', 'error')
        return redirect(referer)

    comments = read_json(COMMENTS_PATH)
    if news_id not in comments.keys():
        comments[news_id] = []
        post_comments = False
    else:
        post_comments = comments[news_id]

    return render_template('comments.html', page='Comments', comments=post_comments, news_link=news_link, id=news_id, preview_data=preview_data)

@views.route('/add_comment', methods=['POST'])
def add_comment():
    """Add a new comment."""
    referer = request.headers.get("Referer")
    comments = read_json(COMMENTS_PATH)
    if not comments['enabled']:
        flash('Comments are temporarily disabled. Try again later.', 'error')
        return redirect(referer)
    name = request.form['name']
    comment_text = request.form['comment']
    # Retrieve token from post data with key 'h-captcha-response'.
    token = request.form['h-captcha-response']

    if not valid_captcha(token):
        flash('Invalid captcha! Try again.', 'error')
        return redirect(referer)
    
    punctuation = {'~', '+', '[', '\\', '@', '^', '{', '-', '*', '|', '&', '<', '`', '}', '_', '=', ']', '>', ';', '$', '/'}
    for p in punctuation:
        if p in comment_text:
            comment_text = comment_text.replace(p, '')
        if p in name:
            name = name.replace(p, '')
    
    news_id = request.form['id']

    if len(news_id) != 32 or search_regex(r'[A-Z]', news_id) or search_regex(r'[\'"!@#$%^&*()_+{}\[\]:;<>,.?~\\/-]', news_id):
        return "<center><h1>Blocked by InfoMundi</h1></center> <br> <center><h3>Message from the Admin: What is hidden must remain hidden.</h3></center>"
    
    random_name = False
    if len(name) > 20:
        flash('Please limit your name to 20 characters.', 'error')
        return redirect(referer)
    elif name == "":
        name_list = read_json('/var/www/infomundi/data/json/nicknames')
        name = choice(name_list)
        random_name = True
    elif len(comment_text) > 300:
        flash('Please limit your comment to 300 characters.', 'error')
        return redirect(referer)
    else:
        pass

    comment_id = create_comment_id()

    new_comment = {
        'name': name, 
        'random_name': random_name,
        'text': comment_text,
        'id': comment_id
    }

    if news_id not in comments.keys():
        comments[news_id] = []

    comments[news_id].append(new_comment)
    write_json(comments, f'{COMMENTS_PATH}')
    flash('Thank you for your comment! Sharing your opinion is safe with us.')
    return redirect(referer)
