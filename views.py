import os
from flask import Blueprint, render_template, request, redirect, jsonify, url_for, flash, make_response, session
from flask_login import current_user, login_required
from random import choice, shuffle, randint
from sqlalchemy import or_
from time import time

from website_scripts import scripts, config, json_util, immutable, search, notifications, image_util, extensions, models
from auth import admin_required, in_maintenance

views = Blueprint('views', __name__)


@views.route('/', methods=['GET'])
def home():
    """Render the homepage."""
    statistics = scripts.get_statistics()

    crypto_data = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/crypto')
    world_stocks = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/stocks')
    currencies = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/currencies')

    us_indexes = world_stocks[:3]

    i = 1
    for item in crypto_data:
        world_stocks.insert(i, item)
        i += 2
    
    return render_template('homepage.html', 
        world_stocks=world_stocks, 
        us_indexes=enumerate(us_indexes), 
        page='home',
        statistics=statistics,
        country_code='en'
    )


@views.route('/maintenance', methods=['GET'])
def maintenance():
    if False:
        return redirect(url_for('views.home'))
    else:
        return render_template('maintenance.html')


@views.route('/test', methods=['GET', 'POST'])
@admin_required
def test():
    return render_template('test.html')


@views.route('/dashboard')
@login_required
@in_maintenance
def dashboard():
    return render_template('dashboard.html')


@views.route('/upload_image', methods=['POST'])
@login_required
def upload_image():
    file = request.files.get('profilePhoto')

    if not file:
        message = 'No file part'
    elif file.filename == '':
        message = 'No selected file'
    elif not image_util.allowed_file(file.filename) or not image_util.allowed_mime_type(file.stream) or not image_util.verify_image_content(file.stream) or not image_util.check_image_dimensions(file.stream):
        message = 'Invalid file'
    else:
        message = ''

    if message:
        flash(message, 'error')
        return redirect(url_for('views.dashboard'))
    
    filepath = f'{config.WEBSITE_ROOT}/static/img/users/{current_user.user_id}'
    
    image_util.convert_to_webp(file.stream, filepath)

    user_data = models.User.query.filter_by(email=current_user.email).first()
    user_data.avatar_url = f'https://infomundi.net/static/img/users/{current_user.user_id}.webp'
    extensions.db.session.commit()

    flash('File uploaded successfully!')
    return redirect(url_for('views.dashboard'))


@views.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'GET':
        return render_template('contact.html')
    else:
        token = request.form['cf-turnstile-response']
        if not scripts.valid_captcha(token):
            flash('Invalid captcha. Are you a robot?', 'error')
            return redirect(url_for('views.contact'))
        
        name = request.form.get('name', '')
        email = request.form.get('email', '')
        message = request.form.get('message', '')

        if len(name) > 25 or len(email) > 50 or len(message) > 500:
            flash('Something went wrong.', 'error')
            return redirect(url_for('views.contact'))

        data = {
        'username': 'Maximus',
        'icon_url': 'https://infomundi.net/static/img/maximus.webp',
        'text': f"""@here

# Contact Form

We got a new message.

**Name:** {name}  
**Email:** {email}

**Message:**  
{message}

---

2024 Infomundi
"""
        }
        sent_message = notifications.post_webhook(data)
        if sent_message:
            flash("Your message has been sent, thank you! Expect a return from us shortly.")
        else:
            flash("We apologize, but your message couldn't be sent. We'll look into that as soon as possible. In the meantime, feel free to send us an email at contac@infomundi.net", 'error')
        
        return redirect(url_for('views.contact'))


@views.route('/about', methods=['GET'])
def about():
    return render_template('about.html')


@views.route('/policies', methods=['GET'])
def policies():
    return render_template('policies.html')


@views.route('/team', methods=['GET'])
def team():
    return render_template('team.html')


@views.route('/donate', methods=['GET'])
def donate():
    referer = request.headers.get('Referer', url_for('views.home'))
    
    flash('We apologize, but this page is currently unavailable. Please try again later!', 'error')
    return redirect(referer)


@views.route('/news', methods=['GET'])
def get_latest_feed():
    """Serving the /news endpoint. 

    Arguments
        page_num: str
            GET 'page' parameter. Specifies the cache page. Example: '1'.
        
        country_filter: str
            GET 'country' parameter. Specifies the country code (2 digits). Example: 'br' (cca2 for Brazil).

        news_filter: str
            GET 'section' parameter. Specifies the news category. Example: 'general'.

    Return
        Renders the news page, containing 100 news per page.
    """
    
    page_num = request.args.get('page', 1)
    try:
        page_num = int(page_num)
    except TypeError:
        page_num = 1
    
    # If no country was selected, selects a random one.
    country_filter = request.args.get('country', f"{choice(['br', 'us', 'ca', 'es', 'ro', 'ly', 'ru', 'in', 'za', 'au'])}").lower()
    
    news_filter = request.args.get('section', 'general').lower()
    selected_filter = f"{country_filter}_{news_filter}"

    # Check if the selected category is valid
    if not scripts.valid_category(selected_filter):
        flash('We apologize, but there is no support available for the country you selected. If you would like to recommend sources, please send us an email at contact@infomundi.net.', 'error')
        return redirect(url_for('views.home'))

    # Searches for the country full name (may be modularized at some point)
    country_name = scripts.country_code_to_name(country_filter)

    cache = Story.query.order_by(Story.created_at.desc()).all()
    if cache:
        end_index = page_num * 100

        start_index = end_index - 100

        if start_index - 100 < 0:
            start_index = 0
        
        feeds = cache[start_index:end_index-1]

        # We shuffle the current page to provide a more dynamic experience to the user
        shuffle(feeds)
    else:
        flash('We apologize, but something went wrong. Please try again later. In the meantime, feel free to explore other countries!', 'error')
        return redirect(url_for('views.home'))
    
    # Declares the referer up here just in case 
    referer = 'https://infomundi.net/' + session.get('last_visited_country', '')
    
    # Get page language    
    page_languages = []
    languages = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/langcodes')
    for lang in languages:
        if lang['country'].lower() == country_name.lower():
            page_languages.append(lang)

    # Query will change code logic, but I think its better to just adapt everything - @behindsecurity
    original_query = ''
    query = request.args.get('query', '').lower()
    if query:
        if len(query) < 3:
            flash('Your query is too small. Please provide at least 3 characters.', 'error')
            return redirect(referer)

        for character in immutable.SPECIAL_CHARACTERS:
            query = query.replace(character, '')

        translate_language = request.args.get('translation', '').lower()

        # This value will be used in the frontend to display a badge if the query has been translated
        session['want_translate'] = False
        if translate_language:
            
            for lang in page_languages:
                if lang['lang'].lower() == translate_language.lower():
                    page_language = lang['lang_code'][:2]
                    break
            else:
                flash('Invalid language for the specified page.', 'error')
                return redirect(referer)
            
            query_translated = scripts.translate(dest_lang=page_language, msg=query)
        
            if query_translated:
                original_query = query
                query = query_translated
                session['want_translate'] = True
        
        found_stories_via_query = extensions.db.session.query(models.Story).filter(
            models.Story.category_id == selected_filter,
            or_(
                models.Story.title.ilike(f"%{query}%"),
                models.Story.description.ilike(f"%{query}%")
            )
        ).distinct().all()

        if not found_stories_via_query:
            flash(f'No stories were found with the term: "{query}".', 'error')
            return redirect(referer)

        # Change the current feed in order to make the rest of the code usable.
        feeds = found_stories_via_query
    
    try:
        favicon_database = [x.replace('.ico', '') for x in os.listdir(f'{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}/favicons')]
    except FileNotFoundError:
        favicon_database = []

    # Get telemetry
    telemetry = json_util.read_json(config.TELEMETRY_PATH)
    for story in feeds:
        if story.publisher_id in favicon_database:
            story.favicon = f"static/img/stories/{selected_filter}/favicons/{story.publisher_id}.ico"

        if telemetry.get(story.story_id, ''):
            total_clicks = telemetry[story.story_id]['clicks']
            story.total_clicks = total_clicks if total_clicks > 0 else ''
        else:
            story.total_clicks = ''
    
    # Set the page to integer to work properly with rss_template.html.
    page_num = int(page_num)

    # Else is 0 because rss_template.html should not render the pagination if the query is set.
    total_pages = len(cache) // 100 if not query else 0

    stock_data = scripts.scrape_stock_data(country_name)

    # There are countries with no national stock data available, so we use global stocks if that is the case.
    is_global = False
    if not stock_data or stock_data[0]['market_cap'] == None:
        stock_data = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/stock_data/united-states_stock')
        is_global = True

    # Gets the date from the first stock
    stock_date = stock_data[0]['date']

    try:
        country_index = [x for x in json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/stocks') if x['country']['name'].lower() == country_name.lower()][0]
        currency_info = [x for x in json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/currencies') if x['country']['name'].lower() == country_name.lower().replace(' ', '-')][0]
        country_index['currency'] = currency_info
    except IndexError as err:
        scripts.log(f'[!] Error at /views: {err} // {country_name}')
        country_index = ''
    
    GET_PARAMETERS = f'news?country={country_filter}&section={news_filter}&page={page_num}'
    session['last_visited_country'] = GET_PARAMETERS
    
    # Get area ranking
    area_ranks = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/area_ranking')
    for rank in area_ranks:
        if rank['country'].lower() == country_name.lower():
            area_rank = rank
            break
    else:
        area_rank = ''

    # Get religion info
    religions = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/religions')
    for country, religion in religions.items():
        if country.lower() == country_name.lower():
            main_religion = religion
            break
    else:
        main_religion = ''

    supported_categories = scripts.get_supported_categories(country_filter)
    session['visited_country'] = country_name.title()
    
    best_tags = models.Category.query.filter_by(category_id=selected_filter).first()
    if best_tags:
        best_tags = [x.tag for x in best_tags.tags]

    return render_template('rss_template.html', 
        feeds=enumerate(feeds),
        feed_length=len(feeds),
        query=query,
        total_pages=total_pages, 
        country_name=country_name, 
        news_filter=news_filter, 
        page_num=page_num, 
        selected_filter=selected_filter, 
        country_code=country_filter, 
        supported_categories=supported_categories, 
        all_categories=['general', 'politics', 'economy', 'technology', 'sports'],
        area_rank=area_rank,
        main_religion=main_religion,
        nation_data=scripts.get_nation_data(country_filter),
        gdp_per_capita=scripts.get_gdp(country_name, is_per_capita=True),
        gdp=scripts.get_gdp(country_name),
        current_time=scripts.get_current_time_in_timezone(country_filter),
        stock_data=stock_data,
        is_global=is_global,
        country_index=country_index,
        stock_date=stock_date,
        page_languages=page_languages,
        original_query=original_query,
        tags=best_tags if best_tags else ''
    )


@views.route('/comments', methods=['GET'])
def comments():
    news_id = request.args.get('id', '').lower()
    category = request.args.get('category', '').lower()
    
    if not scripts.valid_category(category) or not news_id:
        message = 'We apologize, but there was an error. Please try again later.'
    else:
        message = ''

    referer = request.headers.get('Referer', url_for('views.home'))
    if message:
        flash(message, 'error')
        return redirect(referer)

    story = models.Story.query.filter_by(story_id=news_id).first()
    if not story:
        flash('We apologize, but there was an error. Please try again later.', 'error')
        return redirect(referer)
    
    # Get publisher favicon
    favicon_database = [x.replace('.ico', '') for x in os.listdir(f'{config.WEBSITE_ROOT}/static/img/stories/{category}/favicons')]
    if story.publisher_id in favicon_database:
        favicon_url = f'static/img/stories/{category}/favicons/{story.publisher_id}.ico'
    else:
        favicon_url = ''

    # The current response format is not yet prepared to be displayed. We basically need to replace all underscores by spaces.
    formatted_gpt_summary = []
    if story.gpt_summary:
        summary_dict = story.gpt_summary
        
        for key, value in summary_dict.items():
            header = key.replace('_', ' ').title()
            formatted_gpt_summary.append({'header': header, 'paragraph': value})

    # Add a click to the story
    if story.clicks is None:
        story.clicks = 1
    else:
        story.clicks += 1

    # Commit changes to the database
    extensions.db.session.commit()
    
    # Assign GET parameters to the session cookie
    GET_PARAMETERS = f'comments?id={news_id}&category={category}'
    session['last_visited_news'] = GET_PARAMETERS
    
    session['visited_category'] = category
    session['visited_news'] = news_id
    
    resp = make_response(render_template('comments.html', 
        story=story,
        favicon_url=favicon_url,
        formatted_gpt_summary=formatted_gpt_summary,
        from_country_name=scripts.country_code_to_name(category.split('_')[0]),
        from_country_category=category.split('_')[1],
        from_country_code=category.split('_')[0],
        previous_news='',
        next_news='',
        hyvor_data=scripts.generate_hyvor_sso(current_user.email if current_user.is_authenticated else '')
    ))
    resp.set_cookie('clicked', f'{news_id}-{category}')
    
    return resp
