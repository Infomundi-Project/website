from flask import Blueprint, request, redirect, jsonify, url_for, flash, session, abort
from flask_login import current_user, login_required
from sqlalchemy import or_, and_
from datetime import datetime
from random import choice
from time import time

from website_scripts import config, json_util, scripts, notifications, models, extensions, immutable
from views import make_cache_key
from auth import admin_required

api = Blueprint('api', __name__)


@api.route('/get-description', methods=['GET'])
@extensions.cache.cached(timeout=60*60*24, query_string=True) # 24 hours
def get_description():
    news_id = request.args.get('id')

    story = models.Story.query.filter_by(story_id=news_id).first()
    if story:
        data = {}
        data['title'] = scripts.sanitize_input(story.title)
        data['description'] = scripts.sanitize_input(story.description)
        data['publisher'] = scripts.sanitize_input(story.publisher.name)
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


@api.route('/search', methods=['POST'])
def search():
    """Search for valid countries in our database.
    
    Argument: str
        GET 'query' parameter. A simple string, like 'brazil'.
    """
    query = request.form.get('query', '').lower()
    if len(query) < 2:
        return redirect(url_for('views.home'))
    
    countries = [x['name'].lower() for x in config.COUNTRY_LIST]
    
    results = [x.lower() for x in countries if scripts.string_similarity(query, x) > 80]
    if results:
        code = [x['code'] for x in config.COUNTRY_LIST if x['name'].lower() == results[0]][0]
    else:
        code = 'ERROR'

    url = f'https://infomundi.net/news?country={code}&section=general&page=1'
    return redirect(url)


@api.route('/summarize_story', methods=['GET'])
def summarize_story():
    # This is safe because only who has access to the secret key can control the session variables.
    news_id = session.get('visited_news', '')
    category = session.get('visited_category', '')

    if not news_id or not category:
        return jsonify({'success': False}), 406 # Not acceptable

    story = models.Story.query.filter_by(story_id=news_id).first()

    response = scripts.gpt_summarize(story.link)
    if response:
        # We convert the json response to a dict in order to store it in the database
        story.gpt_summary = json_util.loads_json(response)
        extensions.db.session.commit()
    else:
        return jsonify({'response': response}), 500

    return jsonify({'response': response}), 200


@api.route('/get_stories', methods=['GET'])
@extensions.cache.cached(timeout=60*60, query_string=True) # 1h cached
def get_stories():
    """Returns jsonified list of stories based on certain criteria. Cached for 1h (60s * 60)."""
    country = request.args.get('country', 'br', type=str).lower()
    category = request.args.get('category', 'general', type=str).lower()
    page = request.args.get('page', 1, type=int)
    order_by = request.args.get('order_by', 'created_at', type=str).lower()
    order_dir = request.args.get('order_dir', 'desc', type=str).lower()

    # br_general, us_general and so on
    selected_filter = f'{country}_{category}'
    if not scripts.valid_category(selected_filter):
        return jsonify({'error': 'This category is not yet supported!'}), 500

    valid_order_columns = ('created_at', 'clicks', 'title', 'pub_date')
    if order_by not in valid_order_columns:
        order_by = 'created_at'

    if order_dir == 'asc':
        order_criterion = getattr(models.Story, order_by).asc()
    else:
        order_criterion = getattr(models.Story, order_by).desc()

    # Page should be between 1 and 999
    if not (1 <= page <= 9999):
        page = 1

    stories_per_page = 9
    start_index = (page - 1) * stories_per_page
    stories = models.Story.query.filter(
        and_(
            models.Story.category_id == selected_filter,
            models.Story.media_content_url.contains('bucket.infomundi.net')
        )
    ).order_by(order_criterion).offset(start_index).limit(stories_per_page).all()

    stories_list = [
        {
            'story_id': story.story_id,
            #'created_at': story.created_at,
            'title': story.title,
            'description': story.description,
            #'gpt_summary': story.gpt_summary,
            'clicks': story.clicks,
            'link': story.link,
            'pub_date': story.pub_date,
            #'category_id': story.category_id,
            'publisher': {
                'name': story.publisher.name,
                'link': story.publisher.link,
                'favicon': story.publisher.favicon
            },
            'media_content_url': story.media_content_url,
        }
        for story in stories
    ]

    session['category'] = category
    session['order_by'] = order_by
    session['order_dir'] = order_dir

    return jsonify(stories_list)
