from flask import Blueprint, request, redirect, jsonify, url_for, session
from sqlalchemy import and_, cast, desc, asc, insert
from sqlalchemy.orm import joinedload
from flask_login import current_user
from sqlalchemy.types import Date
from newsplease import NewsPlease
from datetime import datetime

from website_scripts import (
    config,
    json_util,
    scripts,
    models,
    extensions,
    input_sanitization,
    friends_util,
    country_util,
    totp_util,
    security_util,
    hashing_util,
    llm_util,
    decorators,
    comments_util,
    notifications,
    qol_util,
)

api = Blueprint("api", __name__)


def make_cache_key(*args, **kwargs):
    user_id = current_user.id if current_user.is_authenticated else "guest"
    args_list = [request.path, user_id] + sorted(
        (key.lower(), value.lower()) for key, value in request.args.items()
    )

    return hashing_util.string_to_md5_hex(str(args_list))


@api.route("/countries", methods=["GET"])
@extensions.cache.cached(timeout=60 * 60 * 24 * 30)  # 30 days
@decorators.api_login_required
def get_countries():
    return jsonify(country_util.get_countries())


@api.route("/countries/<int:country_id>/states", methods=["GET"])
@extensions.cache.cached(timeout=60 * 60 * 24 * 30)  # 30 days
@decorators.api_login_required
def get_states(country_id):
    return jsonify(country_util.get_states(country_id))


@api.route("/states/<int:state_id>/cities", methods=["GET"])
@extensions.cache.cached(timeout=60 * 60 * 24 * 30)  # 30 days
@decorators.api_login_required
def get_cities(state_id):
    return jsonify(country_util.get_cities(state_id))


@api.route("/currencies")
@extensions.cache.cached(timeout=60 * 30)  # 30m cached
def get_currencies():
    currencies = json_util.read_json(
        f"{config.WEBSITE_ROOT}/assets/data/json/currencies"
    )
    return jsonify(currencies)


@api.route("/stocks")
@extensions.cache.cached(timeout=60 * 30)  # 30m cached
def get_stocks():
    stocks = json_util.read_json(f"{config.WEBSITE_ROOT}/assets/data/json/stocks")

    # Removes unused US stocks
    del stocks[1:3]

    return jsonify(stocks)


@api.route("/crypto")
@extensions.cache.cached(timeout=60 * 30)  # 30m cached
def get_crypto():
    return jsonify(
        json_util.read_json(f"{config.WEBSITE_ROOT}/assets/data/json/crypto")
    )


@api.route("/user/friend", methods=["POST"])
@extensions.limiter.limit("12/hour;6/minute")
@decorators.api_login_required
def handle_friends():
    data = request.get_json()

    friend_id = data.get("friend_id")
    action = data.get("action")

    if action not in ("add", "accept", "reject", "delete") or not friend_id:
        return jsonify(
            success=False,
            message="Action must be 'add', 'accept', 'reject' or 'delete', and 'friend_id should be supplied.",
        )

    friend = extensions.db.session.get(models.User, friend_id)
    if not friend:
        return jsonify(success=False, message="Could not find user.")

    if action == "add":
        new_friendship_id = friends_util.send_friend_request(current_user.id, friend_id)
        notifications.notify_single(friend.id, 'friend_request', f'{current_user.username} has sent you a friend request', url=url_for('views.user_profile_by_id', public_id=current_user.get_public_id()))
        return jsonify(success=True, message="Friend request sent")

    elif action == "accept":
        if friends_util.accept_friend_request(current_user.id, friend_id):
            return jsonify(success=True, message="Friend request accepted")

        return jsonify(success=False, message="Failed to accept friend request")

    elif action == "reject":
        if friends_util.reject_friend_request(current_user.id, friend_id):
            return jsonify(success=True, message="Friend request rejected")

        return jsonify(success=True, message="Failed to reject friend request")

    else:
        if friends_util.delete_friend(current_user.id, friend_id):
            return jsonify(success=True, message="Friend request deleted")

        return jsonify(success=True, message="Failed to delete friend request")


@api.route("/user/<int:user_id>/friend/status", methods=["GET"])
@decorators.api_login_required
def friendship_status(user_id):
    status, is_sent_by_current_user = friends_util.get_friendship_status(
        current_user.id, user_id
    )
    return jsonify(status=status, is_sent_by_current_user=is_sent_by_current_user)


@api.route("/story/<action>", methods=["POST"])
@decorators.api_login_required
def story_reaction(action):
    if action not in ("like", "dislike"):
        return jsonify(error="Invalid action"), 400

    # We get an 'id' attribute, but it isn't the ID really, it's url hash (md5 hex).
    # We pretend it's the ID to lure bad actors.
    url_hash = request.get_json().get("id")
    if not url_hash:
        return jsonify(error="Story ID is required"), 400

    story = models.Story.query.filter_by(
        url_hash=hashing_util.md5_hex_to_binary(url_hash)
    ).first()
    if not story:
        return jsonify({"error": "Story not found."}), 404

    # Check if a reaction already exists for this story and user
    existing_reaction = models.StoryReaction.query.filter_by(
        story_id=story.id, user_id=current_user.id
    ).first()

    # Initialize response flags
    is_liked = is_disliked = False

    story_stats = extensions.db.session.get(models.StoryStats, story.id)
    if not story_stats:
        story_stats = models.StoryStats(story_id=story.id, views=0, likes=0, dislikes=0)
        extensions.db.session.add(story_stats)
        extensions.db.session.commit()

    # If a reaction exists, update it; otherwise, create a new one
    if existing_reaction:
        if existing_reaction.action == action:
            # If the reaction is already the same as the requested action, delete it (unreact)
            extensions.db.session.delete(existing_reaction)

            if action == "like":
                story.stats.likes -= 1
            elif action == "dislike":
                story.stats.dislikes -= 1

            message = f"{action.capitalize()} removed"
        else:
            # If the reaction is different, update it
            existing_reaction.action = action

            if action == "like":
                story.stats.likes += 1
                story.stats.dislikes -= 1
                is_liked = True
            elif action == "dislike":
                story.stats.dislikes += 1
                story.stats.likes -= 1
                is_disliked = True

            message = f"Reaction updated to {action}"
            is_liked = action == "like"
            is_disliked = action == "dislike"
    else:
        # Create a new reaction
        new_reaction = models.StoryReaction(
            story_id=story.id, user_id=current_user.id, action=action
        )
        extensions.db.session.add(new_reaction)

        if action == "like":
            story.stats.likes += 1
            is_liked = True
        elif action == "dislike":
            story.stats.dislikes += 1
            is_disliked = True

        message = f"Story {action}d"
        is_liked = action == "like"
        is_disliked = action == "dislike"

    extensions.db.session.commit()
    return jsonify(
        {
            "message": message,
            "is_liked": is_liked,
            "likes": story.stats.likes,
            "dislikes": story.stats.dislikes,
            "is_disliked": is_disliked,
        }
    ), (201 if not existing_reaction else 200)


@api.route("/totp/generate", methods=["GET"])
@decorators.api_login_required
def generate_totp():
    if current_user.is_totp_enabled:
        return jsonify({"status": "Not Allowed"}), 403

    session["totp_secret"] = totp_util.generate_totp_secret()
    return (
        jsonify(
            {
                "secret_key": session["totp_secret"],
                "qr_code": totp_util.generate_qr_code(
                    session["totp_secret"], session["email_address"]
                ),
            }
        ),
        200,
    )


@api.route("/totp/setup", methods=["GET"])
@decorators.api_login_required
def setup_totp():
    if current_user.is_totp_enabled:
        return jsonify({"status": "Not Allowed"}), 403

    code = request.args.get("code", "")
    totp_secret = session["totp_secret"]

    is_valid = totp_util.verify_totp(totp_secret, code)
    if not is_valid:
        return jsonify({"valid": False}), 200

    totp_recovery_token = current_user.setup_totp(session["totp_secret"])

    # There's no need to keep this info in the user's session anymore
    del session["totp_secret"]

    return jsonify({"valid": True, "totp_recovery_token": totp_recovery_token}), 200


@api.route("/2fa/mail/send", methods=["POST"])
@extensions.limiter.limit("7/day;5/hour;3/minute")
def send_mail_twofactor_code():
    user = extensions.db.session.get(models.User, session["user_id"])

    code = security_util.generate_random_number_sequence()
    user.mail_twofactor_code = code
    user.mail_twofactor_timestamp = datetime.now()
    extensions.db.session.commit()

    notifications.send_email(
        session["email_address"],
        f"Infomundi - {code} is Your Two-Factor Code",
        f"Your two‑factor authentication code is: {code}",
    )

    return jsonify(success=True), 200


@api.route("/2fa/mail/verify", methods=["POST"])
@decorators.api_login_required
def verify_mail_twofactor_code():
    data = request.get_json() or {}
    code = data.get("code")

    if not code:
        return jsonify(success=False, error="Missing 'code' attribute"), 400

    user = extensions.db.session.get(models.User, session["user_id"])

    # We first check if the code is valid
    if not user.check_mail_twofactor(code):
        return jsonify(success=False, error="Invalid or expired code"), 400

    # This means the user has just configured mail twofactor via settings
    if not user.is_mail_twofactor_enabled:
        recovery_token = user.setup_mail_twofactor()
        return jsonify(success=True, recovery_token=recovery_token), 200

    return jsonify(success=True), 200


@api.route("/user/friends", methods=["GET"])
@extensions.cache.cached(
    timeout=60 * 2, query_string=True, make_cache_key=make_cache_key
)
@decorators.api_login_required
def get_friends():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    friends_list = friends_util.get_friends_list(current_user.id)
    total_friends = len(friends_list)
    online_friends = sum(1 for friend in friends_list if friend.is_online)
    paginated_friends = friends_list[(page - 1) * per_page : page * per_page]

    friends_data = [
        {
            "username": friend.username,
            "display_name": friend.display_name,
            "user_id": friend.get_public_id(),
            "avatar_url": friend.avatar_url,
            "level": friend.level,
            "is_online": friend.is_online,
            "last_activity": friend.last_activity,
        }
        for friend in paginated_friends
    ]

    return (
        jsonify(
            {
                "friends": friends_data,
                "total_friends": total_friends,
                "online_friends": online_friends,
                "page": page,
                "per_page": per_page,
                "total_pages": (total_friends + per_page - 1) // per_page,
            }
        ),
        200,
    )


@api.route("/user/<user_public_id>/status", methods=["GET"])
def get_user_status(user_public_id):
    user = models.User.query.filter_by(
        public_id=security_util.uuid_string_to_bytes(user_public_id)
    ).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    if not user.last_activity:
        return jsonify({"is_online": False, "last_activity": user.last_activity})

    # Save to the database
    user.is_online = user.check_is_online()
    extensions.db.session.commit()

    return jsonify({"is_online": user.is_online, "last_activity": user.last_activity})


@api.route("/user/status/update", methods=["GET"])
@decorators.api_login_required
def update_user_status():
    current_user.is_online = True
    current_user.last_activity = datetime.now()

    extensions.db.session.commit()
    return jsonify({"message": "Success!"})


@api.route("/get_country_code", methods=["GET"])
# @extensions.cache.cached(timeout=60 * 60 * 24 * 30, query_string=True)  # 30 days
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
    country = country_util.get_country(name=request.args.get("country", ""))
    return jsonify({"countryCode": country.iso2 if country else ""})


@api.route("/autocomplete", methods=["GET"])
def autocomplete():
    """Autocomplete endpoint for country names.

    Argument: str
        GET 'query' parameter. A simple string, for example 'Bra'.

    Return: jsonify(list)
        Returns a list of countries relevant to the query. An example would be:

        ['Brazil', 'Gibraltar']
    """
    query = request.args.get("query", "")
    if len(query) < 2:
        return redirect(url_for("views.home"))

    results = [x.name for x in country_util.get_country(name=query, ilike=True)]
    return jsonify(results)


@api.route("/search", methods=["POST"])
def search():
    """Search for valid countries in our database, based on an incomplete query.

    Argument: str
        GET 'query' parameter. A simple, perhaps incomplete string that makes up for a country name. E.g. 'bra' for Brazil or Gibraltar.

    Return:
        Redirects the user to the news endpoint, passing the country CCA2 as argument. E.g. '/news?country=br' for Brazil.
    """
    query = request.form.get("query", "")
    if len(query) < 2:
        return redirect(url_for("views.home"))

    # Grabs all countries from the database based on the incomplete string
    countries = country_util.get_country(name=query, ilike=True)

    # Adds all countries and calculates the similarity percentage for each name
    similarity_data = []
    for country in countries:
        similarity_data.append(
            (country, scripts.string_similarity(query, country.name))
        )

    # Grabs the best match
    best_match_country, value = max(similarity_data, key=lambda item: item[1])

    return redirect(url_for("views.news", country=best_match_country.iso2))


@api.route("/story/summarize/<story_url_hash>", methods=["GET"])
@extensions.limiter.limit("120/day;60/hour;6/minute", override_defaults=True)
def summarize_story(story_url_hash):
    story = models.Story.query.filter_by(
        url_hash=hashing_util.md5_hex_to_binary(story_url_hash)
    ).first()
    if not story:
        return jsonify({"response": "Couldn't find the story"}), 404

    if story.gpt_summary:
        return jsonify({"response": story.gpt_summary}), 200

    try:
        article = NewsPlease.from_url(story.url)
        title = article.title
        main_text = article.maintext
        tags = scripts.extract_yake(f"{title}, {main_text}", lang_code=story.lang)
        tag_dicts = [
            {"story_id": story.id, "tag": t.strip()} for t in tags if t.strip()
        ]
        if tag_dicts:
            extensions.db.session.execute(insert(models.Tag), tag_dicts)
            extensions.db.session.commit()
    except Exception:
        title = story.title
        main_text = story.description

    response = llm_util.gpt_summarize(
        input_sanitization.gentle_cut_text(300, title),
        input_sanitization.gentle_cut_text(1700, main_text),
    )
    if not response:
        return jsonify({"response": "Summarization has failed."}), 500

    story.gpt_summary = response
    extensions.db.session.commit()
    return jsonify({"response": response}), 200


@api.route("/get_stories", methods=["GET"])
@extensions.cache.cached(timeout=60 * 15, query_string=True)  # 15 min cached
def get_stories():
    """Returns jsonified list of stories based on certain criteria. Cached for 15 min (60s * 15)."""
    country = request.args.get("country", "br", type=str).lower()
    category = request.args.get("category", "general", type=str).lower()
    page = request.args.get("page", 1, type=int)
    order_by = request.args.get("order_by", "created_at", type=str).lower()
    order_dir = request.args.get("order_dir", "desc", type=str).lower()

    start_date = request.args.get("start_date", "", type=str)
    end_date = request.args.get("end_date", "", type=str)
    # query = request.args.get('query', '', type=str)

    # br_general, us_general and so on
    category = models.Category.query.filter_by(name=f"{country}_{category}").first()
    if not category:
        return jsonify({"error": "This category is not yet supported!"}), 501

    valid_order_columns = ("created_at", "views", "title", "pub_date")
    if order_by not in valid_order_columns:
        order_by = "created_at"

    model = models.StoryStats if order_by == "views" else models.Story

    if order_dir == "asc":
        order_criterion = getattr(model, order_by).asc()
    else:
        order_criterion = getattr(model, order_by).desc()

    # Page should be between 1 and 9999
    if not (1 <= page <= 9999):
        page = 1

    # Basic filtering. Category id should match and story should have image.
    query_filters = [models.Story.category_id == category.id, models.Story.has_image]

    # if query:
    #    query_filters.append(
    #        func.match(models.Story.title, models.Story.description, query)
    #    )

    if start_date and end_date:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()

        query_filters.append(
            and_(
                cast(models.Story.pub_date, Date) >= start_date_obj,
                cast(models.Story.pub_date, Date) <= end_date_obj,
            )
        )

    stories_per_page = 9
    start_index = (page - 1) * stories_per_page
    stories = (
        models.Story.query.filter(and_(*query_filters))
        .options(joinedload(models.Story.publisher))
        .order_by(order_criterion, models.Story.id)
        .offset(start_index)
        .limit(stories_per_page)
        .all()
    )

    stories_list = [
        {
            "story_id": hashing_util.binary_to_md5_hex(story.url_hash),
            "id": story.id,
            "title": story.title,
            "tags": [tag.tag for tag in story.tags],
            "author": story.author,
            "description": story.description if story.description else "",
            "views": story.stats.views if story.stats else 0,
            "likes": story.stats.likes if story.stats else 0,
            "dislikes": story.stats.dislikes if story.stats else 0,
            "url": story.url,
            "pub_date": story.pub_date,
            "publisher": {
                "name": input_sanitization.clean_publisher_name(story.publisher.name),
                "url": story.publisher.site_url,
                "favicon_url": story.publisher.favicon_url,
            },
            "image_url": story.image_url,
        }
        for story in stories
    ]
    return jsonify(stories_list)


@api.route("/comments", methods=["POST"])
@extensions.limiter.limit("120/day;60/hour;12/minute")
def create_comment():
    data = request.get_json()
    parent_id = data.get("parent_id")
    page_id = data.get("page_id")  # A string that uniquely identifies the page
    type = data.get("type")  # Type of page which comment was posted on
    content = content = input_sanitization.gentle_cut_text(
        1000, input_sanitization.sanitize_html(data.get("content"))
    )  # Sanitizes and then gently cuts content

    if not page_id or not content:
        return jsonify(error="Missing page_id or content"), 400

    if type not in ("user", "story", "page"):
        return jsonify(error="Invalid type"), 400

    comment = models.Comment(
        page_hash=hashing_util.string_to_md5_binary(page_id),
        user_id=(
            current_user.id
            if current_user.is_authenticated
            else comments_util.get_anonymous_user().id
        ),
        content=content,
        is_flagged=comments_util.is_content_inappropriate(content),
        parent_id=parent_id,
    )
    extensions.db.session.add(comment)  # stage the INSERT
    extensions.db.session.flush()  # actually send it to the DB, get back the PK

    if type == "story":
        # Sees if the page_id refers to a valid story in the database
        story = models.Story.query.filter_by(
            url_hash=hashing_util.md5_hex_to_binary(page_id)
        ).first()
        if not story:
            return jsonify(error="Could not find story in database."), 400

        comment.url = (
            url_for("views.comments", id=story.get_public_id())
            + f"#comment-{comment.id}"
        )
        comment.story_id = story.id  # Sets the optional story_id column
        # Send notifications to the users who bookmarked this specific story.
        bookmarks = models.Bookmark.query.filter_by(story_id=story.id).all()
        if bookmarks:
            notif_dicts = [
                {
                    "user_id": b.user_id,
                    "type": "new_comment",
                    "message": "A new comment was posted on a bookmarked story",
                    "url": comment.url,
                }
                for b in bookmarks
            ]
            notifications.notify(notif_dicts)
    elif type == "user":
        profile_owner = models.User.query.filter_by(
            public_id=security_util.uuid_string_to_bytes(page_id)
        ).first()
        if not profile_owner:
            return jsonify(error="Could not find user in database."), 400

        comment.url = (
            url_for("views.user_profile_by_id", public_id=page_id)
            + f"#comment-{comment.id}"
        )
        notifications.notify(
            [
                {
                    "user_id": profile_owner.id,
                    "type": "new_comment",
                    "message": f"{comment.user.username} commented on your profile",
                    "url": comment.url,
                }
            ]
        )
    else:
        comment.url = f"https://{config.BASE_DOMAIN}/{input_sanitization.sanitize_text(page_id)}#comment-{comment.id}"

    # If this is a reply, ping the parent comment's author
    if parent_id:
        # parent_comment = models.Comment.query.get(parent_id)
        parent_comment = extensions.db.session.get(models.Comment, parent_id)
        if parent_comment and parent_comment.user_id != comment.user_id:
            notifications.notify(
                [
                    {
                        "user_id": parent_comment.user_id,
                        "type": "comment_reply",
                        "message": f"Someone replied to your comment",
                        "url": parent_comment.url,
                    }
                ]
            )

    extensions.db.session.commit()

    return (
        jsonify(
            message="Comment created", comment_id=comment.id, comment=comment.content
        ),
        201,
    )


@api.route("/comments/get/<page_id>", methods=["GET"])
@extensions.limiter.limit("20/minute")
def get_comments(page_id):
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "recent")  # "recent", "old", best"
    search = request.args.get("search", "", type=str).strip()

    # Compute the hash once
    page_hash = hashing_util.string_to_md5_binary(page_id)

    # Total comment count (including replies)
    total = models.Comment.query.filter_by(page_hash=page_hash).count()

    # Base query for top-level comments only
    query = models.Comment.query.filter_by(page_hash=page_hash, parent_id=None)

    # Basic. Searches the content.
    if search:
        query = query.filter(models.Comment.content.ilike(f"%{search}%"))

    # Sorting
    if sort == "old":
        query = query.order_by(asc(models.Comment.created_at))
    if sort == "best":
        query = query.outerjoin(models.CommentStats).order_by(
            desc(models.CommentStats.likes - models.CommentStats.dislikes),
            desc(models.Comment.created_at),  # tiebreak by recency
        )
    else:
        query = query.order_by(desc(models.Comment.created_at))  # fallback

    # Pagination
    paginated = query.paginate(page=page, per_page=10, error_out=False)
    comments = paginated.items
    has_more = paginated.has_next
    return jsonify(
        {
            "has_more": has_more,
            "total": total,
            "comments": [
                comments_util.serialize_comment_tree(comment) for comment in comments
            ],
        }
    )


@api.route("/comments/<int:comment_id>", methods=["PUT"])
@decorators.api_login_required
def edit_comment(comment_id):
    comment = models.Comment.query.get_or_404(comment_id)

    if comment.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    content = input_sanitization.gentle_cut_text(
        1000, input_sanitization.sanitize_html(data.get("content"))
    )

    if not content:
        return jsonify({"error": "Empty content"}), 400

    comment.content = content
    comment.is_flagged = comments_util.is_content_inappropriate(content)
    comment.is_edited = True
    extensions.db.session.commit()
    return jsonify(content=comment.content, updated_at=comment.updated_at.isoformat())


@api.route("/comments/<int:comment_id>", methods=["DELETE"])
@decorators.api_login_required
def delete_comment(comment_id):
    comment = models.Comment.query.get_or_404(comment_id)

    if comment.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    comment.is_deleted = True
    extensions.db.session.commit()
    return jsonify({"message": "Comment deleted"})


@api.route("/comments/<int:comment_id>/<action>", methods=["POST"])
@decorators.api_login_required
def react_to_comment(comment_id, action):
    if action not in ("like", "dislike"):
        return jsonify({"error": "Invalid action"}), 400

    # Fetch the comment and its stats row (create stats if missing)
    comment = models.Comment.query.get_or_404(comment_id)
    if comment.stats is None:
        comment.stats = models.CommentStats(comment_id=comment.id)
        extensions.db.session.add(comment.stats)
        extensions.db.session.commit()

    # See if the user already reacted
    reaction = models.CommentReaction.query.filter_by(
        comment_id=comment_id, user_id=current_user.id
    ).first()

    try:
        if reaction:
            if reaction.action == action:
                # Toggle off: remove the reaction and decrement the counter
                extensions.db.session.delete(reaction)
                if action == "like":
                    comment.stats.likes = models.CommentStats.likes - 1
                else:
                    comment.stats.dislikes = models.CommentStats.dislikes - 1
            else:
                # Change reaction: decrement old, increment new
                if reaction.action == "like":
                    comment.stats.likes -= 1
                    comment.stats.dislikes += 1
                else:
                    comment.stats.dislikes -= 1
                    comment.stats.likes += 1
                reaction.action = action
        else:
            # New reaction: add + increment the right counter
            new_reaction = models.CommentReaction(
                comment_id=comment_id, user_id=current_user.id, action=action
            )
            extensions.db.session.add(new_reaction)
            if action == "like":
                comment.stats.likes += 1
            else:
                comment.stats.dislikes += 1

        extensions.db.session.commit()

    except IntegrityError:
        extensions.db.session.rollback()
        return jsonify({"error": "Duplicate reaction"}), 400

    # Return the fresh counters from CommentStats
    return jsonify(
        likes=comment.stats.likes,
        dislikes=comment.stats.dislikes,
    )


@api.route("/bookmark", methods=["GET"])
@decorators.api_login_required
def list_bookmarks():
    stories = current_user.bookmarked_stories.all()
    return jsonify([s.to_dict() for s in stories]), 200


@api.route("/bookmark", methods=["POST"])
@decorators.api_login_required
def add_bookmark():
    data = request.get_json()
    story_id = data.get("story_id")

    story = models.Story.query.get_or_404(story_id)

    # check if already bookmarked
    existing = models.Bookmark.query.filter_by(
        user_id=current_user.id, story_id=story.id
    ).first()
    if existing:
        return jsonify(message="Already bookmarked"), 200

    bm = models.Bookmark(user_id=current_user.id, story_id=story.id)
    extensions.db.session.add(bm)
    extensions.db.session.commit()
    return jsonify(message="Bookmarked!"), 201


@api.route("/bookmark/<int:story_id>", methods=["DELETE"])
@decorators.api_login_required
def remove_bookmark(story_id):
    bm = models.Bookmark.query.filter_by(
        user_id=current_user.id, story_id=story_id
    ).first()
    if not bm:
        return jsonify(message="Not found"), 404
    extensions.db.session.delete(bm)
    extensions.db.session.commit()
    return jsonify(message="Removed bookmark"), 200


@api.route("/notifications", methods=["GET"])
@decorators.api_login_required
def list_notifications():
    """
    List the current user's notifications, newest first, paginated.
    Query params:
      - page: page number (default 1)
      - per_page: items per page (default 20)
      - show_read: "true" or "false" (default true)
    """
    page = request.args.get("page", type=int) or 1
    per_page = request.args.get("per_page", type=int) or 20
    show_read = request.args.get("show_read", "true").lower() == "true"

    q = models.Notification.query.filter_by(user_id=current_user.id)
    if not show_read:
        q = q.filter_by(is_read=False)

    pagination = q.order_by(models.Notification.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    items = []
    for n in pagination.items:
        items.append(
            {
                "id": n.id,
                "type": n.type,
                "message": n.message,
                "url": n.url,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
                # include related IDs if set
                "comment_id": n.comment_id,
                "friendship_id": n.friendship_id,
            }
        )

    return (
        jsonify(
            {
                "notifications": items,
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
            }
        ),
        200,
    )


@api.route("/notifications/unread_count", methods=["GET"])
@decorators.api_login_required
def unread_notification_count():
    """
    Return count of unread notifications for current user.
    """
    count = models.Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()
    return jsonify({"unread_count": count}), 200


@api.route("/notifications/<int:notification_id>/read", methods=["POST"])
@decorators.api_login_required
def mark_notification_read(notification_id):
    """
    Mark a single notification as read.
    """
    notif = models.Notification.query.filter_by(
        id=notification_id, user_id=current_user.id
    ).first()
    if not notif:
        return jsonify({"error": "Notification not found."}), 404

    if not notif.is_read:
        notif.is_read = True
        notif.read_at = (
            datetime.utcnow() if hasattr(models.Notification, "read_at") else None
        )
        extensions.db.session.commit()

    return jsonify({"message": "Notification marked as read.", "id": notif.id}), 200


@api.route("/notifications/read_all", methods=["POST"])
@decorators.api_login_required
def mark_all_notifications_read():
    """
    Mark all of the current user's notifications as read.
    """
    updated = models.Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({"is_read": True}, synchronize_session="fetch")
    extensions.db.session.commit()

    return (
        jsonify(
            {
                "message": "All notifications marked as read.",
                "notifications_updated": updated,
            }
        ),
        200,
    )
