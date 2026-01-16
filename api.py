from flask import Blueprint, request, redirect, jsonify, url_for, session, abort
from werkzeug.exceptions import BadRequest
from sqlalchemy import and_, cast, desc, asc, func
from datetime import datetime, time, timedelta
from requests import get as requests_get
from sqlalchemy.orm import joinedload
from flask_login import current_user
from collections import defaultdict
from sqlalchemy.types import Date
import logging

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
    image_util,
    captcha_util,
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


@api.route("/currencies", methods=["GET"])
@extensions.cache.cached(timeout=60 * 30)  # 30m cached
def get_currencies():
    currencies = json_util.read_json(
        f"{config.WEBSITE_ROOT}/assets/data/json/currencies"
    )
    return jsonify(currencies)


@api.route("/stocks", methods=["GET"])
@extensions.cache.cached(timeout=60 * 30)  # 30m cached
def get_stocks():
    stocks = json_util.read_json(f"{config.WEBSITE_ROOT}/assets/data/json/stocks")

    # Removes unused US stocks
    del stocks[1:3]

    return jsonify(stocks)


@api.route("/crypto", methods=["GET"])
@extensions.cache.cached(timeout=60 * 30)  # 30m cached
def get_crypto():
    return jsonify(
        json_util.read_json(f"{config.WEBSITE_ROOT}/assets/data/json/crypto")
    )


@api.route("/home/dashboard", methods=["GET"])
@extensions.cache.cached(timeout=60 * 10)  # 10m cached
def get_home_dashboard():
    now = datetime.utcnow()
    today = now.date()
    start_date = today - timedelta(days=6)  # inclusive 7-day window
    start_dt = datetime.combine(start_date, time.min)

    # ── 1) STORIES PER DAY ──
    daily = (
        extensions.db.session.query(
            cast(models.Story.pub_date, Date).label("day"),
            func.count(models.Story.id).label("count"),
        )
        .filter(cast(models.Story.pub_date, Date) >= start_date)
        .group_by("day")
        .order_by("day")
        .all()
    )
    day_map = {r.day: r.count for r in daily}
    days = [start_date + timedelta(days=i) for i in range(7)]
    stories_last_7_days = [day_map.get(d, 0) for d in days]

    # ── 2) TOP 5 COUNTRIES ──
    # get raw category counts, then aggregate on country‐prefix
    raw = (
        extensions.db.session.query(
            models.Category.name, func.count(models.Story.id).label("count")
        )
        .join(models.Story, models.Story.category_id == models.Category.id)
        .filter(cast(models.Story.pub_date, Date) >= start_date)
        .group_by(models.Category.name)
        .all()
    )
    # fold into per‐country totals
    country_totals = {}
    for cat_name, cnt in raw:
        country = cat_name.split("_", 1)[0].upper()
        country_totals[country] = country_totals.get(country, 0) + cnt

    top_countries = [
        {"country": c, "count": country_totals[c]}
        for c in sorted(country_totals, key=lambda k: country_totals[k], reverse=True)[
            :5
        ]
    ]

    # ── 3) ENGAGEMENT METRICS ──
    likes = (
        extensions.db.session.query(func.count(models.StoryReaction.id))
        .filter(
            models.StoryReaction.action == "like",
            models.StoryReaction.created_at >= start_dt,
        )
        .scalar()
        or 0
    )
    dislikes = (
        extensions.db.session.query(func.count(models.StoryReaction.id))
        .filter(
            models.StoryReaction.action == "dislike",
            models.StoryReaction.created_at >= start_dt,
        )
        .scalar()
        or 0
    )
    comments = (
        extensions.db.session.query(func.count(models.Comment.id))
        .filter(models.Comment.created_at >= start_dt)
        .scalar()
        or 0
    )
    shares = (
        extensions.db.session.query(func.count(models.Bookmark.id))
        .filter(models.Bookmark.created_at >= start_dt)
        .scalar()
        or 0
    )
    days_iso = [(start_date + timedelta(days=i)).isoformat() for i in range(7)]

    return (
        jsonify(
            {
                "stories_last_7_days": stories_last_7_days,
                "days": days_iso,
                "top_countries": top_countries,
                "engagement": {
                    "likes": likes,
                    "dislikes": dislikes,
                    "comments": comments,
                    "shares": shares,
                },
            }
        ),
        200,
    )


@api.route("/user/pubkey", methods=["POST"])
@decorators.api_login_required
def update_pubkey():
    jwk = request.json.get("publicKey")
    if not jwk:
        abort(400, description="jwk is required")

    if current_user.public_key_jwk != jwk:
        current_user.public_key_jwk = jwk
        extensions.db.session.commit()

    return "", 204


@api.route("/user/<int:friend_id>/pubkey")
@extensions.cache.cached(timeout=60 * 5)  # 5m cached
@decorators.api_login_required
def get_pubkey(friend_id):
    fs_status = friends_util.get_friendship_status(current_user.id, friend_id)[0]
    if fs_status != "accepted":
        abort(403, description="No friendship with this user")
    friend = extensions.db.session.get(models.User, friend_id)
    return jsonify(publicKey=friend.public_key_jwk)


@api.route("/user/<int:friend_id>/messages", methods=["GET"])
@decorators.api_login_required
def get_messages(friend_id):
    """Get recent messages (encrypted) between current user and the specified friend."""
    friendship_status = friends_util.get_friendship_status(current_user.id, friend_id)[
        0
    ]
    if friendship_status != "accepted":
        abort(403, description="No friendship with this user.")

    # Query last N messages between users (both directions)
    msgs = (
        models.Message.query.filter(
            (
                (models.Message.sender_id == current_user.id)
                & (models.Message.receiver_id == friend_id)
            )
            | (
                (models.Message.sender_id == friend_id)
                & (models.Message.receiver_id == current_user.id)
            )
        )
        .options(joinedload(models.Message.replied_to))
        .order_by(models.Message.timestamp.desc())  # ← newest first
        .limit(50)
        .all()
    )

    msgs.reverse()  # this puts the messages in order

    messages_data = []
    for msg in msgs:
        preview = None
        if msg.parent_id:
            preview = msg.replied_to.content_encrypted
        messages_data.append(
            {
                "id": msg.id,
                "from": msg.sender.id,
                "ciphertext": msg.content_encrypted,
                "timestamp": msg.timestamp.isoformat(),
                "deliveredAt": msg.delivered_at and msg.delivered_at.isoformat(),
                "readAt": msg.read_at and msg.read_at.isoformat(),
                "reply_to": (
                    {"id": msg.replied_to.id, "previewText": preview}
                    if preview
                    else None
                ),
            }
        )
    return jsonify({"messages": messages_data})


@api.route("/user/<int:uid>/stats/reading", methods=["GET"])
@extensions.cache.cached(timeout=60 * 15)  # Cached for 15 minutes
def reading_stats(uid):
    user = extensions.db.session.get(models.User, uid)
    if not user:
        return jsonify({})

    now = datetime.utcnow()
    cuts = {
        "daily": now - timedelta(days=1),
        "weekly": now - timedelta(days=7),
        "monthly": now - timedelta(days=30),
    }

    # 1) Counts per period (just as you already have):
    stats = {}
    for period, since in cuts.items():
        stats[period] = (
            extensions.db.session.query(
                func.count(func.distinct(models.UserStoryView.story_id))
            )
            .filter(
                models.UserStoryView.user_id == uid,
                models.UserStoryView.viewed_at >= since,
            )
            .scalar()
            or 0
        )

    # 2) Top publishers
    top_pubs = (
        extensions.db.session.query(
            models.Publisher.name,
            func.count(func.distinct(models.UserStoryView.story_id)).label("ctr"),
        )
        .join(models.Story, models.Publisher.id == models.Story.publisher_id)
        .join(models.UserStoryView, models.Story.id == models.UserStoryView.story_id)
        .filter(models.UserStoryView.user_id == uid)
        .group_by(models.Publisher.name)
        .order_by(desc("ctr"))
        .limit(5)
        .all()
    )

    # 3) Top tags
    top_tags = (
        extensions.db.session.query(
            models.Tag.tag,
            func.count(func.distinct(models.UserStoryView.story_id)).label("ctr"),
        )
        .join(models.Story, models.Tag.story_id == models.Story.id)
        .join(models.UserStoryView, models.Story.id == models.UserStoryView.story_id)
        .filter(models.UserStoryView.user_id == uid)
        .group_by(models.Tag.tag)
        .order_by(desc("ctr"))
        .limit(5)
        .all()
    )

    # 4) Top countries (Category.name is something like "us_politics", so we split on “_”)
    country_counts = (
        extensions.db.session.query(
            models.Category.name,
            func.count(func.distinct(models.UserStoryView.story_id)).label("ctr"),
        )
        .join(models.Story, models.Category.id == models.Story.category_id)
        .join(models.UserStoryView, models.Story.id == models.UserStoryView.story_id)
        .filter(models.UserStoryView.user_id == uid)
        .group_by(models.Category.name)
        .order_by(desc("ctr"))
        .limit(5)
        .all()
    )
    top_countries = [
        {"country": cat.split("_", 1)[0].upper(), "count": cnt}
        for cat, cnt in country_counts
    ]

    # 5) Daily counts for the last 365 days
    one_year_ago = now - timedelta(days=365)

    # -------------------------
    # Replace date_trunc("day", ...) with DATE(viewed_at)
    # -------------------------
    daily_rows = (
        extensions.db.session.query(
            func.date(models.UserStoryView.viewed_at).label("d"),  # MySQL DATE()
            func.count(func.distinct(models.UserStoryView.story_id)).label("ctr"),
        )
        .filter(
            models.UserStoryView.user_id == uid,
            models.UserStoryView.viewed_at >= one_year_ago,
        )
        .group_by(func.date(models.UserStoryView.viewed_at))
        .order_by(func.date(models.UserStoryView.viewed_at))
        .all()
    )
    # daily_rows: list of (date (as a Python date), count) for each date where user viewed ≥1 story.

    # Build a lookup dict { "YYYY-MM-DD": count }
    date_to_count = {row.d.isoformat(): row.ctr for row in daily_rows}

    # Now fill in all 366 days (from one_year_ago through today), defaulting to 0 if missing
    daily_counts = []
    for i in range(0, 366):
        that_day = (one_year_ago + timedelta(days=i)).date().isoformat()
        daily_counts.append({"date": that_day, "count": date_to_count.get(that_day, 0)})

    # 6) Return the combined JSON
    return jsonify(
        {
            "counts": stats,  # { "daily": X, "weekly": Y, "monthly": Z }
            "top_publishers": [{"name": n, "count": c} for n, c in top_pubs],
            "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
            "top_countries": top_countries,
            "daily_counts": daily_counts,  # New field: list of 366 { date, count } objects
        }
    )


@api.route("/story/trending", methods=["GET"])
@extensions.cache.cached(timeout=60 * 30, query_string=True)  # 30m cached
@extensions.limiter.limit("15/minute")
def get_trending():
    """
    Returns trending stories based on period, metric, and optional filters.
    Query params:
      - period: 'hour', 'day', 'week', 'all' (default 'day')
      - metric: 'views', 'likes', 'dislikes' (default 'views')
      - limit: int (default 9)
      - country: ISO2 code (e.g. 'br')
      - category: category slug (e.g. 'general')
      - author: substring of author name
      - tag: single tag to filter by
      - publisher: substring of publisher name
    """
    # Read basic query parameters
    period = request.args.get("period", "all").lower()
    metric = request.args.get("metric", "views").lower()
    limit = request.args.get("limit", 7, type=int)

    if limit > 15:
        limit = 15

    # Optional filters
    country = request.args.get("country", type=str)
    category_slug = request.args.get("category", type=str)
    author = request.args.get("author", type=str)
    tag = request.args.get("tag", type=str)
    publisher_name = request.args.get("publisher", type=str)

    # Determine time window
    now = datetime.utcnow()
    if period == "hour":
        since = now - timedelta(hours=1)
    elif period == "week":
        since = now - timedelta(days=7)
    elif period == "all":
        since = None
    else:
        since = now - timedelta(days=1)

    # Base query: join Story with StoryStats
    query = extensions.db.session.query(models.Story, models.StoryStats).join(
        models.StoryStats, models.Story.id == models.StoryStats.story_id
    )

    # Time filter
    if since is not None:
        query = query.filter(models.Story.pub_date >= since)

    # Country & Category filter
    if country or category_slug:
        from sqlalchemy.orm import aliased

        Cat = aliased(models.Category)
        query = query.join(Cat, models.Story.category)
        if country and category_slug:
            full_cat = f"{country.lower()}_{category_slug.lower()}"
            query = query.filter(Cat.name == full_cat)
        elif category_slug:
            query = query.filter(Cat.name.ilike(f"%_{category_slug.lower()}"))
        elif country:
            query = query.filter(Cat.name.ilike(f"{country.lower()}_%"))

    # Author filter
    if author:
        query = query.filter(models.Story.author.ilike(f"%{author}%"))

    # Tag filter
    if tag:
        query = query.join(models.Tag, models.Story.tags).filter(
            models.Tag.tag.ilike(f"%{tag}%")
        )

    # Publisher filter
    if publisher_name:
        query = query.join(models.Publisher, models.Story.publisher)
        query = query.filter(models.Publisher.name.ilike(f"%{publisher_name}%"))

    # Choose ordering column
    if metric in ("likes", "dislikes"):
        order_col = getattr(models.StoryStats, metric)
    else:
        order_col = models.StoryStats.views

    # Finalize query
    results = query.order_by(desc(order_col)).limit(limit).all()

    # Serialize output
    trending = []
    for story, stats in results:
        trending.append(
            {
                "story_id": hashing_util.binary_to_md5_hex(story.url_hash),
                "title": story.title,
                "url": story.url,
                "pub_date": story.pub_date,
                "views": stats.views,
                "likes": stats.likes,
                "dislikes": stats.dislikes,
                "image_url": story.image_url,
                "author": story.author,
                "tags": [t.tag for t in story.tags],
                "publisher": {
                    "name": input_sanitization.clean_publisher_name(
                        story.publisher.name
                    ),
                    "url": story.publisher.site_url,
                    "favicon_url": story.publisher.favicon_url,
                },
            }
        )

    return jsonify(trending), 200


@api.route("/home/trending", methods=["GET"])
# @extensions.cache.cached(timeout=60 * 30)  # 30m cached
@extensions.limiter.limit("18/minute")
def get_home_trending():
    """
    Returns up to 10 “most relevant” stories (published in the last 24 h, scored by tag_count + recency),
    but only those with has_image=True, and no more than 3 per category.
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(days=15)

    # 1) Count tags per story (only for stories in the last 24 h AND has_image=True)
    tag_counts_subq = (
        extensions.db.session.query(
            models.Tag.story_id.label("story_id"),
            func.count(models.Tag.id).label("tag_count"),
        )
        .join(models.Story, models.Story.id == models.Tag.story_id)
        .filter(models.Story.pub_date >= cutoff, models.Story.has_image == True)
        .group_by(models.Tag.story_id)
        .subquery()
    )

    # 2) Join Story ⇄ tag_counts_subq, again filtering by date AND has_image
    rows = (
        extensions.db.session.query(models.Story, tag_counts_subq.c.tag_count)
        .outerjoin(tag_counts_subq, models.Story.id == tag_counts_subq.c.story_id)
        .filter(
            models.Story.pub_date >= cutoff,
            models.Story.has_image == True,
            # Ensure we only pick stories that appear in tag_counts_subq (i.e. have ≥1 tag)
            tag_counts_subq.c.tag_count.isnot(None),
        )
        .all()
    )

    # 3) Compute each story’s combined score = tag_count + recency_score
    scored = []
    for story, tag_count in rows:
        tag_count = tag_count or 0
        hours_since = (now - story.pub_date).total_seconds() / 3600.0
        recency_score = 1.0 / (hours_since + 1.0)
        score = tag_count + recency_score
        scored.append((story, score))

    # 4) Sort descending by score
    scored.sort(key=lambda x: x[1], reverse=True)

    # 5) Soft‐cap of 3 stories/category, pick up to 10 total
    MAX_PER_CATEGORY = 3
    caps = defaultdict(int)
    selected = []
    for story, _ in scored:
        cat = story.category.name
        if caps[cat] < MAX_PER_CATEGORY:
            caps[cat] += 1
            selected.append(story)
        if len(selected) >= 10:
            break

    # 6) Serialize JSON (only stories with has_image=True are here)
    out = []
    for story in selected:
        story_data = {
            "story_id": story.get_public_id(),
            "title": story.title,
            "url": story.url,
            "pub_date": story.pub_date.isoformat(),
            "image_url": story.image_url,
            "author": story.author or "",
            "tags": [t.tag for t in story.tags],
            "publisher": {
                "name": input_sanitization.clean_publisher_name(story.publisher.name),
                "url": story.publisher.site_url,
                "favicon_url": story.publisher.favicon_url,
            },
            "views": story.stats.views if story.stats else 0,
            "likes": story.stats.likes if story.stats else 0,
            "dislikes": story.stats.dislikes if story.stats else 0,
            "num_comments": (
                extensions.db.session.query(func.count(models.Comment.id))
                .filter(
                    models.Comment.story_id == story.id,
                    models.Comment.is_deleted == False,
                )
                .scalar()
                or 0
            ),
            "category": story.category.name,
        }
        out.append(story_data)

    return jsonify(out), 200


@api.route("/user/friend", methods=["POST"])
@extensions.limiter.limit("54/hour;18/minute")
@decorators.api_login_required
def handle_friends():
    data = request.get_json()

    friend_id = data.get("friend_id")
    action = data.get("action")

    if action not in ("add", "accept", "reject", "delete") or not friend_id:
        abort(
            400,
            description="Action must be 'add', 'accept', 'reject' or 'delete', and 'friend_id' should be supplied.",
        )

    if current_user.id == friend_id:
        abort(400, description="You can't friend yourself.")

    friend = extensions.db.session.get(models.User, friend_id)
    if not friend:
        abort(404, description="Couldn't find user.")

    if action == "add":
        new_friendship_id = friends_util.send_friend_request(current_user.id, friend_id)
        notifications.notify_single(
            friend.id,
            "friend_request",
            f"{current_user.username} has sent you a friend request",
            friendship_id=new_friendship_id,
            url=url_for(
                "views.user_profile_by_id", public_id=current_user.get_public_id()
            ),
        )
        return jsonify(message="Friend request sent"), 201

    elif action == "accept":
        if not friends_util.accept_friend_request(current_user.id, friend_id):
            abort(404, description="You don't have a pending request from this user.")

        # Sends notification to the friend
        notifications.notify_single(
            friend.id,
            "friend_accepted",
            f"{current_user.username} has accepted your friend request",
            url=url_for(
                "views.user_profile_by_id", public_id=current_user.get_public_id()
            ),
        )
        # Sends also notification to the user
        notifications.notify_single(
            current_user.id,
            "friend_accepted",
            f"You accepted the friend request from {friend.username}",
            url=url_for("views.user_profile_by_id", public_id=friend.get_public_id()),
        )
        return jsonify(message="Friend request accepted"), 200

    elif action == "reject":
        if not friends_util.reject_friend_request(current_user.id, friend_id):
            return abort(
                404, description="You don't have a pending request from this user."
            )

        return jsonify(message="Friend request rejected."), 200

    else:
        if not friends_util.delete_friend(current_user.id, friend_id):
            return abort(404, "You're not friends.")

        return jsonify(message="Friend removed."), 200


@api.route("/user/<int:user_id>/friend/status", methods=["GET"])
@decorators.api_login_required
def friendship_status(user_id):
    status, is_sent_by_current_user = friends_util.get_friendship_status(
        current_user.id, user_id
    )
    return jsonify(status=status, is_sent_by_current_user=is_sent_by_current_user)


@api.route("/story/<action>", methods=["POST"])
@extensions.limiter.limit("10/minute")
@decorators.api_login_required
def story_reaction(action):
    if action not in ("like", "dislike"):
        abort(400, "Invalid action.")

    # We get an 'id' attribute, but it isn't the ID really, it's url hash (md5 hex).
    # We pretend it's the ID to lure bad actors.
    url_hash = request.get_json().get("id")
    if not url_hash:
        abort(400, "Story ID is required.")

    story = models.Story.query.filter_by(
        url_hash=hashing_util.md5_hex_to_binary(url_hash)
    ).first()
    if not story:
        abort(400, "Could not find story.")

    # Check if a reaction already exists for this story and user
    existing_reaction = models.StoryReaction.query.filter_by(
        story_id=story.id, user_id=current_user.id
    ).first()

    # Initialize response flags
    is_liked = is_disliked = False

    story_stats = extensions.db.session.get(models.StoryStats, story.id)
    if not story_stats:
        story_stats = models.StoryStats(story_id=story.id)
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
            existing_reaction.created_at = datetime.now()
            message = f"Reaction updated to {action}"
            is_liked = action == "like"
            is_disliked = action == "dislike"
    else:
        # Create a new reaction
        new_reaction = models.StoryReaction(
            story_id=story.id,
            user_id=current_user.id,
            action=action,
            created_at=datetime.now(),
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
        abort(403, "You are already totp-enabled.")

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
        abort(400, "You are already totp-enabled.")

    code = request.args.get("code", "")
    totp_secret = session["totp_secret"]

    is_valid = totp_util.verify_totp(totp_secret, code)
    if not is_valid:
        return jsonify({"valid": False}), 200

    totp_recovery_token = current_user.setup_totp(session["totp_secret"])

    # There's no need to keep this info in the user's session anymore
    del session["totp_secret"]

    return jsonify({"valid": True, "totp_recovery_token": totp_recovery_token}), 201


@api.route("/2fa/mail/send", methods=["POST"])
@extensions.limiter.limit("30/day;3/minute")
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

    return jsonify(message="2FA code has been sent to your email."), 200


@api.route("/2fa/mail/verify", methods=["POST"])
@extensions.limiter.limit("10/minute")
@decorators.api_login_required
def verify_mail_twofactor_code():
    data = request.get_json() or {}
    code = data.get("code")

    if not code:
        abort(400, "Missing 'code' attribute.")

    user = extensions.db.session.get(models.User, session["user_id"])

    # We first check if the code is valid
    if not user.check_mail_twofactor(code):
        abort(400, "Invalid or expired code.")

    # This means the user has just configured mail twofactor via settings
    if not user.is_mail_twofactor_enabled:
        recovery_token = user.setup_mail_twofactor()
        return jsonify(recovery_token=recovery_token), 201

    return jsonify(message="2FA code is valid!"), 200


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
            "user_id": friend.id,
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
        abort(404, "Couldn't find user.")

    if not user.last_activity:
        return jsonify(is_online=False, last_activity=user.last_activity), 200

    # Save to the database
    user.is_online = user.check_is_online()
    extensions.db.session.commit()

    return jsonify(is_online=user.is_online, last_activity=user.last_activity), 200


@api.route("/user/status/update", methods=["GET"])
@decorators.api_login_required
def update_user_status():
    current_user.is_online = True
    current_user.last_activity = datetime.now()

    extensions.db.session.commit()
    return jsonify(message="Your status has been updated."), 201


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
    return jsonify({"countryCode": country.iso2 if country else ""}), 200


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

    return jsonify(country_util.get_country(name=query, ilike=True)), 200


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
    similarity_data = country_util.get_country(name=query, ilike=True)

    # Tries to grab the best match
    try:
        best_match_country, match_index = similarity_data[0]
        iso2 = best_match_country.iso2
    except Exception:
        iso2 = "donotexist"

    return redirect(url_for("views.news", country=iso2))


@api.route("/story/summarize/<story_url_hash>", methods=["GET"])
@extensions.limiter.limit("120/day;60/hour;6/minute", override_defaults=True)
def summarize_story(story_url_hash):
    story = models.Story.query.filter_by(
        url_hash=hashing_util.md5_hex_to_binary(story_url_hash)
    ).first()
    if not story:
        abort(404, "Couldn't find the story.")

    if story.gpt_summary:
        return jsonify({"response": story.gpt_summary}), 200

    try:
        r = requests_get(story.url, timeout=4)
        if r.status_code == 200:
            article = scripts.extract_article_fields(r.text)
        else:
            article = {}
    except Exception:
        article = {}

    title = article.get("title", story.title)
    main_text = article.get("text", story.description)

    response = llm_util.gpt_summarize(
        input_sanitization.gentle_cut_text(300, title),
        input_sanitization.gentle_cut_text(1700, main_text),
    )
    if not response:
        return jsonify("Failed to summarize."), 204

    story.gpt_summary = response
    extensions.db.session.commit()
    return jsonify({"response": response}), 200


@api.route("/story/chat/<story_url_hash>", methods=["POST"])
@extensions.limiter.limit("240/day;120/hour;20/minute", override_defaults=True)
def chat_about_story(story_url_hash: str):
    # Resolve story
    story = models.Story.query.filter_by(
        url_hash=hashing_util.md5_hex_to_binary(story_url_hash)
    ).first()
    if not story:
        abort(404, "Couldn't find the story.")

    try:
        data = request.get_json(force=True) or {}
    except BadRequest:
        return jsonify({"error": "Invalid JSON"}), 400

    user_message = (data.get("message") or "").strip()
    history = data.get("history") or []
    if not user_message:
        return jsonify({"error": "Message is required."}), 400

    # Optional moderation
    try:
        if llm_util.is_inappropriate(text=user_message):
            return jsonify(
                {"error": "Your message was flagged by our safety system."}
            ), 400
    except Exception:
        # If moderation fails silently, proceed rather than breaking the UX
        pass

    # Fetch article content (short timeout; graceful fallback)
    try:
        article_title = story.title
        article_text = story.description or ""
        r = requests_get(story.url, timeout=4)
        if r.status_code == 200:
            parsed = scripts.extract_article_fields(r.text) or {}
            article_title = parsed.get("title", article_title) or article_title
            article_text = parsed.get("text", article_text) or article_text
    except Exception:
        article_title = story.title
        article_text = story.description or ""

    # Ensure we have/can produce a compact structured summary for grounding
    summary_obj = story.gpt_summary
    if not summary_obj:
        try:
            summary_obj = llm_util.gpt_summarize(
                input_sanitization.gentle_cut_text(300, article_title),
                input_sanitization.gentle_cut_text(1700, article_text),
            )
            if summary_obj:
                story.gpt_summary = summary_obj
                extensions.db.session.commit()
        except Exception:
            summary_obj = {}

    # Call LLM chat
    try:
        reply = llm_util.gpt_chat_about_story(
            title=input_sanitization.gentle_cut_text(300, article_title or story.title),
            main_text=input_sanitization.gentle_cut_text(
                1800, article_text or story.description or ""
            ),
            summary_dict=summary_obj if isinstance(summary_obj, dict) else {},
            history=history if isinstance(history, list) else [],
            user_message=user_message,
        )
    except Exception:
        return jsonify({"error": "Chat failed. Please try again later."}), 500

    return jsonify({"response": reply.get("text", "")}), 200


@api.route("/get_stories", methods=["GET"])
@extensions.cache.cached(timeout=60 * 5, query_string=True)  # 5 min cached
@extensions.limiter.limit("20/minute", override_defaults=True)
def get_stories():
    """Returns a JSON list of stories, ordered by views, likes, comments, or publication date."""
    # 1) Read query parameters
    country = request.args.get("country", "br", type=str).lower()
    category_slug = request.args.get("category", "general", type=str).lower()
    page = request.args.get("page", 1, type=int)
    order_by = request.args.get("order_by", "pub_date", type=str).lower()
    order_dir = request.args.get("order_dir", "desc", type=str).lower()

    start_date = request.args.get("start_date", "", type=str)
    end_date = request.args.get("end_date", "", type=str)

    # 2) Resolve the Category row (e.g. "br_general")
    category = models.Category.query.filter_by(
        name=f"{country}_{category_slug}"
    ).first()
    if not category:
        return jsonify({"error": "This category is not yet supported!"}), 404

    # 3) Allow only these four order fields; default to "pub_date"
    valid_order_columns = ("views", "likes", "comments", "pub_date")
    if order_by not in valid_order_columns:
        order_by = "pub_date"

    # 4) Build the base filters on Story (category + has_image)
    base_filters = [
        models.Story.category_id == category.id,
        models.Story.has_image == True,
    ]

    # 5) If ordering by "comments", prepare a subquery that counts non-deleted comments per story
    if order_by == "comments":
        comment_counts = (
            extensions.db.session.query(
                models.Comment.story_id.label("story_id"),
                func.count(models.Comment.id).label("comment_count"),
            )
            .filter(models.Comment.is_deleted == False)
            .group_by(models.Comment.story_id)
            .subquery()
        )

    # 6) Start building the main query
    query = models.Story.query.filter(and_(*base_filters))

    # 7) If ordering by "views" or "likes", we need to join StoryStats
    if order_by in ("views", "likes"):
        query = query.outerjoin(
            models.StoryStats, models.Story.id == models.StoryStats.story_id
        )

    # 8) If ordering by "comments", join the comment_counts subquery
    if order_by == "comments":
        query = query.outerjoin(
            comment_counts, models.Story.id == comment_counts.c.story_id
        )

    # 9) Apply date filtering if both start_date and end_date are provided
    if start_date and end_date:
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(
                and_(
                    cast(models.Story.pub_date, Date) >= start_date_obj,
                    cast(models.Story.pub_date, Date) <= end_date_obj,
                )
            )
        except ValueError:
            return jsonify({"error": "Invalid date format: must be YYYY-MM-DD."}), 400

    # 10) Determine the ORDER BY column
    if order_by == "views":
        order_column = models.StoryStats.views
    elif order_by == "likes":
        order_column = models.StoryStats.likes
    elif order_by == "comments":
        # Use COALESCE so that stories with no comments sort as zero
        order_column = func.coalesce(comment_counts.c.comment_count, 0)
    else:  # "pub_date"
        order_column = models.Story.pub_date

    if order_dir == "asc":
        order_criterion = order_column.asc()
    else:
        order_criterion = order_column.desc()

    # 11) Pagination setup
    stories_per_page = 9
    start_index = (page - 1) * stories_per_page

    # 12) Execute query, eager-loading publisher
    stories = (
        query.options(joinedload(models.Story.publisher))
        .order_by(order_criterion, models.Story.id)
        .offset(start_index)
        .limit(stories_per_page)
        .all()
    )

    # 13) Serialize results (including num_comments for clarity)
    stories_list = []
    for story in stories:
        # Count non-deleted comments for each story (if the user requested ordering by comments,
        # we already joined the subquery, but here we recompute to include in the response)
        num_comments = (
            extensions.db.session.query(func.count(models.Comment.id))
            .filter(
                models.Comment.story_id == story.id, models.Comment.is_deleted == False
            )
            .scalar()
            or 0
        )

        story_dict = story.to_dict()
        story_dict["num_comments"] = num_comments

        stories_list.append(story_dict)

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

    # only flush() (later) once we've verified type and found the story (or profile_owner)
    if type == "story":
        # Sees if the page_id refers to a valid story in the database
        story = models.Story.query.filter_by(
            url_hash=hashing_util.md5_hex_to_binary(page_id)
        ).first()
        if not story:
            return jsonify(error="Could not find story in database."), 400
    elif type == "user":
        profile_owner = models.User.query.filter_by(
            public_id=security_util.uuid_string_to_bytes(page_id)
        ).first()
        if not profile_owner:
            return jsonify(error="Could not find user in database."), 400

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
        comment.url = f"{config.BASE_URL}/{input_sanitization.sanitize_text(page_id)}#comment-{comment.id}"

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
                        "message": "Someone replied to your comment",
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
    search = input_sanitization.sanitize_text(request.args.get("search", "", type=str))

    # Compute the hash once
    page_hash = hashing_util.string_to_md5_binary(page_id)

    # Total comment count (including replies)
    total = models.Comment.query.filter_by(page_hash=page_hash).count()

    # Base query for top-level comments only
    query = models.Comment.query.filter_by(page_hash=page_hash, parent_id=None)

    # Basic. Searches the content.
    if search:
        query = query.filter(models.Comment.content.ilike(f"%{search}%"))

    if sort == "old":
        query = query.order_by(asc(models.Comment.created_at))
    if sort == "best":
        query = query.outerjoin(models.CommentStats).order_by(
            desc(models.CommentStats.likes - models.CommentStats.dislikes),
            desc(models.Comment.created_at),  # tiebreak by recency
        )
    else:
        query = query.order_by(desc(models.Comment.created_at))  # fallback

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
        abort(403, description="You can't edit someone else's comment.")

    data = request.get_json()
    content = input_sanitization.gentle_cut_text(
        1000, input_sanitization.sanitize_html(data.get("content"))
    )

    if not content:
        abort(400, description="Content shoudln't be empty.")

    comment.content = content
    comment.is_flagged = comments_util.is_content_inappropriate(content)
    comment.is_edited = True
    extensions.db.session.commit()
    return (
        jsonify(
            content=comment.content,
            message="Comment updated.",
            updated_at=comment.updated_at.isoformat(),
        ),
        200,
    )


@api.route("/comments/<int:comment_id>", methods=["DELETE"])
@decorators.api_login_required
def delete_comment(comment_id):
    comment = models.Comment.query.get_or_404(comment_id)

    if comment.user_id != current_user.id:
        abort(403, "You can't delete a comment from other user.")

    comment.is_deleted = True
    comment.deleted_at = datetime.utcnow()
    extensions.db.session.commit()
    return jsonify(message="Comment deleted"), 200


@api.route("/comments/<int:comment_id>/<action>", methods=["POST"])
@decorators.api_login_required
@extensions.limiter.limit("150/hour;15/minute")
def react_to_comment(comment_id, action):
    if action not in ("like", "dislike"):
        abort(400, description="Invalid action")

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

    except Exception:
        extensions.db.session.rollback()
        abort(400, description="Reaction already exists.")

    # Return the fresh counters from CommentStats
    return jsonify(
        likes=comment.stats.likes,
        dislikes=comment.stats.dislikes,
    )


@api.route("/bookmark", methods=["GET"])
@decorators.api_login_required
def list_bookmarks():
    stories = (
        models.Story.query.join(
            models.Bookmark, models.Bookmark.story_id == models.Story.id
        )
        .filter(models.Bookmark.user_id == current_user.id)
        .all()
    )
    return jsonify([s.to_dict() for s in stories]), 200


@api.route("/bookmark", methods=["POST"])
@extensions.limiter.limit("100/hour;20/minute")
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
        abort(404, description="Couldn't find target bookmark.")
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
    notif = extensions.db.session.get(models.Notification, notification_id)
    if not notif:
        abort(404, description="Couldn't find target notification.")

    if current_user.id != notif.user_id:
        abort(404, description="Couldn't find target notification.")  # to blend in

    if not notif.is_read:
        notif.friendship_id = None
        notif.is_read = True
        notif.read_at = datetime.utcnow()
        extensions.db.session.commit()

    return jsonify(message="Notification marked as read.", id=notif.id), 200


@api.route("/notifications/read_all", methods=["POST"])
@decorators.api_login_required
@extensions.limiter.limit("5/minute")
def mark_all_notifications_read():
    """
    Mark all of the current user's notifications as read.
    """
    updated = models.Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({"is_read": True, "friendship_id": None}, synchronize_session="fetch")
    extensions.db.session.commit()

    return (
        jsonify(
            message="All notifications marked as read.", notifications_updated=updated
        ),
        200,
    )


@api.route("/user/<int:uid>/block", methods=["GET", "POST", "DELETE"])
@decorators.api_login_required
def block_user(uid, action):
    if uid == current_user.id:
        abort(403, description="Self-blocking? Well, that's new")

    target = extensions.db.session.get(models.User, uid)
    if not target:
        abort(404, description="Couldn't find target user.")

    block = models.UserBlock.query.filter_by(
        blocker_id=current_user.id, blocked_id=uid
    ).first()

    if request.method == "POST":
        if block:
            return jsonify(message="User is already blocked."), 204

        friends_util.delete_friend(
            current_user.id, target.id
        )  # users aren't friends anymore if they decide to block each other

        new_block = models.UserBlock(blocker=current_user, blocked=target)
        extensions.db.session.add(new_block)
    elif request.method == "DELETE":
        if not block:
            abort(400, description="User is not blocked.")
        extensions.db.session.delete(block)

    extensions.db.session.commit()

    return (
        jsonify(
            message=f"You {'blocked' if request.method == 'POST' else 'unblocked'} {target.username}. Take care of your peace!",
        ),
        201,
    )


@api.route("/user/<int:uid>/reports", methods=["GET", "POST"])
@api.route("/user/<int:uid>/reports/<int:report_id>", methods=["PATCH", "DELETE"])
@decorators.api_login_required
def user_reports(uid, report_id=0):
    if uid == current_user.id:
        abort(403, description="Self-reporting? Well, that's new.")

    target = extensions.db.session.get(models.User, uid)
    if not target:
        abort(404, description="Couldn't find target user.")

    if request.method == "GET":
        reports = models.UserReport.query.filter_by(
            reporter_id=current_user.id, reported_id=uid
        ).all()

        return jsonify(reports=[r.to_dict() for r in reports]), 200

    # Collecs this data only when required
    if request.method in ("POST", "PATCH"):
        data = request.get_json() or {}
        reason = input_sanitization.gentle_cut_text(
            500, input_sanitization.sanitize_html(data.get("reason", ""))
        )
        category = data.get("category")

        if category not in (
            "spam",
            "harassment",
            "hate_speech",
            "inappropriate",
            "other",
        ):
            abort(404, description="Couldn't find target category.")

    if request.method == "POST":
        report = models.UserReport.query.filter_by(
            reporter_id=current_user.id, reported_id=uid, category=category
        ).first()
        if report:
            abort(400, description="You've already reported this user.")

        report = models.UserReport(
            reporter=current_user, reported=target, reason=reason, category=category
        )
        extensions.db.session.add(report)

    elif request.method == "DELETE":
        report = models.UserReport.query.filter_by(
            id=report_id, reporter_id=current_user.id
        ).first()
        if not report:
            abort(404, description="Couldn't find target report.")

        extensions.db.session.delete(report)
    elif request.method == "PATCH":
        report = models.UserReport.query.filter_by(
            id=report_id, reporter_id=current_user.id
        ).first()
        if not report:
            abort(404, description="Couldn't find target report.")

        report.reason = reason
        report.category = category

    extensions.db.session.commit()

    return (
        jsonify(message="That's done."),
        200,
    )


@api.route("/user/image/<category>", methods=["POST"])
@decorators.api_login_required
def upload_image(category):
    ALLOWED = {
        "avatar": ("profile_picture", "users/{id}.webp", "has_avatar"),
        "banner": ("profile_banner", "banners/{id}.webp", "has_banner"),
        "wallpaper": (
            "profile_wallpaper",
            "wallpapers/{id}.webp",
            "has_wallpaper",
        ),
    }
    if category not in ALLOWED:
        return jsonify(error="Unknown category"), 404

    util_cat, key_tmpl, attr_flag = ALLOWED[category]
    file = request.files.get(category)
    if not file:
        abort(400, description="No image provided")

    s3_key = key_tmpl.format(id=current_user.get_public_id())
    setattr(current_user, attr_flag, True)

    is_valid, message = image_util.convert_and_save(
        file.stream, file.filename, util_cat, s3_key
    )

    if not is_valid:
        abort(400, description=message)

    extensions.db.session.commit()
    notifications.notify_single(
        current_user.id,
        "profile_edit",
        f"You submitted a new {category}. Wait a few minutes for it to update.",
    )

    return jsonify(success=True), 201


@api.route("/captcha", methods=["GET"])
@extensions.limiter.limit("20/minute", override_defaults=True)
def captcha():
    b64_img, text = captcha_util.generate_captcha()

    session["captcha_text"] = text
    session["captcha_time"] = datetime.utcnow().timestamp()

    return jsonify({"captcha": b64_img}), 200


@api.route("/world/feed", methods=["GET"])
@extensions.cache.cached(timeout=60 * 15)
@extensions.limiter.limit("20/minute", override_defaults=True)
def world_feed():
    """Returns latest news organized by world regions for the homepage."""
    from website_scripts.fallback_data import get_fallback_world_feed

    try:
        result = scripts.get_world_feed_by_regions()
        return jsonify(result), 200
    except (extensions.db.exc.SQLAlchemyError, ValueError, KeyError) as e:
        # Log the error for diagnostics
        logging.error(f"Error loading world feed: {e}")
        return jsonify(get_fallback_world_feed()), 200