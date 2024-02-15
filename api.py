import os
from flask import Blueprint, request, redirect, jsonify, url_for, flash, session
from flask_login import current_user, login_required
from datetime import datetime
from random import choice
from time import time

from website_scripts import config, json_util, scripts, comments_util, notifications, models, extensions, immutable
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

    url = f'https://infomundi.net/news?country={code}'
    return redirect(url)


@api.route('/comments', methods=['GET', 'POST'])
@api.route('/comments/<comment_id>/<action>', methods=['POST'])
def comments(comment_id=None, action=None):
    """API endpoint to handle everything about comments.
    
    Arguments:
        <comment_id> - The name says by itself. 
        <action> - Must be in ['likes', 'dislikes', 'report']. Actions to perform on the comment.

    No arguments:
        This endpoint can be called without arguments. We use the user's session cookie to get the news ID he's accessing and search for its comments in the database.
    """

    # Users must be authenticated in order to interact with the comments section.
    if not current_user.is_authenticated and request.method == 'POST':
        return jsonify( {'message': 'You must be authenticated to perform this action.'} ), 401 # Unauthorized

    # This is the cookie the "comments" button on top of news uses
    clicked = request.cookies.get('clicked', '')
    if not clicked:
        news_id = session.get('visited_news', '')
        category = session.get('visited_category', '')
        if not news_id or not category:
            return jsonify( {'message': 'There was an error.'} ), 400
    else:
        news_id = clicked.split('-')[0]
        category = clicked.split('-')[1]

    # Check if category is valid
    if clicked and not scripts.valid_category(category):
        flash('Something went wrong.')
        return redirect(url_for('views.home'))

    # Check if news exist
    cache = json_util.read_json(f'{config.CACHE_PATH}/{category}')
    for item in cache['stories']:
        if item['id'] == news_id:
            break
    else:
        flash('Something went wrong.')
        return redirect(url_for('views.home'))

    if request.method == 'GET':
        # Initialize the variable to send later
        comments_with_replies = {}
        comments_with_replies['total'] = models.Comment.query.filter_by(news_id=news_id).count()
        comments_with_replies['comments'] = []
        
        top_level_comments = models.Comment.query.filter_by(news_id=news_id, parent_comment_id=None).all()
        for comment in top_level_comments:
            comment_dict = {
                'id': comment.comment_id,
                'text': comment.text,
                'userName': comment.user.username,
                'userRole': comment.user.role,
                'userAvatar': comment.user.avatar_url,
                'timestamp': comment.timestamp,
                'likes': comment.likes,
                'dislikes': comment.dislikes,
                'replies': comments_util.get_replies(comment)  # Use the helper function to get replies
            }
            comments_with_replies['comments'].append(comment_dict)

        sort_by = request.args.get('sort', 'top')
        orders = ['top', 'newest', 'oldest']

        if sort_by not in orders or not comments_with_replies['comments']:
            return jsonify(comments_with_replies)
        else:
            comments_with_replies['comments'] = comments_util.sort_comments(comments_with_replies['comments'], sort_by)
            return jsonify(comments_with_replies)

    else:
        # Handle actions
        if comment_id:
            if action not in ['like', 'dislike', 'report']:
                return jsonify({"message": "Invalid action. Use 'like' or 'dislike'."}), 400

            comment = models.Comment.query.get_or_404(comment_id)
            existing_reaction = models.CommentReaction.query.filter_by(comment_id=comment_id, user_id=current_user.user_id).first()

            if existing_reaction and existing_reaction.action == action:
                # User has already performed this action; remove it
                extensions.db.session.delete(existing_reaction)
                if action == 'like':
                    comment.likes = max(comment.likes - 1, 0)  # Ensure likes don't go negative
                elif action == 'report':
                    comment.reports = max(comment.reports - 1, 0) # Ensure reports don't go negative
                else:
                    comment.dislikes = max(comment.dislikes - 1, 0)  # Ensure dislikes don't go negative
                message = f'Your {action} has been removed.'
            elif action in ['like', 'dislike'] and (existing_reaction and existing_reaction.action != action):
                # User has performed the opposite action; switch it
                existing_reaction.action = action
                if action == 'like':
                    comment.likes += 1
                    comment.dislikes = max(comment.dislikes - 1, 0)  # Ensure dislikes don't go negative
                else:
                    comment.dislikes += 1
                    comment.likes = max(comment.likes - 1, 0)  # Ensure likes don't go negative
                message = f'Your {action} has been updated.'
            else:
                # User has not reacted to this comment yet; add new reaction
                new_reaction = models.CommentReaction(reaction_id=scripts.generate_id(10), comment_id=comment_id, user_id=current_user.user_id, action=action, timestamp=datetime.utcnow().isoformat() + 'Z')
                extensions.db.session.add(new_reaction)
                if action == 'like':
                    comment.likes += 1
                elif action == 'report':
                    comment.reports += 1
                    if comment.reports == 5: # Sends webhook if reports hit 5
                        notifications.post_webhook(
                            {'text': f"""@everyone

# Comment has been reported X times

Users are upset with a specific comment, and we should look into that.

**Comment ID:** {comment.comment_id}  
**Content:** {comment.text}  
**User ID:** {comment.user.user_id}  
**Username:** {comment.user.username}  
**News ID:** {comment.news_id}

"""})
                else:
                    comment.dislikes += 1
                message = f'Comment {action}ed successfully'

            extensions.db.session.commit()
            return jsonify({'message': message})
        
        try:
            data = request.json
        except Exception:
            return jsonify( {'message': 'An error has ocurred.'} ), 400 # Bad request

        if not data.get('text', ''):
            return jsonify( {'message': 'No comment provided.'} ), 406 # Not Acceptable

        # Reply-to
        parent_comment_id = data.get('parentId', '')

        # Sanitize input
        data['text'] = scripts.sanitize_input(data['text'])

        # If top level comment, just add it to the list.
        if not parent_comment_id:
            # We just need to save the id of the user who commented, so we can retrive its username and avatar when pulling comments.
            new_comment = models.Comment(
                text=data['text'],
                comment_id=scripts.generate_id(),
                user_id=current_user.user_id,
                news_id=news_id,
                timestamp=datetime.utcnow().isoformat() + 'Z'
            )
            extensions.db.session.add(new_comment)
            extensions.db.session.commit()
        else:
            # If it's a reply, we get its parent comment and add to the comments database.
            parent_comment = models.Comment.query.get_or_404(parent_comment_id)
            reply_comment = models.Comment(
                text=data['text'],
                comment_id=scripts.generate_id(),
                user_id=current_user.user_id,
                news_id=parent_comment.news_id,  # Inherit news_id from parent comment
                parent_comment_id=parent_comment_id,
                timestamp=datetime.utcnow().isoformat() + 'Z'
            )
            extensions.db.session.add(reply_comment)
            extensions.db.session.commit()
        
        scripts.add_telemetry(news_id, 'comments')
        return jsonify({'success': True}), 201


@api.route('/summarize_story', methods=['GET'])
@login_required
def summarize_story():
    news_id = session.get('visited_news', '')
    category = session.get('visited_category', '')

    if not news_id or not category:
        return jsonify({'success': False}), 406 # Not acceptable

    filename = f'{config.CACHE_PATH}/{category}'
    
    cache = json_util.read_json(f'{config.CACHE_PATH}/{category}')
    for story in cache['stories']:
        if story['id'] == news_id:
            response = scripts.gpt_summarize(story['link'])
            if response:
                story['gpt_summarize'] = response
                json_util.write_json(cache, f'{config.CACHE_PATH}/{category}')
            else:
                response = story['description']
            
            break
    else:
        return jsonify({'success': False}), 406 # Not acceptable

    return jsonify({'response': response}), 200
