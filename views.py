from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, session, g
from flask_login import current_user, login_required
from datetime import datetime, timedelta
from random import choice, shuffle
from sqlalchemy import or_, and_
from hashlib import md5

from website_scripts import scripts, config, json_util, immutable, notifications, image_util, extensions, models
from auth import admin_required, in_maintenance, captcha_required

views = Blueprint('views', __name__)


def make_cache_key(*args, **kwargs):
    user_id = current_user.user_id if current_user.is_authenticated else 'guest'
    args_list = [request.path, user_id] + sorted((key.lower(), value.lower()) for key, value in request.args.items())
    key = md5(str(args_list).encode('utf-8')).hexdigest()
    return key


@views.route('/', methods=['GET'])
def home():
    statistics = scripts.get_statistics()

    crypto_data = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/crypto')
    world_stocks = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/stocks')
    currencies = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/currencies')

    us_indexes = world_stocks[:3]

    # We remove unused US stock data
    world_stocks.pop(1)
    world_stocks.pop(1)

    return render_template('homepage.html', 
        stock_date=world_stocks[0]['date'],
        world_stocks=enumerate(world_stocks), 
        us_indexes=enumerate(us_indexes), 
        page='home',
        statistics=statistics,
        crypto_data=crypto_data
    )


@views.route('/be-right-back', methods=['GET'])
def be_right_back():
    return render_template('maintenance.html')


@views.route('/captcha', methods=['GET', 'POST'])
def captcha():
    if request.method == 'GET':
        # If they have clearance (means that they have recently proven they're human)
        clearance = session.get('clearance', '')
        if clearance:
            now = datetime.now()

            time_difference = now - datetime.fromisoformat(clearance)
            if time_difference < timedelta(hours=config.CAPTCHA_CLEARANCE_HOURS):
                referer = scripts.is_safe_url(request.headers.get('Referer', url_for('views.home')))
                flash("We know you are not a robot, don't worry")
                return redirect(referer)

        return render_template('captcha.html')

    # Checks if the user is a robot
    token = request.form['cf-turnstile-response']
    if not scripts.valid_captcha(token):
        flash('Invalid captcha!', 'error')
        return redirect(url_for('views.captcha'))
    
    session['clearance'] = datetime.now().isoformat()
    flash('Thanks for verifying! You are not a robot after all.')
    return redirect(session.get('clearance_from', url_for('views.home')))


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
        message = 'We apologize, but no file was found!'
    elif file.filename == '':
        message = "We apologize, but we couldn't find your image!"
    elif not image_util.allowed_file(file.filename) or not image_util.allowed_mime_type(file.stream) or not image_util.verify_image_content(file.stream) or not image_util.check_image_dimensions(file.stream):
        message = "The file you provided is invalid."
    else:
        message = ''

    if message:
        flash(message, 'error')
        return redirect(url_for('views.dashboard'))
    
    # Convert the uploaded image to JPG format and save it. If conversion fails, flash an error message and redirect to the dashboard
    convert = image_util.convert_to_jpg(file.stream, f'users/{current_user.user_id}.jpg')
    if not convert:
        flash('We apologize, but something went wrong when saving your image. Please try again later.', 'error')
        return redirect(url_for('views.dashboard'))

    # Update the user's avatar URL in the database
    user_data = models.User.query.filter_by(email=current_user.email).first()
    user_data.avatar_url = f'https://bucket.infomundi.net/users/{current_user.user_id}.jpg'
    extensions.db.session.commit()

    flash('File uploaded successfully! Wait a few minutes for your profile picture to update.')
    return redirect(url_for('views.dashboard'))


@views.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'GET':
        return render_template('contact.html')

    # Checks if the user is a robot
    token = request.form['cf-turnstile-response']
    if not scripts.valid_captcha(token):
        flash('Invalid captcha. Are you a robot?', 'error')
        return redirect(url_for('views.contact'))
    
    # Gets all valus from the form
    name = scripts.sanitize_input(request.form.get('name', ''))
    email = scripts.sanitize_input(request.form.get('email', '')).lower()
    message = scripts.sanitize_input(request.form.get('message', ''))

    # Validate user input
    if not scripts.is_valid_email(email) or not (5 <= len(name) <= 50) or not (5 <= len(message) <= 1000):
        flash('Something went wrong.', 'error')
        return render_template('contact.html')

    # Gets the user ipv4 and/or ipv6
    user_ips = scripts.get_user_ip(request)

    if current_user.is_authenticated:
        email = session.get('email_address', '')
        login_message = f"Yes, as {email}"
    else:
        login_message = 'No'

    # Formats the from message
    from_formatted = f'{name} - {email}'

    email_body = f"""This message was sent through the contact form in our website.

Authenticated: {login_message}
From: {from_formatted}
IP: {' '.join(user_ips).strip()}
Country: {scripts.get_user_country(request)}
Timestamp: {scripts.get_current_date_and_time()} UTC


{message}"""

    sent_message = notifications.send_email('contact@infomundi.net', 'Infomundi - Contact Form', email_body, email, f'{name} <{email}>')
    if sent_message:
        flash("Your message has been sent, thank you! Expect a return from us shortly.")
    else:
        flash("We apologize, but looks like that the contact form isn't working. We'll look into that as soon as possible. In the meantime, feel free to send us an email directly at contact@infomundi.net", 'error')
    
    return render_template('contact.html')


@views.route('/about', methods=['GET'])
@captcha_required
def about():
    return render_template('about.html')


@views.route('/policies', methods=['GET'])
def policies():
    return render_template('policies.html')


@views.route('/team', methods=['GET'])
@captcha_required
def team():
    return render_template('team.html')


@views.route('/donate', methods=['GET'])
def donate():
    referer = scripts.is_safe_url(request.headers.get('Referer', url_for('views.home')))
    
    flash('We apologize, but this page is currently unavailable. Please try again later!', 'error')
    return redirect(referer)


@views.route('/news', methods=['GET'])
def get_latest_feed():
    """Serving the /news endpoint. 

    Arguments:
        page_num: str
            GET 'page' parameter. Specifies the cache page. Example: '1'.
        
        country_filter: str
            GET 'country' parameter. Specifies the country code (2 digits). Example: 'br' (cca2 for Brazil).

        news_filter: str
            GET 'section' parameter. Specifies the news category. Example: 'general'.

    Behavior:
        Renders the news page, containing 100 news per page.
    """
    page_num = request.args.get('page', 1, type=int)
    
    # If no country was selected, selects a random one.
    country_filter = request.args.get('country', f"{choice(
        ['br', 'us', 'ca', 'es', 'ro', 'ly', 'ru', 'in', 'za', 'au'])}",
         type=str).lower()
    
    # Gets the news filter from the url. Defaults to 'general'.
    news_filter = request.args.get('section', 'general', type=str).lower()
    
    # Format news filter (e.g. br_general or us_general and so on)
    selected_filter = f"{country_filter}_{news_filter}"

    # Check if the selected category is valid
    if not scripts.valid_category(selected_filter):
        flash('We apologize, but there is no support available for the country you selected. If you would like to recommend sources, please send us an email at contact@infomundi.net.', 'error')
        return redirect(url_for('views.home'))

    # Searches for the country full name (may be modularized at some point)
    country_name = scripts.country_code_to_name(country_filter)

    # Declares the referer up here just in case. No open redirect here because the session is encrypted and we control it.
    referer = 'https://infomundi.net/' + session.get('last_visited_country', '')
    
    # Get page language
    page_languages = []
    languages = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/langcodes')
    for lang in languages:
        if lang['country'].lower() == country_name.lower():
            page_languages.append(lang)

    # Query will change code logic, but I think its better to just adapt everything
    original_query = ''
    query = scripts.sanitize_input(request.args.get('query', '').lower())
    if query:
        if len(query) < 3:
            flash('Your query is too small. Please provide at least 3 characters.', 'error')
            return redirect(referer)

        # Deactivated!
        translate_language = '' #request.args.get('translation', '').lower()

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
            models.Story.media_content_url.contains('bucket.infomundi.net'),
            or_(
                models.Story.title.ilike(f"%{query}%"),
                models.Story.description.ilike(f"%{query}%")
            )
        ).order_by(models.Story.created_at.desc()).limit(50).all()

        if not found_stories_via_query:
            flash(f'No stories were found with the term: "{query}".', 'error')
            return redirect(referer)

        # Change the current feed in order to make the rest of the code usable.
        feeds = found_stories_via_query
    else:
        # Calculates start index based on the page number
        start_index = page_num * 100

        if start_index == 100:
            start_index = 0

        # Retrieve the cache
        """
        cache = models.Story.query.filter(
            and_(
                models.Story.category_id == selected_filter,
                models.Story.media_content_url.contains('bucket.infomundi.net')
            )
        ).order_by(models.Story.created_at.desc()).offset(start_index).limit(100).all()
        """
        cache = []
        if cache:
            flash('We apologize, but something went wrong. Please try again later.', 'error')
            return redirect(url_for('views.home'))

        # Get the feed and shuffle it
        feeds = cache
        shuffle(feeds)

    best_tags = models.Category.query.filter_by(category_id=selected_filter).first()
    if best_tags:
        best_tags = [x.tag for x in best_tags.tags]

        for story in feeds:
            story.tags = []
            
            for tag in best_tags:
                if tag in story.title.lower() or tag in story.description.lower():
                    story.tags.append(tag)
    else:
        best_tags = []

    # There are countries with no national stock data available, so we use global stocks if that is the case.
    is_global = False
    stock_data = scripts.scrape_stock_data(country_name)
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
    
    GET_PARAMETERS = f'news?country={country_filter}'
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

    seo_title = f'Infomundi - {country_name.title()} {news_filter.title()}'
    seo_description = f"Whether you're interested in local events, national happenings, or international affairs affecting {country_name.title()}, Infomundi is your go-to source for news. Visit us today to stay informed and connected with {country_name.title()} and beyond."

    return render_template('rss_template.html', 
        seo_data=(seo_title, seo_description),
        country_name=country_name, 
        news_filter=news_filter, 
        country_code=country_filter,
        supported_categories=supported_categories, 
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
        query=query,
        tags=best_tags if best_tags else ''
    )


@views.route('/comments', methods=['GET'])
def comments():
    referer = scripts.is_safe_url(request.headers.get('Referer', url_for('views.home')))
    
    news_id = request.args.get('id', '').lower()
    # Check if has the length of a md5 hash
    if not scripts.has_md5_hash(news_id):
        flash('We apologize, but the ID you provided is not valid. Please try again.', 'error')
        return redirect(referer)

    # Check if story exists
    story = models.Story.query.filter_by(story_id=news_id).first()
    if not story:
        flash("We apologize, but we could not find the story you were looking for. Please try again later.", 'error')
        return redirect(referer)

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
    
    # Set session information
    session['last_visited_news'] = f'comments?id={news_id}'
    session['visited_category'] = story.category_id
    session['visited_news'] = news_id
    
    # Create the SEO title. Must NOT have more than 60 characters.
    seo_title = 'Infomundi - '
    for word in story.title.split(' '):
        seo_title += word
        
        if len(seo_title) >= 60:
            break
        
        seo_title += ' '

    # Create the SEO description. Must NOT have more than 150 characters.
    seo_description = ''
    for word in story.description.split(' '):
        seo_description += word
        
        if len(seo_description) >= 150:
            break
        
        seo_description += ' '
    
    country = story.category_id.split('_')[0]
    section = story.category_id.split('_')[1]

    favicon_url = f'https://bucket.infomundi.net/favicons/{story.category_id}/{story.publisher_id}.ico'
    return render_template('comments.html', 
        story=story,
        seo_data=(seo_title, seo_description),
        favicon_url=favicon_url,
        formatted_gpt_summary=formatted_gpt_summary,
        from_country_name=scripts.country_code_to_name(story.category_id.split('_')[0]),
        referer='https://infomundi.net/' + session.get('last_visited_country', f'news?country={country}'),
        from_country_category=story.category_id.split('_')[1],
        from_country_code=story.category_id.split('_')[0],
        page_language=scripts.detect_language(story.title + ' ' + story.description),
        previous_news='',
        next_news=''
    )
