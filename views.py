from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, abort
from flask_login import current_user, login_required
from datetime import datetime

from website_scripts import scripts, config, json_util, immutable, notifications, image_util, extensions, models,\
cloudflare_util, input_sanitization, friends_util, qol_util, hashing_util, totp_util, auth_util
from website_scripts.decorators import verify_captcha, admin_required, captcha_required, sensitive_area, in_maintenance

views = Blueprint('views', __name__)


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


@views.route('/id/<user_id>', methods=['GET'])
def user_profile_by_id(user_id):
    user = models.User.query.get(user_id)
    if not user:
        flash('User not found!', 'error')
        return redirect(url_for('views.user_redirect'))
    
    return redirect(url_for('views.user_profile', username=user.username))


@views.route('/profile/<username>', methods=['GET'])
@views.route('/p/<username>', methods=['GET'])
def user_profile(username):
    user = models.User.query.filter_by(username=username).first()
    if not user:
        flash("We apologize, but the user you're looking for could not be found.", 'error')
        return redirect(url_for('views.user_redirect'))
    
    # Make sure to add a trailing <p> to avoid breaking the page
    short_description = input_sanitization.gentle_cut_text(150, user.profile_description or '')

    if current_user.is_authenticated:
        friend_status, pending_friend_request_sent_by_current_user = friends_util.get_friendship_status(current_user.user_id, user.user_id)
    else:
        friend_status = 'not_friends'
        pending_friend_request_sent_by_current_user = False
    
    seo_title = f"Infomundi - {user.display_name if user.display_name else user.username}'s profile"
    seo_description = f"{user.profile_description if user.profile_description else 'We don\'t know much about this user, they prefer keeping an air of mystery...'}"
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


@views.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_user_profile():
    if request.method == 'GET':
        return render_template('edit_profile.html')

    # Gets first user input
    description = input_sanitization.sanitize_description(request.form.get('description', '')).strip()
    display_name = input_sanitization.sanitize_text(request.form.get('display_name', '')).strip()

    # Checks if the description is in the allowed range
    if not input_sanitization.is_text_length_between(config.DESCRIPTION_LENGTH_RANGE, description):
        flash(f'We apologize, but your description is too big. Keep it under {config.MAX_DESCRIPTION_LEN} characters.', 'error')
        return render_template('edit_profile.html')

    # Checks if the display name is in the allowed range
    if not input_sanitization.is_text_length_between(config.DISPLAY_NAME_LENGTH_RANGE, display_name):
        flash(f'We apologize, but your display name is too big. Keep it under {config.MAX_DISPLAY_NAME_LEN} characters.', 'error')
        return render_template('edit_profile.html')

    username = request.form.get('username', '').strip()

    # If the user changed their username, we should make sure it's alright.
    if current_user.username != username:
        # Checks if the username is valid
        if not input_sanitization.is_valid_username(username):
            flash(f'We apologize, but your username is invalid.', 'error')
            return render_template('edit_profile.html')
        
        username_query = models.User.query.filter_by(username=username).first()
        if username_query:
            flash(f'The username "{username}" is unavailable. Try making it more unique adding numbers/underscores/hiphens.', 'error')
            return render_template('edit_profile.html')
    
    # At this point user input should be safe :thumbsup: so we apply changes
    current_user.username = username
    current_user.display_name = display_name
    current_user.profile_description = description

    # Commit changes to the database
    extensions.db.session.commit()
    
    flash('Profile updated successfully!')
    return render_template('edit_profile.html')


@views.route('/profile/edit/avatar', methods=['GET'])
@login_required
def edit_user_avatar():
    return render_template('edit_avatar.html')


@views.route('/profile/edit/settings', methods=['GET', 'POST'])
@login_required
@sensitive_area
def edit_user_settings():
    if request.method == 'GET':
        return render_template('edit_settings.html')

    new_email = request.form.get('new_email', '').strip().lower()
    confirm_email = request.form.get('confirm_email', '').strip().lower()
    if (new_email or confirm_email) and (new_email != session['email_address']):
        if new_email != confirm_email:
            flash('Emails must match.', 'error')
            return render_template('edit_settings.html')

        if not input_sanitization.is_valid_email(new_email) or auth_util.search_user_email_in_database(new_email):
            flash('The email you provided is invalid.', 'error')
            return render_template('edit_settings.html')

        hashed_new_email = auth_util.hash_user_email_using_salt(new_email)

        # Send email to the user
        subject = 'Infomundi - Your Email Has Been Changed'
        body = f"""Hello, {current_user.display_name if current_user.display_name else current_user.username}.

We wanted to inform you that the email address associated with your Infomundi account has been successfully updated. Here are the details:

Device: {qol_util.get_device_info(request.headers.get('User-Agent'))}
IP Address: {cloudflare_util.get_user_ip()}
Country: {cloudflare_util.get_user_country()}

If you made this change, no further action is needed. However, if you did not request this change, please secure your account immediately by contacting our support team for assistance.

Best regards,
The Infomundi Team
"""
        
        # Update session information
        session['email_address'] = new_email
        session['obfuscated_email_address'] = input_sanitization.obfuscate_email(new_email)

        # Update database information
        current_user.email = hashed_new_email
        extensions.db.session.commit()

        flash('Your email has been updated.')
        return render_template('edit_settings.html')

    # If the user wants to change their password, we do so. Otherwise, we just skip
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    if new_password or confirm_password:
        if not (new_password == confirm_password and input_sanitization.is_strong_password(new_password)):
            flash("Either the passwords don't match or the password is not strong enough.", 'error')
            return render_template('edit_settings.html')

        auth_util.change_password(current_user, new_password)
        flash('Your password has been updated, and you may log in again.')
        return redirect(url_for('auth.login'))


@views.route('/redirect', methods=['GET'])
def user_redirect():
    target_url = request.headers.get('Referer', '')

    if target_url == 'https://infomundi.net/redirect':
        return redirect('https://infomundi.net/')
    elif not input_sanitization.is_safe_url(target_url):
        return redirect(url_for('views.home'))
    else:
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
            if qol_util.is_date_within_threshold_minutes(timestamp, config.CAPTCHA_CLEARANCE_HOURS, is_hours=True):
                flash("We know you are not a robot, don't worry")
                return redirect(url_for('views.user_redirect'))

        return render_template('captcha.html')
    
    session['clearance'] = datetime.now().isoformat()
    flash('Thanks for verifying! You are not a robot after all.')
    return redirect(session.get('clearance_from', url_for('views.home')))


@views.route('/sensitive', methods=['GET', 'POST'])
@verify_captcha
@login_required
def sensitive():
    if request.method == 'GET':
        is_trusted_session = session.get('is_trusted_session', '')
        if is_trusted_session:
            flash("We know you are who you say you are, don't worry!")
            return redirect(url_for('views.user_redirect'))

        return render_template('sensitive.html')
    
    recovery_token = request.form.get('recovery_token', '').strip()
    code = request.form.get('code', '').strip()

    # If user provided the code or recovery token, then we check it. If not, check the password instead
    if code or recovery_token:
        is_valid, message = totp_util.deal_with_it(current_user, code, recovery_token, session['key_value'])
    else:
        is_valid = current_user.check_password(request.form.get('current_password', ''))
        message = 'Invalid password!'
    
    if not is_valid:
        flash(message, 'error')
        return redirect(url_for('views.sensitive'))

    session['is_trusted_session'] = bool(request.form.get('trust_session', ''))

    flash('Thanks for verifying! You are who you say you are after all.')
    return redirect(url_for('views.edit_user_settings', username=current_user.username))


@views.route('/upload_image', methods=['POST'])
@login_required
def upload_image():
    image_categories = ('profile_picture', 'profile_banner', 'profile_background')
    for image_category in image_categories:
        file = request.files.get(image_category, '')
        
        if not file:
            continue
        
        # Checks file extension, mime type, image content and dimensions
        if not image_util.perform_all_checks(file.stream, file.filename):
            flash("We apologize, but the file you provided is invalid. Make sure the image isn't inappropriate and meets the minimum dimension requirements.", "error")
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
    email = request.form.get('email', '') if not current_user.is_authenticated else session.get('email_address', '')
    if not input_sanitization.is_valid_email(email):
        flash('We apologize, but your email address format is invalid.')
        return render_template('contact.html')

    # Cuts the name and message gently
    name = input_sanitization.gentle_cut_text(30, name)
    message = input_sanitization.gentle_cut_text(1000, message)

    if current_user.is_authenticated:
        login_message = f"Yes, as {email}"
    else:
        login_message = 'No'

    email_body = f"""This message was sent through the contact form in our website.

Authenticated: {login_message}
From: {name} - {email}
IP: {cloudflare_util.get_user_ip()}
Country: {cloudflare_util.get_user_country()}
Timestamp: {scripts.get_current_date_and_time()} UTC


{message}"""

    sent_message = notifications.send_email('contact@infomundi.net', f"Infomundi{' [PRIORITY]' if current_user.is_authenticated else ''} - Contact Form", email_body, email, f'{name} <{email}>')
    if sent_message:
        flash("Your message has been sent, thank you! Expect a return from us shortly.")
    else:
        flash("We apologize, but looks like that the contact form isn't working. We'll look into that as soon as possible. In the meantime, feel free to send us an email directly at contact@infomundi.net", 'error')
        notifications.post_webhook({'text': f"It wasn't possible to get a contact message for some reason, so... here's the email body: {email_body}"})
    

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
    notifications.send_email(email, 'Infomundi - Your Message Has Been Received', receive_message)
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
#@in_maintenance
def news():
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
    
    session['last_visited_country'] = f'news?country={contry_cca2}'

    supported_categories = scripts.get_supported_categories(contry_cca2)

    seo_title = f'Infomundi - {country_name.title()} Stories'
    seo_description = f"Whether you're interested in local events, national happenings, or international affairs affecting {country_name.title()}, Infomundi is your go-to source for news."

    news_page_data = scripts.news_page_processing(country_name)
    return render_template('news.html', 
        gdp_per_capita=scripts.get_gdp(country_name, is_per_capita=True),
        current_time=scripts.get_current_time_in_timezone(contry_cca2),
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
        area_rank=news_page_data['area_rank']
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
    if story.clicks == None:
        story.clicks = 1
    else:
        story.clicks += 1

    # Commit changes to the database.
    extensions.db.session.commit()
    
    # Set session information, used in templates.
    session['last_visited_news'] = f'comments?id={news_id}'
    
    # Used in the api.
    session['visited_news'] = news_id
    
    # Create the SEO data. Title should be 60 characters, description should be 150 characters
    seo_title = input_sanitization.gentle_cut_text(45, story.title)
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
