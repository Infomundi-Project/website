from re import search as search_regex, compile as re_compile, match as re_match
from requests import get as get_request, post as post_request
from datetime import datetime, timedelta
from base64 import b64encode, b64decode
from difflib import SequenceMatcher
from urllib.parse import urlparse
from os import listdir, urandom
from bs4 import BeautifulSoup
from hashlib import md5
from json import loads

from . import config, json_util

def encode_base64(input_string):
    encoded_bytes = b64encode(input_string.encode('utf-8'))
    encoded_string = encoded_bytes.decode('utf-8')
    return encoded_string

def decode_base64(encoded_string):
    decoded_bytes = b64decode(encoded_string)
    decoded_string = decoded_bytes.decode('utf-8')
    return decoded_string

def get_session_info(request):
    try:
        country = decode_base64(request.cookies.get('last_visited_country', ''))
        news = decode_base64(request.cookies.get('last_visited_news', ''))
    except:
        return {}
    
    if not is_valid_url(country) or not is_valid_url(news):
        return {}

    return {
    'last_visited_country': country,
    'last_visited_news': news
    }

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def is_url_or_domain(input_str):
    # Regular expression pattern for a simple URL
    url_pattern = re_compile(r'^https?://\S+')

    # Regular expression pattern for a domain name
    domain_pattern = re_compile(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    if re_match(url_pattern, input_str):
        return "Url"
    elif re_match(domain_pattern, input_str):
        return "Domain"
    else:
        return "Neither"

def get_link_preview(url):
    """Takes a URL as input and returns a dictionary with link preview information."""
    try:
        # Send a GET request to the URL
        response = get_request(url, timeout=5)
        response.raise_for_status()
        response.encoding = 'utf-8'

        # Parse the HTML content of the page
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract relevant information
        title = soup.title.text.strip() if soup.title else "No title"
        description = soup.find('meta', {'name': 'description'})
        description = description.get('content').strip() if description else "No description"
        image = soup.find('meta', {'property': 'og:image'})
        image = image.get('content').strip() if image else "No image"

        return {
            'image': image,
            'description': description,
            'title': title
        }
    except:
        return {
            'image': 'static/img/infomundi-white-darkbg-square.webp',
            'description': 'No description was provided',
            'title': 'No title was provided'
        }

def create_comment_id():
    return md5(urandom(20)).hexdigest()

def string_similarity(s1, s2):
    """Takes two strings and returns the percentage similarity between them."""
    matcher = SequenceMatcher(None, s1, s2)
    return matcher.ratio() * 100 # Returns percentage of similarity

def add_click(news_id):
    telemetry = json_util.read_json(config.TELEMETRY_PATH)
    if news_id not in telemetry:
        telemetry[news_id] = {}
        telemetry[news_id]['clicks'] = 0

    telemetry[news_id]['clicks'] += 1
    json_util.write_json(telemetry, config.TELEMETRY_PATH)

def get_statistics():
    statistics = json_util.read_json(config.STATISTICS_PATH)
    saved_timestamp = datetime.fromisoformat(statistics['timestamp'])

    current_timestamp = datetime.now()
    formatted_time = current_timestamp.strftime('%Y/%m/%d %H:%M')  # Local Time

    time_difference = current_timestamp - saved_timestamp
    if time_difference < timedelta(minutes=15):
        statistics['current_time'] = formatted_time
        return statistics

    categories = [file.replace('.json', '') for file in listdir(config.FEEDS_PATH)]
    total_countries_supported = len([x.split('_')[0] for x in categories if 'general' in x])  # Total countries supported

    total_news = 0
    total_feeds = 0
    minutes_since_last_update = 0  # Initialize the variable

    for category in categories:
        news_feeds = json_util.read_json(f'{config.FEEDS_PATH}/{category}')
        total_feeds += len(news_feeds)

        try:
            news_cache = json_util.read_json(f'{config.CACHE_PATH}/{category}')
        except FileNotFoundError:
            continue

        for page in news_cache:
            if 'page' in page:
                total_news += len(page)
        
        timestamp = news_cache['created_at']
    
    time_comparison = int((current_timestamp - datetime.fromtimestamp(timestamp)).total_seconds())
    if time_comparison < 3600: # hours
        last_updated_message = f"{time_comparison // 60} minute{'s' if time_comparison > 1 else ''} ago"
    else:
        last_updated_message = f"{time_comparison // 3600} hour{'s' if time_comparison > 1 else ''} ago"
        
    last_updated = datetime.fromtimestamp(timestamp).strftime('%Y/%m/%d at %H:%M')  # Last updated date

    total_comments = 0
    comments = json_util.read_json(config.COMMENTS_PATH)
    for news_id in comments:
        if news_id != 'enabled':
            total_comments += len(comments[news_id])

    total_clicks = 0
    telemetry = json_util.read_json(config.TELEMETRY_PATH)
    for news_id in telemetry:
        total_clicks += telemetry[news_id]['clicks']

    timestamp_string = current_timestamp.isoformat()
    data = {
        'current_time': formatted_time,
        'timestamp': timestamp_string,  # this will be used to check if the statistics are ready for an update
        'total_countries_supported': total_countries_supported,
        'total_news': total_news,
        'total_feeds': total_feeds,
        'total_comments': total_comments,
        'last_updated': last_updated,
        'last_updated_message': last_updated_message,
        'total_clicks': total_clicks
    }

    json_util.write_json(data, config.STATISTICS_PATH)
    return data

def valid_category(category):
    """Takes a category and checks if it is a valid category based on existing JSON files."""
    categories = [file.replace('.json', '') for file in listdir(config.FEEDS_PATH)]
    
    if category not in categories:
        return False
    else:
        return True

def get_supported_categories(country_code):
    return [file.split('_')[1].replace('.json', '') for file in listdir(config.FEEDS_PATH) if file.startswith(country_code)]

def valid_captcha(token):
    """Takes a CAPTCHA token and checks if it is valid. Returns bool."""
    VERIFY_URL = "https://api.hcaptcha.com/siteverify"

    # Build payload with secret key and token.
    data = {
        'secret': config.CAPTCHA_SECRET_KEY, 
        'response': token
    }

    # Make POST request with data payload to hCaptcha API endpoint.
    response = post_request(url=VERIFY_URL, data=data)

    # Parse JSON from response and return if was a success (True or False).
    return loads(response.content)['success']

def is_strong_password(password):
    """Takes a password and checks if it is a strong password based on Infomundi password policy. That is: at least 1 lowercase character, 1 uppercase character, 1 digit, 1 special character, min 10 chacarters and max 50 characters."""

    if not search_regex(r'[a-z]', password) or not search_regex(r'[A-Z]', password) or not search_regex(r'\d', password) or not search_regex(r'[!@#$%^&*()_+{}\[\]:;<>,.?~\\/-]', password) or len(password) < 10 or len(password) > 50:
        return False
    else:
        return True

def remove_html_tags(text_with_html):
    return BeautifulSoup(text_with_html, 'html.parser').get_text()