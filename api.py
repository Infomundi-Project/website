from flask import Blueprint, request, redirect, jsonify, url_for, session
from flask_login import current_user, login_required
from sqlalchemy import or_, and_, cast, func
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from sqlalchemy.types import Date
from random import shuffle

from website_scripts import config, json_util, scripts, notifications,\
    models, extensions, immutable, input_sanitization, friends_util, \
    country_util, totp_util, security_util, hashing_util, llm_util, decorators

api = Blueprint('api', __name__)


def make_cache_key(*args, **kwargs):
    user_id = current_user.id if current_user.is_authenticated else 'guest'
    args_list = [request.path, user_id] + sorted((key.lower(), value.lower()) for key, value in request.args.items())
    key = hashing_util.md5_hash_text(str(args_list))
    return key


@api.route('/story/<action>', methods=['POST'])
@decorators.api_login_required
def story_reaction(action):
    # Validate the action
    if action not in ('like', 'dislike'):
        return jsonify({"error": "Invalid action. Use 'like' or 'dislike'."}), 400

    # Get the story_id from the JSON body
    data = request.get_json()
    story_id = data.get('id')
    if not story_id:
        return jsonify({"error": "Story ID is required."}), 400

    # Find the story
    story = models.Story.query.get(story_id)
    if not story:
        return jsonify({"error": "Story not found."}), 404

    # Check if a reaction already exists for this story and user
    existing_reaction = models.StoryReaction.query.filter_by(
        story_id=story_id, user_id=current_user.id).first()

    # Initialize response flags
    is_liked = is_disliked = False

    # If a reaction exists, update it; otherwise, create a new one
    if existing_reaction:
        if existing_reaction.action == action:
            # If the reaction is already the same as the requested action, delete it (unreact)
            extensions.db.session.delete(existing_reaction)
            
            if action == 'like':
                story.likes -= 1
            elif action == 'dislike':
                story.dislikes -= 1
            
            message = f"{action.capitalize()} removed"
        else:
            # If the reaction is different, update it
            existing_reaction.action = action
            
            if action == 'like':
                story.likes += 1
                story.dislikes -= 1
                is_liked = True
            elif action == 'dislike':
                story.dislikes += 1
                story.likes -= 1
                is_disliked = True

            message = f"Reaction updated to {action}"
            is_liked = action == 'like'
            is_disliked = action == 'dislike'
    else:
        # Create a new reaction
        new_reaction = models.StoryReaction(
            story_id=story_id,
            user_id=current_user.id,
            action=action
        )
        extensions.db.session.add(new_reaction)

        if action == 'like':
            story.likes += 1
            is_liked = True
        elif action == 'dislike':
            story.dislikes += 1
            is_disliked = True

        message = f"Story {action}d"
        is_liked = action == 'like'
        is_disliked = action == 'dislike'

    extensions.db.session.commit()
    return jsonify({
        "message": message,
        "is_liked": is_liked,
        "likes": story.likes,
        "dislikes": story.dislikes,
        "is_disliked": is_disliked
    }), 201 if not existing_reaction else 200


@api.route('/totp/generate', methods=['GET'])
@login_required
def generate_totp():
    if current_user.totp_secret:
        return jsonify({'status': 'Not Allowed'}), 403

    session['totp_secret'] = totp_util.generate_totp_secret()
    return jsonify({
        'secret_key': session['totp_secret'],
        'qr_code': totp_util.generate_qr_code(session['totp_secret'], session['email_address'])
        }), 200


@api.route('/totp/setup', methods=['GET'])
@login_required
def setup_totp():
    # If the user already has a secret, then they don't need to finish setup again
    if current_user.totp_secret:
        return jsonify({'status': 'Not Allowed'}), 403

    code = request.args.get('code', '')
    totp_secret = session['totp_secret']

    is_valid = totp_util.verify_totp(totp_secret, code)
    if not is_valid:
        return jsonify({'valid': False}), 200

    # Generates a super random recovery token
    totp_recovery_token = security_util.generate_nonce()

    # Gets the key information from user's session
    key_salt = current_user.derived_key_salt
    key_value = session['key_value']

    # Saves the TOTP information encrypted in the database
    current_user.totp_secret = security_util.encrypt(totp_secret, salt=key_salt, key=key_value)
    current_user.totp_recovery = hashing_util.string_to_argon2_hash(totp_recovery_token)
    extensions.db.session.commit()

    # There's no need to keep this info in the user's session
    del session['totp_secret']

    return jsonify({'valid': True, 'totp_recovery_token': totp_recovery_token}), 200


@api.route('/countries', methods=['GET'])
@login_required
def get_countries():
    return jsonify(country_util.get_countries())


@api.route('/countries/<int:country_id>/states', methods=['GET'])
@login_required
def get_states(country_id):
    return jsonify(country_util.get_states(country_id))


@api.route('/states/<int:state_id>/cities', methods=['GET'])
@login_required
def get_cities(state_id):
    return jsonify(country_util.get_cities(state_id))


@api.route('/user/friends', methods=['GET'])
@extensions.cache.cached(timeout=60*2, query_string=True, make_cache_key=make_cache_key)
@login_required
def get_friends():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    friends_list = friends_util.get_friends_list(current_user.id)
    total_friends = len(friends_list)
    online_friends = sum(1 for friend in friends_list if friend.is_online)
    paginated_friends = friends_list[(page - 1) * per_page: page * per_page]

    friends_data = [{
        'username': friend.username,
        'display_name': friend.display_name,
        'user_id': friend.id,
        'avatar_url': friend.avatar_url,
        'level': friend.level,
        'is_online': friend.is_online,
        'last_activity': friend.last_activity
    } for friend in paginated_friends]

    return jsonify({
        "friends": friends_data,
        "total_friends": total_friends,
        "online_friends": online_friends,
        "page": page,
        "per_page": per_page,
        "total_pages": (total_friends + per_page - 1) // per_page
    }), 200


@api.route('/user/<user_id>/status', methods=['GET'])
def get_user_status(user_id):
    user = models.User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if not user.last_activity:
        return jsonify({'is_online': False, 'last_activity': user.last_activity})

    # Save to the database
    user.is_online = user.check_is_online()
    extensions.db.session.commit()
    
    return jsonify({'is_online': user.is_online, 'last_activity': user.last_activity})


@api.route('/user/status/update', methods=['GET'])
@login_required
def update_user_status():
    current_user.is_online = True
    current_user.last_activity = datetime.utcnow()
    
    extensions.db.session.commit()
    return jsonify({'message': 'Status updated successfully'})


@api.route('/get_country_code', methods=['GET'])
@extensions.cache.cached(timeout=60*60*24*30, query_string=True) # 30 days
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
        code = [x['code'].lower() for x in config.COUNTRY_LIST if x['name'].lower() == results[0]][0]
    else:
        code = 'ERROR'

    return redirect(f'https://infomundi.net/news?country={code}')


@api.route('/story/summarize/<story_id>', methods=['GET'])
@extensions.limiter.limit("120/day;60/hour;10/minute", override_defaults=True)
def summarize_story(story_id):
    story = models.Story.query.get(story_id)
    if story.gpt_summary:
        return jsonify({'response': story.gpt_summary}), 200

    response = llm_util.gpt_summarize(story.url)
    if response:
        # We convert the json response to a dict in order to store it in the database
        story.gpt_summary = response
        extensions.db.session.commit()
    else:
        return jsonify({'response': response}), 500

    return jsonify({'response': response}), 200


@api.route('/get_stories', methods=['GET'])
@extensions.cache.cached(timeout=60*1, query_string=True) # 1 min cached
def get_stories():
    """Returns jsonified list of stories based on certain criteria. Cached for 1h (60s * 60)."""
    country = request.args.get('country', 'br', type=str).lower()
    category = request.args.get('category', 'general', type=str).lower()
    page = request.args.get('page', 1, type=int)
    order_by = request.args.get('order_by', 'created_at', type=str).lower()
    order_dir = request.args.get('order_dir', 'desc', type=str).lower()

    start_date = request.args.get('start_date', '', type=str)
    end_date = request.args.get('end_date', '', type=str)
    query = request.args.get('query', '', type=str)

    # br_general, us_general and so on
    category_name = f'{country}_{category}'
    if not scripts.is_valid_category(category_name):
        return jsonify({'error': 'This category is not yet supported!'}), 501

    valid_order_columns = ('created_at', 'clicks', 'title', 'pub_date')
    if order_by not in valid_order_columns:
        order_by = 'created_at'

    if order_dir == 'asc':
        order_criterion = getattr(models.Story, order_by).asc()
    else:
        order_criterion = getattr(models.Story, order_by).desc()

    # Page should be between 1 and 9999
    if not (1 <= page <= 9999):
        page = 1

    category_id = models.Category.query.filter_by(name=category_name).first()

    # Basic filtering. Category id should match and story should have image.
    query_filters = [
        models.Story.category_id == category_id.id,
        models.Story.has_image == True
    ]

    # Filter by search query
    if query:
        query_filters.append(
            func.match(models.Story.title, models.Story.description, query)
        )

    # Filter by date range
    if start_date and end_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()

        query_filters.append(
            and_(
                cast(models.Story.pub_date, Date) >= start_date_obj,
                cast(models.Story.pub_date, Date) <= end_date_obj
            )
        )

    stories_per_page = 9
    start_index = (page - 1) * stories_per_page
    stories = models.Story.query.filter(
        and_(*query_filters)
    ).options(
        joinedload(models.Story.publisher)
    ).order_by(
        order_criterion,
        models.Story.id
    ).offset(
        start_index
    ).limit(
        stories_per_page
    ).all()

    stories_list = [
        {
            'story_id': story.id,
            'title': story.title,
            'description': story.description,
            # DEBUG 
            'clicks': 0,
            'likes': 0,
            'dislikes': 0,

            'link': story.url,
            'pub_date': story.pub_date,
            'publisher': {
                'name': input_sanitization.clean_publisher_name(story.publisher.name),
                'link': story.publisher.url,
                'favicon': story.publisher.favicon_url
            },
            'media_content_url': story.image_url,
        }
        for story in stories
    ]
    shuffle(stories_list)
    return jsonify(stories_list)


@api.route('/currencies')
@extensions.cache.cached(timeout=60*60) # 1h cached
def get_currencies():
    currencies = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/currencies')
    return jsonify(currencies)


@api.route('/stocks')
@extensions.cache.cached(timeout=60*60) # 1h cached
def get_stocks():
    stocks = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/stocks')
    
    # Removes unused US stocks
    del stocks[1:3]
    
    return jsonify(stocks)


@api.route('/crypto')
@extensions.cache.cached(timeout=60*60) # 1h cached
def get_crypto():
    return jsonify(json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/crypto'))
