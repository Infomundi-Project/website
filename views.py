from flask import Blueprint, render_template, request, redirect, jsonify, url_for, flash, make_response, session
from flask_login import current_user
from random import choice
from time import time

from website_scripts import scripts, config, json_util, immutable

views = Blueprint('views', __name__)


@views.route('/', methods=['GET'])
def home():
    """Render the homepage."""
    statistics = scripts.get_statistics()

    crypto_data = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/crypto')
    world_stocks = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/stocks')
    currencies = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/currencies')

    us_indexes = [x for x in world_stocks if x['name'] in ['US500', 'US100', 'US30']]
    
    unique_indexes = []
    for index in us_indexes:
        if index not in unique_indexes:
            unique_indexes.append(index)

    # Assign currency information to the respective country
    for stock in world_stocks:
        for currency in currencies:
            country_name = currency['country_name'].replace('-', ' ').lower()
            if country_name == stock.get('country', '').lower():
                if currency['name'] == 'DXY':
                    currency['name'] = 'USD'
                    currency['price'] = 1
                stock['currency'] = currency
                break

        if not stock.get('currency', ''):
            country_name = stock['country_name'].lower()
            if country_name in immutable.EU_COUNTRIES:
                stock['currency'] = currencies[0]

    i = 1
    for item in crypto_data:
        world_stocks.insert(i, item)
        i += 2
    
    return render_template('homepage.html', 
        page='Home', 
        world_stocks=world_stocks, 
        us_indexes=enumerate(unique_indexes), 
        statistics=statistics, 
        user=current_user, 
        last_visited_country=session.get('last_visited_country', ''), 
        last_visited_news=session.get('last_visited_news', ''), 
        is_mobile=scripts.detect_mobile(request), 
        country_code='en'
    )


@views.route('/contact', methods=['GET'])
def contact():
    referer = request.headers.get('Referer', url_for('views.home'))
    
    flash('We apologize, but this page is currently unavailable. Please try again later!', 'error')
    return redirect(referer)


@views.route('/about', methods=['GET'])
def about():
    referer = request.headers.get('Referer', url_for('views.home'))
    
    flash('We apologize, but this page is currently unavailable. Please try again later!', 'error')
    return redirect(referer)


@views.route('/donate', methods=['GET'])
def donate():
    referer = request.headers.get('Referer', url_for('views.home'))
    
    flash('We apologize, but this page is currently unavailable. Please try again later!', 'error')
    return redirect(referer)


@views.route('/news', methods=['GET'])
def get_latest_feed():
    """Serving the /news endpoint. This function allows three GET parameters and uses them to filter by country, news category, and page number. It reads the cache information from the respective cache file and renders the rss_template.html template."""
    
    page_num = request.args.get('page', '1') 
    
    # If no country, selects a random one.
    country_filter = request.args.get('country', f"{choice(['br', 'us', 'ca', 'es', 'ro', 'ly', 'ru', 'in', 'za', 'au'])}").lower()
    
    news_filter = request.args.get('section', 'general').lower()
    selected_filter = f"{country_filter}_{news_filter}"

    # Check if the selected category is valid
    if not scripts.valid_category(selected_filter):
        flash('We apologize, but there is no support available for the country you selected. If you would like to recommend sources, please send us an email at contact@infomundi.net.', 'error')
        return redirect(url_for('views.home'))

    # Searches for the country full name (can be modularized)
    countries = config.COUNTRY_LIST
    for item in countries:
        if item['code'].lower() == country_filter:
            country_name = item['name']

    # Read the cache for the selected filter
    try:
        cache = json_util.read_json(f"{config.CACHE_PATH}/{selected_filter}")
        err = cache[f'page_{page_num}']
    except FileNotFoundError: # Handle cache reading error
        flash('We apologize, but something went wrong. Please try again later. In the meantime, feel free to explore other countries!', 'error')
        return redirect(url_for('views.home'))
    except KeyError: # Handle page not found in cache
        page_num = 1

    cache_pages = [x for x in cache if 'page' in x]
    query = request.args.get('query', '').lower()
    
    # Query will change code logic, but I think its better to adapt everything - @behindsecurity
    if query:
        found_stories_via_query = []
        for page in cache_pages:
            # Makes a copy of all the stories on the current cache page and adds a new entry: on_page. This entry is needed to work properly with the comments section, as we no longer relay on the GET parameter 'page' to read the correct page in cache.
            individual_page_keys = [{**d, 'on_page': page.split('_')[1]} for d in cache[page]]
            
            # Split words for better accuracy.
            found_stories_via_query.extend([story for story in individual_page_keys if query in story['title'].lower().split(' ') or query in story['description'].lower().split(' ')])

        if not found_stories_via_query:
            flash('No stories were found with the provided term.', 'error')
            referer = request.headers.get('Referer', url_for('views.home'))
            return redirect(referer)

        # Changes the current page to the results from the search in order to make the rest of the code usable.
        cache[f'page_{page_num}'] = found_stories_via_query

    # Get number of comments
    comments = json_util.read_json(config.COMMENTS_PATH)
    telemetry = json_util.read_json(config.TELEMETRY_PATH)
    for story in cache[f'page_{page_num}']:
        # Filter the title length.
        story['title'] = ' '.join(story['title'].split(' ')[:10]) + ' ...' if len(story['title']) > 90 else story['title']
        
        # Add total comments and clicks to the story.
        story['total_comments'] = len(comments[story['id']]) if story['id'] in comments else ''
        story['total_clicks'] = telemetry[story['id']]['clicks'] if story['id'] in telemetry else ''
    
    # Set the page to integer to work properly with rss_template.html.
    page_num = int(page_num)

    # Else is 0 because rss_template.html should not render the pagination if the query is set.
    total_pages = len(cache_pages) if not query else 0

    stock_data = scripts.scrape_stock_data(country_name)

    # There are countries with no national stock data available, so we use global stocks if that is the case.
    is_global = False
    if not stock_data or stock_data[0]['market_cap'] == None:
        stock_data = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/stock_data/united-states_stock')
        is_global = True

    stock_date = stock_data[0]['date']

    try:
        country_index = [x for x in json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/stocks') if x.get('country', '').lower() == country_name.lower()][0]
        currency_info = [x for x in json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/currencies') if x.get('country_name', '').lower() == country_name.lower().replace(' ', '-')][0]
        country_index['currency'] = currency_info
    except IndexError as err:
        scripts.log(f'[!] Error at /views: {err} // {country_name}')
        country_index = ''
    
    FULL_URL = f'https://infomundi.net/news?country={country_filter}&section={news_filter}&page={page_num}'
    session['last_visited_country'] = FULL_URL
    
    supported_categories = scripts.get_supported_categories(country_filter)

    area_ranks = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/area_ranking')

    for rank in area_ranks:
        if rank['country'].lower() == country_name.lower():
            area_rank = rank
            break
    else:
        area_rank = ''

    religions = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/religions')
    for country, religion in religions.items():
        if country.lower() == country_name.lower():
            main_religion = religion
            break
    else:
        main_religion = ''

    return render_template('rss_template.html', 
        feeds=cache[f'page_{page_num}'], 
        total_pages=total_pages, 
        country_name=country_name, 
        news_filter=news_filter, 
        page_num=page_num, 
        selected_filter=selected_filter, 
        country_code=country_filter, 
        supported_categories=supported_categories, 
        page='News', 
        area_rank=area_rank,
        main_religion=main_religion,
        user=current_user, 
        is_mobile=scripts.detect_mobile(request),
        nation_data=scripts.get_nation_data(country_filter),
        gdp_per_capita=scripts.get_gdp(country_name, is_per_capita=True),
        gdp=scripts.get_gdp(country_name),
        current_time=scripts.get_current_time_in_timezone(country_filter),
        stock_data=stock_data,
        is_global=is_global,
        country_index=country_index,
        stock_date=stock_date
    )


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
    query = request.args.get('query', '').lower()
    
    if len(query) < 2:
        return redirect(url_for('views.home'))
    
    results = [x['name'] for x in config.COUNTRY_LIST if query in x['name'].lower()]
    return jsonify(results)


@views.route('/comments', methods=['GET'])
def comments():
    news_id = request.args.get('id', '').lower()
    category = request.args.get('category', '').lower()

    comments = json_util.read_json(config.COMMENTS_PATH)
    
    if not scripts.valid_category(category) or not news_id:
        message = 'We apologize, but there was an error. Please try again later.'
    elif not comments['enabled']:
        message = 'We apologize, but comments are temporarily disabled. You can try again later.'
    else:
        message = ''

    referer = request.headers.get('Referer', url_for('views.home'))
    if message:
        flash(message, 'error')
        return redirect(referer)

    cache = json_util.read_json(f"{config.CACHE_PATH}/{category}")
    for cache_page in cache:
        if cache_page == 'created_at': continue
        
        for story in cache[cache_page]:
            if story['id'] == news_id:
                news_link = story['link']

                comments_file = json_util.read_json(config.COMMENTS_PATH)
                telemetry_file = json_util.read_json(config.TELEMETRY_PATH)
                
                story_info = story
                
                story_info['total_clicks'] = telemetry_file[news_id]['clicks'] if news_id in telemetry_file else 0
                story_info['total_comments'] = len(comments_file[news_id]) if news_id in comments_file else 0
                
                # If there's no image (default is Infomundi's logo), we use scraping to get the news image.
                if 'infomundi' in story['media_content']['url']:
                    preview_data = scripts.get_link_preview(news_link)
                    
                    if 'infomundi' in preview_data['image']:
                        preview_data['title'] = story['title']
                        preview_data['description'] = scripts.remove_html_tags(story['description'])
                        preview_data['image'] = story['media_content']['url']
                    
                    story['media_content']['url'] = preview_data['image']
                    json_util.write_json(cache, f"{config.CACHE_PATH}/{category}")
                else:
                    preview_data = {}
                    preview_data['image'] = story['media_content']['url']
                    preview_data['description'] = scripts.remove_html_tags(story['description'])
                    preview_data['title'] = story['title']
                
                break
        else:
            continue
        
        break
    else:
        flash('We apologize, but there was an error. Please try again later.', 'error')
        return redirect(referer)

    scripts.add_click(news_id)
    
    FULL_URL = f'https://infomundi.net/comments?id={news_id}&category={category}'
    session['last_visited_news'] = FULL_URL

    session['entered_comments_at'] = time()
    
    return render_template('comments.html', 
        page='Comments', 
        comments=comments[news_id] if news_id in comments else False, 
        news_link=news_link, 
        id=news_id, 
        story_info=story, 
        preview_data=preview_data, 
        user=current_user, 
        last_visited_country=session.get('last_visited_country', ''),
        is_mobile=scripts.detect_mobile(request),
        category=category
    )


@views.route('/add_comment', methods=['POST'])
def add_comment():
    referer = request.headers.get('Referer', url_for('views.home'))
    
    comments = json_util.read_json(config.COMMENTS_PATH)
    if not comments['enabled']:
        flash('We apologize, but comments are temporarily disabled. Please try again later.', 'error')
        
        return redirect(referer)
    
    token = request.form['cf-turnstile-response'] # Retrieve token from post data with key 'cf-turnstile-response'
    if not scripts.valid_captcha(token):
        flash('Invalid captcha! Are you a robot?', 'error')
        return redirect(referer)

    entered_comments_at = session.get('entered_comments_at', '')

    if not entered_comments_at:
        flash('There was an error processing your comment. Please make sure your browser supports cookies.', 'error')
        return redirect(referer)

    elapsed_time = time() - entered_comments_at
    cooldown_time = 10
    
    if elapsed_time < cooldown_time:
        remaining_time = int(cooldown_time - elapsed_time)
        flash(f'Hold up! Wait a couple of seconds, we need to make sure you are not a robot. Cooldown: {remaining_time}', 'error')
        return redirect(referer)

    name = current_user.username if current_user.is_authenticated else request.form['name']
    comment_text = request.form['comment']

    # Shady users may edit the request using a tool like burpsuite to bypass the form restriction. We must check input length regardless.
    if len(comment_text) > 300 or len(name) > 30:
        flash('Please limit your input accordingly.', 'error')
        return redirect(referer)

    # Checks if the user needs a random name.
    is_random_name = False
    if not name:
        name = choice(config.NICKNAME_LIST)
        is_random_name = True
    
    # Checks if the news really exist (we can't trust user input)
    news_id = request.form.get('id', '')
    category = request.form.get('category', '')

    if not scripts.valid_category(category) or not news_id:
        flash('We apologize, but there was an error. Please try again later.', 'error')
        return redirect(referer)

    cache = json_util.read_json(f"{config.CACHE_PATH}/{category}")

    for key, items in cache.items():
        if not key.startswith('page'): continue

        for item in items:
            if item['id'] == news_id: break
        else:
            continue
        break
    else:
        flash('We apologize, but there was an error. Please try again later.', 'error')
        return redirect(referer)

    new_comment = {
        'name': name,
        'random_name': is_random_name,
        'is_admin': True if current_user.is_authenticated and current_user.role == 'admin' else False,
        'is_logged_in': True if current_user.is_authenticated else False,
        'text': comment_text,
        'link': session.get('last_visited_news', ''),
        'id': scripts.create_comment_id()
    }

    if news_id not in comments:
        comments[news_id] = []

    comments[news_id].append(new_comment)
    json_util.write_json(comments, f'{config.COMMENTS_PATH}')
    
    scripts.check_in_badlist(new_comment)
    
    flash('Thank you for your comment! Sharing your opinion is safe with us.')
    return redirect(referer)
