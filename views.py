from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
    jsonify,
)
from flask_login import current_user, login_required
from datetime import datetime, timedelta

from website_scripts import (
    scripts,
    config,
    notifications,
    extensions,
    models,
    cloudflare_util,
    input_sanitization,
    friends_util,
    qol_util,
    hashing_util,
    auth_util,
    security_util,
    decorators,
    country_util,
    clustering_util,
)

views = Blueprint("views", __name__)


@views.route("/", methods=["GET"])
def home():
    home_data = scripts.home_processing()

    now = datetime.utcnow()
    country_iso = cloudflare_util.get_user_country().lower()

    # read previous visit (if any)
    last_visit_iso = session.get("last_visit")
    last_visit = None
    if last_visit_iso:
        try:
            last_visit = datetime.fromisoformat(last_visit_iso)
        except ValueError:
            # invalid format → treat as never-visisted
            last_visit = None

    # redirect if first visit (no last_visit) OR they've been away too long
    if not last_visit or (now - last_visit) > timedelta(hours=1):
        session["last_visit"] = now.isoformat()
        return redirect(url_for("views.news", country=country_iso))

    # otherwise show homepage as normal
    session["last_visit"] = now.isoformat()

    return render_template(
        "homepage.html",
        stock_date=home_data["stock_date"],
        world_stocks=enumerate(home_data["world_stocks"]),
        us_indexes=enumerate(home_data["us_indexes"]),
        page="home",
        statistics=home_data["statistics"],
        crypto_data=home_data["crypto_data"],
    )


@views.route("/admin", methods=["GET"])
@decorators.admin_required
def admin():
    return render_template("admin.html")


@views.route("/id/<public_id>", methods=["GET"])
def user_profile_by_id(public_id):
    user = models.User.query.filter_by(
        public_id=security_util.uuid_string_to_bytes(public_id)
    ).first()
    if not user:
        flash("User not found!", "error")
        return redirect(url_for("views.user_redirect"))

    return redirect(url_for("views.user_profile", username=user.username))


@views.route("/profile/<username>", methods=["GET"])
@views.route("/p/<username>", methods=["GET"])
def user_profile(username):
    user = models.User.query.filter_by(username=username).first()
    if not user:
        flash(
            "We apologize, but the user you're looking for could not be found.", "error"
        )
        return redirect(url_for("views.user_redirect"))

    # Make sure to add a trailing <p> to avoid breaking the page
    short_description = input_sanitization.gentle_cut_text(
        150, user.profile_description or ""
    )

    seo_title = f"Infomundi - {user.display_name if user.display_name else user.username}'s profile"
    seo_description = f"{short_description if short_description else 'We know nothing about this user, they prefer keeping an air of mystery...'}"
    seo_image = user.avatar_url

    user.has_contact_info = (
        user.public_email or user.linkedin_url or user.instagram_url or user.twitter_url
    )

    user.website_domain = (
        input_sanitization.get_domain(user.website_url) if user.website_url else ""
    )

    return render_template(
        "user_profile.html",
        has_too_many_newlines=input_sanitization.has_x_linebreaks(
            user.profile_description
        ),
        short_description=input_sanitization.close_open_html_tags(short_description),
        friends_list=friends_util.get_friends_list(user.id),
        seo_data=(seo_title, seo_description, seo_image),
        user=user,
    )


@views.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_user_profile():
    if request.method == "GET":
        return render_template("edit_profile.html")

    # Gets first user input
    description = input_sanitization.sanitize_description(
        request.form.get("description", "")
    ).strip()
    display_name = input_sanitization.sanitize_text(
        request.form.get("display_name", "")
    ).strip()

    # Checks if the description is in the allowed range
    if not input_sanitization.is_text_length_between(
        config.DESCRIPTION_LENGTH_RANGE, description
    ):
        flash(
            f"We apologize, but your description is too big. Keep it under {config.MAX_DESCRIPTION_LEN} characters.",
            "error",
        )
        return render_template("edit_profile.html")

    # Checks if the display name is in the allowed range
    if not input_sanitization.is_text_length_between(
        config.DISPLAY_NAME_LENGTH_RANGE, display_name
    ):
        flash(
            f"We apologize, but your display name is too big. Keep it under {config.MAX_DISPLAY_NAME_LEN} characters.",
            "error",
        )
        return render_template("edit_profile.html")

    username = request.form.get("username", "").strip()

    # If the user changed their username, we should make sure it's alright.
    if current_user.username != username:
        # Checks if the username is valid
        if not input_sanitization.is_valid_username(username):
            flash("We apologize, but your username is invalid.", "error")
            return render_template("edit_profile.html")

        username_query = models.User.query.filter_by(username=username).first()
        if username_query:
            flash(
                f'The username "{username}" is unavailable. Try making it more unique adding numbers/underscores/hiphens.',
                "error",
            )
            return render_template("edit_profile.html")

    country_id = request.form.get("country", 0, type=int)
    state_id = request.form.get("state", 0, type=int)
    city_id = request.form.get("city", 0, type=int)

    if country_id != current_user.country_id:
        if country_id == 0:
            current_user.country_id = None
        else:
            country = extensions.db.session.get(models.Country, country_id)
            if country:
                current_user.country_id = country_id

    if state_id != current_user.state_id:
        if state_id == 0:
            current_user.state_id = None
        else:
            state = extensions.db.session.get(models.State, state_id)
            if state:
                current_user.state_id = state_id

    if city_id != current_user.city_id:
        if city_id == 0:
            current_user.city_id = None
        else:
            city = extensions.db.session.get(models.City, city_id)
            if city:
                current_user.city_id = city_id

    for platform_option in ("linkedin", "twitter", "instagram"):
        platform_profile_url = request.form.get(
            f"{platform_option}_url"
        )  # e.g. linkedin_url or instagram_url

        if platform_profile_url:  # we check to see if the user actually did set this, or want to remove from profile
            platform_result, username_result = (
                input_sanitization.extract_username_from_thirdparty_platform_url(
                    platform_profile_url
                )
            )
            if platform_option != platform_result:
                flash(f"Invalid url for {platform_option} profile.", "error")
                return render_template("edit_profile.html")

        if platform_option == "linkedin":
            current_user.linkedin_url = platform_profile_url
        elif platform_option == "twitter":
            current_user.twitter_url = platform_profile_url
        else:
            current_user.instagram_url = platform_profile_url

    website_url = request.form.get("website_url")
    if website_url:
        if not input_sanitization.is_valid_url(website_url):
            flash("Invalid website url.", "error")
            return render_template("edit_profile.html")

    public_email = request.form.get("public_email")
    if public_email:
        if not input_sanitization.is_valid_email(public_email):
            flash("Invalid public email.", "error")
            return render_template("edit_profile.html")

    # At this point user input should be safe :thumbsup: so we apply changes
    current_user.website_url = website_url
    current_user.public_email = public_email

    current_user.username = username
    current_user.display_name = display_name
    current_user.profile_description = description

    # Commit changes to the database
    extensions.db.session.commit()

    notifications.notify_single(
        current_user.id, "profile_edit", "You edited information on your profile"
    )

    flash("Profile updated successfully!")
    return render_template("edit_profile.html")


@views.route("/profile/edit/avatar", methods=["GET"])
@login_required
def edit_user_avatar():
    return render_template("edit_avatar.html")


@views.route("/profile/edit/settings", methods=["GET", "POST"])
@login_required
@decorators.sensitive_area
def edit_user_settings():
    if request.method == "GET":
        return render_template("edit_settings.html")

    new_email = request.form.get("new_email", "").strip().lower()
    confirm_email = request.form.get("confirm_email", "").strip().lower()
    if (new_email or confirm_email) and (new_email != session["email_address"]):
        if new_email != confirm_email:
            flash("Emails must match.", "error")
            return render_template("edit_settings.html")

        if not input_sanitization.is_valid_email(
            new_email
        ) or auth_util.search_user_email_in_database(new_email):
            flash("The email you provided is invalid.", "error")
            return render_template("edit_settings.html")

        # Update session information
        session["email_address"] = new_email
        session["obfuscated_email_address"] = input_sanitization.obfuscate_email(
            new_email
        )

        # Update database information
        current_user.set_email(new_email)

        notifications.notify_single(
            current_user.id, "security", "You updated your email address"
        )

        flash("Your email has been updated.")
        return render_template("edit_settings.html")

    # If the user wants to change their password, we do so. Otherwise, we just skip
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")
    if new_password or confirm_password:
        if not (
            new_password == confirm_password
            and input_sanitization.is_strong_password(new_password)
        ):
            flash(
                "Either the passwords don't match or the password is not strong enough.",
                "error",
            )
            return render_template("edit_settings.html")

        current_user.set_password(new_password)
        notifications.notify_single(
            current_user.id, "security", "You updated your password"
        )
        flash("Your password has been updated.")
        return render_template("edit_settings.html")


@views.route("/redirect", methods=["GET"])
def user_redirect():
    target_url = request.headers.get("Referer", "")

    if "/redirect" in target_url or not input_sanitization.is_safe_url(target_url):
        return redirect(url_for("views.home"))

    return redirect(target_url)


@views.route("/be-right-back", methods=["GET"])
def be_right_back():
    return render_template("maintenance.html")


@views.route("/captcha", methods=["GET", "POST"])
@decorators.verify_turnstile
def captcha():
    if request.method == "GET":
        # If they have clearance (means that they have recently proven they're human)
        clearance = session.get("clearance", "")
        if clearance:
            timestamp = datetime.fromisoformat(clearance)
            if qol_util.is_date_within_threshold_minutes(
                timestamp, config.CAPTCHA_CLEARANCE_HOURS, is_hours=True
            ):
                flash("We know you are not a robot, don't worry")
                return redirect(url_for("views.user_redirect"))

        return render_template("captcha.html")

    session["clearance"] = datetime.now().isoformat()
    flash("Thanks for verifying! You are not a robot after all.")
    return redirect(session.get("clearance_from", url_for("views.home")))


@views.route("/sensitive", methods=["GET", "POST"])
#@extensions.limiter.limit("10/minute", override_defaults=True)
@decorators.check_twofactor
@login_required
def sensitive():
    if request.method == "GET":
        return (
            abort(404)
            if decorators.is_session_trusted()
            else render_template("sensitive.html")
        )

    decorators.set_session_trusted()

    flash("Thanks for verifying!")
    return redirect(url_for("views.edit_user_settings"))


@views.route("/contact", methods=["GET", "POST"])
@extensions.limiter.limit("120/day;60/hour;12/minute", override_defaults=True)
@decorators.verify_turnstile
def contact():
    if request.method == "GET":
        return render_template("contact.html")

    # Get and sanitize input data
    name = input_sanitization.sanitize_text(request.form.get("name", ""))
    message = input_sanitization.sanitize_text(request.form.get("message", ""))

    # Checks if email is valid
    email = (
        request.form.get("email", "")
        if not current_user.is_authenticated
        else session.get("email_address", "")
    )
    if not input_sanitization.is_valid_email(email):
        flash("We apologize, but your email address format is invalid.")
        return render_template("contact.html")

    # Cuts the name and message gently
    name = input_sanitization.gentle_cut_text(30, name)
    message = input_sanitization.gentle_cut_text(1000, message)

    if current_user.is_authenticated:
        login_message = f"Yes, as {email}"
    else:
        login_message = "No"

    email_body = f"""This message was sent through the contact form in our website.

Authenticated: {login_message}
From: {name} - {email}
IP: {cloudflare_util.get_user_ip()}
Country: {cloudflare_util.get_user_country()}
Timestamp: {scripts.get_current_date_and_time()} UTC


{message}"""

    sent_message = notifications.send_email(
        "contact@infomundi.net",
        f"Infomundi{' [PRIORITY]' if current_user.is_authenticated else ''} - Contact Form",
        email_body,
        email,
        f"{name} <{email}>",
    )
    if sent_message:
        flash("Your message has been sent, thank you! Expect a return from us shortly.")
    else:
        flash(
            "We apologize, but looks like that the contact form isn't working. We'll look into that as soon as possible. In the meantime, feel free to send us an email directly at contact@infomundi.net",
            "error",
        )
        notifications.post_webhook(
            {
                "text": f"It wasn't possible to get a contact message for some reason, so... here's the email body: {email_body}"
            }
        )

    if not current_user.is_authenticated:
        receive_message = """Hello there,

Someone used this email to send a message to us at Infomundi. If you didn't perform this action, please ignore this email. However, if you did perform this action, your message has been received, thank you for reaching out! We'll review your inquiry with care and respond within 5 business days.

Regards,
The Infomundi Team"""
    else:
        receive_message = f"""Hello {current_user.display_name if current_user.display_name else current_user.username},

Your message has been received, thank you for reaching out! We'll review your inquiry with care and respond within 3 business days.

Regards,
The Infomundi Team"""
    notifications.send_email(
        email, "Infomundi - Your Message Has Been Received", receive_message
    )
    return render_template("contact.html")


@views.route("/about", methods=["GET"])
@decorators.captcha_required
def about():
    return render_template("about.html")


@views.route("/policies", methods=["GET"])
def policies():
    return render_template("policies.html")


@views.route("/team", methods=["GET"])
@decorators.captcha_required
def team():
    return render_template("team.html")


@views.route("/donate", methods=["GET"])
def donate():
    flash(
        "We apologize, but this page is currently unavailable. Please try again later!",
        "error",
    )
    return redirect(url_for("views.user_redirect"))


@views.route("/news", methods=["GET"])
def news():
    """Serving the /news endpoint.

    Arguments:
        country_cca2 (str): GET 'country' parameter. Specifies the country code (2 digits). Example: 'br' (cca2 for Brazil).
    """
    country_cca2 = request.args.get("country", "").lower()

    if not country_cca2:
        flash(
            "We apologize, but we couldn't find the country you are looking for.",
            "error",
        )
        return redirect(url_for("views.home"))

    country = country_util.get_country(iso2=country_cca2)
    if not country:
        flash(
            "We apologize, but we couldn't find the country you are looking for.",
            "error",
        )
        return redirect(url_for("views.user_redirect"))

    country_name = country.name
    session["last_visited_country_url"] = f"/news?country={country_cca2}"

    supported_categories = scripts.get_supported_categories(country_cca2)

    seo_title = f"Infomundi - {country_name.title()} Stories"
    seo_description = f"Whether you're interested in local events, national happenings, or international affairs affecting {country_name.title()}, Infomundi is your go-to source for news."

    return render_template(
        "news.html",
        gdp_per_capita=scripts.get_gdp(country_name, is_per_capita=True),
        current_time=scripts.get_current_time_in_timezone(country_cca2),
        nation_data=scripts.get_nation_data(country_cca2),
        supported_categories=supported_categories,
        seo_data=(seo_title, seo_description),
        gdp=scripts.get_gdp(country_name),
        country_code=country_cca2,
        country_name=country_name,
    )


@views.route("/comments", methods=["GET"])
def comments():
    story_url_hash = request.args.get("id", "")
    story = models.Story.query.filter_by(
        url_hash=hashing_util.md5_hex_to_binary(story_url_hash)
    ).first()
    if not story:
        flash(
            "We apologize, but we could not find the story you were looking for. Please try again later.",
            "error",
        )
        return redirect(url_for("views.user_redirect"))

    if not story.stats:
        story_stats = models.StoryStats(story_id=story.id, views=1, likes=0, dislikes=0)
        extensions.db.session.add(story_stats)
    else:
        story.stats.views += 1
    extensions.db.session.commit()

    # Set session information, used in templates.
    session["last_visited_story_url"] = f"/comments?id={story_url_hash}"

    # Used in the api.
    session["last_visited_story_id"] = story.id

    # Create the SEO data. Title should be 50 - 60 characters, description should be around 150 characters
    seo_title = input_sanitization.gentle_cut_text(55, story.title)
    seo_description = input_sanitization.gentle_cut_text(150, story.description)
    seo_image = story.image_url

    country_cca2 = story.category.name.split("_")[0]

    if current_user.is_authenticated:
        extensions.db.session.add(
            models.UserStoryView(user_id=current_user.id, story_id=story.id)
        )
        extensions.db.session.commit()

    return render_template(
        "comments.html",
        from_country_name=country_util.get_country(
            iso2=story.category.name.split("_")[0]
        ).name,
        story_url_hash=story_url_hash,
        from_country_url=f"/news?country={country_cca2}",
        from_country_category=story.category.name.split("_")[1],
        from_country_code=story.category.name.split("_")[0],
        seo_data=(seo_title, seo_description, seo_image),
        previous_story="",
        story=story,
        next_story="",
    )


@views.route("/cluster", methods=["GET"])
def cluster():
    """View all stories in a cluster grouped by country."""
    cluster_id = request.args.get("id", "")

    cluster = models.StoryCluster.query.filter_by(
        cluster_hash=hashing_util.md5_hex_to_binary(cluster_id)
    ).first()

    if not cluster:
        flash("Could not find the cluster you were looking for.", "error")
        return redirect(url_for("views.home"))

    stories_by_country = clustering_util.get_cluster_stories(cluster.id)

    # SEO data
    primary_tag = cluster.dominant_tags[0] if cluster.dominant_tags else "Global News"
    seo_title = f"Global Coverage: {primary_tag}"
    seo_description = f"See how {cluster.story_count} news sources from {cluster.country_count} countries are covering this story."

    return render_template(
        "cluster.html",
        cluster=cluster,
        stories_by_country=stories_by_country,
        seo_data=(seo_title, seo_description, ""),
    )