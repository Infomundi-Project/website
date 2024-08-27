from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from flask_login import current_user, login_required
from datetime import datetime

from website_scripts import scripts, config, json_util, immutable, notifications, image_util, extensions, models,\
cloudflare_util, input_sanitization, friends_util, qol_util, hashing_util
from website_scripts.decorators import verify_captcha, admin_required, profile_owner_required, captcha_required

views = Blueprint('views', __name__)


def make_cache_key(*args, **kwargs):
    user_id = current_user.user_id if current_user.is_authenticated else 'guest'
    args_list = [request.path, user_id] + sorted((key.lower(), value.lower()) for key, value in request.args.items())
    key = hashing_util.md5_hash_text(str(args_list))
    return key


@views.route('/', methods=['GET'])
def home():
    home_data = scripts.home_processing()

    return render_template('homepage.html', 
        stock_date=home_data['stock_date'],
        world_stocks=enumerate(home_data['world_stocks']), 
        us_indexes=enumerate(home_data['us_indexes']), 
        page='home',
        statistics=home_data['statistics'],
        crypto_data=home_data['crypto_data']
    )


@views.route('/admin', methods=['GET'])
@admin_required
@extensions.limiter.limit('100 per hour')
def admin():
    return render_template('admin.html')


@views.route('/user/<friend_id>/friend/<action>', methods=['GET'])
@login_required
def handle_friends(friend_id, action):
    if action == 'add':
        if friends_util.send_friend_request(current_user.user_id, friend_id):
            flash('Friend request sent')
        else:
            flash('Something went wrong', 'error')
        
        return redirect(url_for('views.user_redirect'))
    
    elif action == 'accept':
        if friends_util.accept_friend_request(current_user.user_id, friend_id):
            flash('Friend request accepted')
        else:
            flash('Failed to accept friend request', 'error')
        
        return redirect(url_for('views.user_redirect'))
    
    elif action == 'reject':
        if friends_util.reject_friend_request(current_user.user_id, friend_id):
            flash("Friend request rejected")
        else:
            flash('Failed to reject friend request', 'error')

        return redirect(url_for('views.user_redirect'))
            
    elif action == 'delete':
        if friends_util.delete_friend(current_user.user_id, friend_id):
            flash('Friend request deleted')
        else:
            flash('Failed to delete friend request', 'error')
        
        return redirect(url_for('views.user_redirect'))
    
    else:
        flash('What?', 'error')
        return redirect(url_for('views.user_redirect'))


@views.route('/profile/<username>', methods=['GET'])
def user_profile(username):
    user = models.User.query.filter_by(username=username).first()
    if not user:
        flash('User not found!', 'error')
        return redirect(url_for('views.user_redirect'))
    
    # Make sure to add a trailing <p> to avoid breaking the page
    short_description = input_sanitization.gentle_cut_text(150, user.profile_description or '')

    if current_user.is_authenticated:
        friend_status, pending_friend_request_sent_by_current_user = friends_util.get_friendship_status(current_user.user_id, user.user_id)
    else:
        friend_status = 'not_friends'
        pending_friend_request_sent_by_current_user = False
    
    seo_title = f"Infomundi - {user.display_name if user.display_name else user.username}'s profile"
    seo_description = f"{user.profile_description if user.profile_description else 'We don\'t know much about this user, they prefer keeping this air of mystery...'}"
    seo_image = user.avatar_url

    is_profile_owner = current_user.is_authenticated and (current_user.user_id == user.user_id)
    return render_template('user_profile.html', user=user, 
        seo_data=(seo_title, seo_description, seo_image),
        short_description=input_sanitization.close_open_html_tags(short_description), 
        has_too_many_newlines=input_sanitization.has_x_linebreaks(user.profile_description),
        friend_status=friend_status, 
        friends_list=friends_util.get_friends_list(user.user_id),
        pending_friend_request_sent_by_current_user=pending_friend_request_sent_by_current_user, 
        pending_requests=friends_util.get_pending_friend_requests(current_user.user_id) if is_profile_owner else None
        )


@views.route('/profile/<username>/edit', methods=['GET', 'POST'])
@profile_owner_required
@verify_captcha
def edit_user_profile(username):
    if request.method == 'GET':
        return render_template('edit_profile.html')

    # Gets first user input
    description = input_sanitization.sanitize_description(request.form.get('description', ''))
    display_name = input_sanitization.sanitize_text(request.form.get('display_name', ''))

    # Checks if the description is in the allowed range
    if not input_sanitization.is_text_length_between(config.DESCRIPTION_LENGTH_RANGE, description):
        flash(f'We apologize, but your description is too big. Keep it under {config.MAX_DESCRIPTION_LEN} characters.', 'error')
        return redirect(url_for('views.user_redirect'))

    # Checks if the display name is in the allowed range
    if not input_sanitization.is_text_length_between(config.DISPLAY_NAME_LENGTH_RANGE, display_name):
        flash(f'We apologize, but your display name is too big. Keep it under {config.MAX_DISPLAY_NAME_LEN} characters.', 'error')
        return redirect(url_for('views.user_redirect'))

    username = request.form.get('username', '')

    # If the user changed their username, we should make sure it's alright.
    if current_user.username != username:
        # Checks if the username is valid
        if not input_sanitization.is_valid_username(username):
            flash(f'We apologize, but your username is invalid.', 'error')
            return redirect(url_for('views.user_redirect'))
        
        is_username_available = models.User.query.filter_by(username=username)
        if not is_username_available:
            flash(f'The username "{username}" is unavailable. Try making it more unique adding numbers/underscores/hiphens.', 'error')
            return redirect(url_for('views.user_redirect'))
    
    user = models.User.query.filter_by(username=current_user.username).first()
    
    # At this point user input should be safe :thumbsup: so we apply changes
    user.username = username
    user.display_name = display_name
    user.profile_description = description

    # Commit changes to the database
    models.db.session.commit()
    
    flash('Profile updated successfully!', 'success')
    return render_template('edit_profile.html')


@views.route('/profile/<username>/edit/avatar', methods=['GET'])
@profile_owner_required
def edit_user_avatar(username):
    short_description = input_sanitization.gentle_cut_text(25, current_user.profile_description or '')
    return render_template('edit_avatar.html', short_description=short_description)


@views.route('/profile/<username>/edit/settings', methods=['GET', 'POST'])
@profile_owner_required
@verify_captcha
def edit_user_settings(username):
    if request.method == 'GET':
        return render_template('edit_settings.html')

    # Check if current password is valid
    current_password = request.form.get('current_password', '')
    if not current_user.check_password(current_password):
        flash('Invalid current password.', 'error')
        return redirect(url_for('views.edit_user_settings'))

    current_email = request.form.get('email', '').strip().lower()
    if current_email:
        if current_email != session.get('email_address', ''):
            flash('Your current email is invalid.', 'error')
            return redirect(url_for('views.edit_user_settings'))

        new_email = request.form.get('new_email', '').strip().lower()
        confirm_email = request.form.get('confirm_email', '').strip().lower()

        if new_email != confirm_email:
            flash('Emails must match.', 'error')
            return redirect(url_for('views.edit_user_settings'))

        hashed_new_email = hashing_util.sha256_hash_text(new_email)

        # If the email format is invalid or email is already being used by other user
        if not input_sanitization.is_valid_email(new_email) or models.User.query.filter_by(email=hashed_new_email).first():
            flash('Invalid new email.', 'error')
            return redirect(url_for('views.edit_user_settings'))


        # Send email to the user
        subject = 'Infomundi - Your Email Has Been Changed'
        body = f"""Hello, {current_user.display_name if current_user.display_name else current_user.username}.

We wanted to inform you that the email address associated with your Infomundi account has been successfully updated. If you made this change, no further action is needed.

However, if you did not request this change, please secure your account immediately by resetting your password and contacting our support team for assistance.

For your security, we recommend reviewing your account activity and updating your security settings if necessary.

Best regards,
The Infomundi Team
"""
        
        # Update session information
        session['email_address'] = new_email
        session['obfuscated_email_address'] = input_sanitization.obfuscate_email(new_email)

        # Update database information
        current_user.email = hashed_new_email
        extensions.db.session.commit()

        flash('Email updated successfully.')

    # If the user wants to change their password, we do so. Otherwise, we just skip
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    if new_password and confirm_password:
        if not (new_password == confirm_password and scripts.is_strong_password(new_password)):
            flash("Either the passwords don't match or the password is not long enough. Please keep it 8-50 characters.", 'error')
            return redirect(url_for('views.edit_user_settings'))

        user.set_password(new_password)
        extensions.db.session.commit()
    
    flash('Profile updated successfully!')
    return redirect(url_for('views.edit_user_settings'))


@views.route('/redirect', methods=['GET'])
def user_redirect():
    target_url = request.headers.get('Referer', '')

    # If referer url isn't safe, redirect to the home page.
    if not input_sanitization.is_safe_url(target_url):
        return redirect(url_for('views.home'))

    return redirect(target_url)


@views.route('/be-right-back', methods=['GET'])
def be_right_back():
    return render_template('maintenance.html')


@views.route('/captcha', methods=['GET', 'POST'])
@verify_captcha
def captcha():
    if request.method == 'GET':
        # If they have clearance (means that they have recently proven they're human)
        clearance = session.get('clearance', '')
        if clearance:
            timestamp = datetime.fromisoformat(clearance)
            if qol_util.is_within_threshold_minutes(timestamp, config.CAPTCHA_CLEARANCE_HOURS, is_hours=True):
                flash("We know you are not a robot, don't worry")
                return redirect(url_for('views.user_redirect'))

        return render_template('captcha.html')
    
    session['clearance'] = datetime.now().isoformat()
    flash('Thanks for verifying! You are not a robot after all.')
    return redirect(session.get('clearance_from', url_for('views.home')))


@views.route('/upload_image', methods=['POST'])
@login_required
def upload_image():
    token = request.form['cf-turnstile-response']
    if not cloudflare_util.is_valid_captcha(token):
        flash('Invalid captcha!', 'error')
        return redirect(url_for('views.user_redirect'))

    image_categories = ('profile_picture', 'profile_banner', 'profile_background')
    for image_category in image_categories:
        file = request.files.get(image_category, '')
        
        if not file:
            continue
        
        # Checks file extension, mime type, image content and dimensions
        if not image_util.perform_all_checks(file.stream, file.filename):
            flash("We apologize, but the file you provided is invalid.", "error")
            return redirect(url_for('views.user_redirect'))
    
        # Changes some variables depending on the image category
        if image_category == 'profile_picture':
            bucket_path = f'users/{current_user.user_id}.jpg'
            current_user.avatar_url = f'https://bucket.infomundi.net/{bucket_path}'
        elif image_category == 'profile_banner':
            bucket_path = f'banners/{current_user.user_id}.jpg'
            current_user.profile_banner_url = f'https://bucket.infomundi.net/{bucket_path}'
        else:
            bucket_path = f'backgrounds/{current_user.user_id}.jpg'
            current_user.profile_wallpaper_url = f'https://bucket.infomundi.net/{bucket_path}'

        convert = image_util.convert_and_save(file.stream, image_category, bucket_path)
        if not convert:
            flash('We apologize, but something went wrong when saving your image. Please try again later.', 'error')
            return redirect(url_for('views.user_redirect'))
        
    extensions.db.session.commit()
    flash('Profile updated successfully! Please wait a few minutes for the changes to be applied.')
    return redirect(url_for('views.user_redirect'))


@views.route('/contact', methods=['GET', 'POST'])
@verify_captcha
def contact():
    if request.method == 'GET':
        return render_template('contact.html')

    # Get and sanitize input data
    name = input_sanitization.sanitize_text(request.form.get('name', ''))
    message = input_sanitization.sanitize_text(request.form.get('message', ''))

    # Checks if email is valid
    email = request.form.get('email', '')
    if not input_sanitization.is_valid_email(email):
        flash('We apologize, but your email address format is invalid.')
        return render_template('contact.html')

    # Cuts the name and message gently
    name = input_sanitization.gentle_cut_text(30, name)
    message = input_sanitization.gentle_cut_text(1000, message)

    # Gets the user ipv4 or ipv6
    user_ip = cloudflare_util.get_user_ip(request)

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
IP: {user_ip}
Country: {cloudflare_util.get_user_country(request)}
Timestamp: {scripts.get_current_date_and_time()} UTC


{message}"""

    sent_message = notifications.send_email('contact@infomundi.net', 'Infomundi - Contact Form', email_body, email, f'{name} <{email}>')
    if sent_message:
        flash("Your message has been sent, thank you! Expect a return from us shortly.")
    else:
        flash("We apologize, but looks like that the contact form isn't working. We'll look into that as soon as possible. In the meantime, feel free to send us an email directly at contact@infomundi.net", 'error')
        notifications.post_webhook({'text': f"It wasn't possible to get a contact message for some reason, so... here's the email body: {email_body}"})
    
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
    flash('We apologize, but this page is currently unavailable. Please try again later!', 'error')
    return redirect(url_for('views.user_redirect'))


@views.route('/news', methods=['GET'])
def get_latest_feed():
    """Serving the /news endpoint. 

    Arguments:
        country_cca2 (str): GET 'country' parameter. Specifies the country code (2 digits). Example: 'br' (cca2 for Brazil).

    Behavior:
        Renders the news page, containing 100 news per page.
    """
    contry_cca2 = request.args.get('country', '').lower()

    # Searches for the country full name
    country_name = scripts.country_code_to_name(contry_cca2)
    if not country_name:
        flash("We apologize, but we couldn't find the country you are looking for.")
        return redirect(url_for('views.user_redirect'))
    
    GET_PARAMETERS = f'news?country={contry_cca2}'
    session['last_visited_country'] = GET_PARAMETERS

    supported_categories = scripts.get_supported_categories(contry_cca2)

    seo_title = f'Infomundi - {country_name.title()} Stories'
    seo_description = f"Whether you're interested in local events, national happenings, or international affairs affecting {country_name.title()}, Infomundi is your go-to source for news."

    news_page_data = scripts.news_page_processing(country_name)
    return render_template('news.html', 
        current_time=scripts.get_current_time_in_timezone(contry_cca2),
        gdp_per_capita=scripts.get_gdp(country_name, is_per_capita=True),
        nation_data=scripts.get_nation_data(contry_cca2),
        supported_categories=supported_categories, 
        seo_data=(seo_title, seo_description),
        gdp=scripts.get_gdp(country_name),
        country_code=contry_cca2,
        country_name=country_name, 
        page_languages=news_page_data['page_languages'],
        main_religion=news_page_data['main_religion'],
        country_index=news_page_data['country_index'],
        stock_data=news_page_data['stocks']['data'],
        stock_date=news_page_data['stocks']['date'],
        is_global=news_page_data['is_global'],
        area_rank=news_page_data['area_rank'],
    )


@views.route('/comments', methods=['GET'])
def comments():
    news_id = request.args.get('id', '').lower()
    
    # Check if has the length of a md5 hash
    if not input_sanitization.is_md5_hash(news_id):
        flash('We apologize, but the story ID you provided is not valid. Please try again.', 'error')
        return redirect(url_for('views.user_redirect'))

    # Check if story exists.
    story = models.Story.query.get(news_id)
    if not story:
        flash("We apologize, but we could not find the story you were looking for. Please try again later.", 'error')
        return redirect(url_for('views.user_redirect'))

    # The current response format is not yet prepared to be displayed. We basically need to replace all underscores by spaces.
    formatted_gpt_summary = []
    if story.gpt_summary:
        summary_dict = story.gpt_summary
        
        for key, value in summary_dict.items():
            header = key.replace('_', ' ').title()
            formatted_gpt_summary.append({'header': header, 'paragraph': value})

    # Add a click to the story.
    if story.clicks is None:
        story.clicks = 1
    else:
        story.clicks += 1

    # Commit changes to the database.
    extensions.db.session.commit()
    
    # Set session information, used in templates.
    session['last_visited_news'] = f'comments?id={news_id}'
    
    # Used in the api.
    session['visited_news'] = news_id
    
    # Create the SEO dataw. Title should be 60 characters, description must be 150 characters
    seo_title = 'Infomundi - ' + input_sanitization.gentle_cut_text(60, story.title)
    seo_description = input_sanitization.gentle_cut_text(150, story.description)
    seo_image = story.media_content_url
    
    country_cca2 = story.category_id.split('_')[0]
    return render_template('comments.html', 
        from_country_name=scripts.country_code_to_name(story.category_id.split('_')[0]),
        page_language=qol_util.detect_language(story.title + ' ' + story.description),
        from_country_url=f'https://infomundi.net/news?country={country_cca2}',
        from_country_category=story.category_id.split('_')[1],
        from_country_code=story.category_id.split('_')[0],
        formatted_gpt_summary=formatted_gpt_summary,
        seo_data=(seo_title, seo_description, seo_image),
        previous_news='',
        story=story,
        next_news=''
    )
