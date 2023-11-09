import json, requests
from hashlib import md5
from re import search as search_regex
from difflib import SequenceMatcher
from os import listdir, urandom
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

from . import config

def read_json(filepath):
    """Takes only one argument, the path to the .json file on the system. Opens the requested file in a pythonic format (dictionary)"""
    with open(f"{filepath}.json", encoding='utf-8') as f:
        data = json.load(f)
    return data

def write_json(data, filepath):
    """It takes 'data' as the first argument, and then 'filename' as the second argument. 'data' is saved in a 'filepah' file in json format."""
    with open(f"{filepath}.json", "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def append_json(data, filepath):
    """It takes 'data' as the first argument, and then 'filename' as the second argument. 'data' is added to 'filepath' in json format."""
    with open(f"{filepath}.json", "a", encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def get_link_preview(url):
    """Takes a URL as input and returns a dictionary with link preview information."""
    try:
        # Send a GET request to the URL
        response = requests.get(url, timeout=5)
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
            'image': 'static/img/infomundi2.png',
            'description': 'No description was provided',
            'title': 'No title was provided'
        }

def create_comment_id():
    random = urandom(20)
    comment_id = md5(random).hexdigest()
    return comment_id

def string_similarity(s1, s2):
    """Takes two strings and returns the percentage similarity between them."""
    matcher = SequenceMatcher(None, s1, s2)
    return matcher.ratio() * 100 # Returns percentage of similarity

def get_statistics():
    statistics = read_json(config.STATISTICS_PATH)

    current_timestamp = datetime.now()
    formatted_time = current_timestamp.strftime('%Y/%m/%d %H:%M') # Local Time 

    saved_timestamp = datetime.fromisoformat(statistics['timestamp'])
    
    time_difference = current_timestamp - saved_timestamp
    if time_difference < timedelta(minutes=15):
        statistics['current_time'] = formatted_time
        return statistics
    
    categories = [file.replace('.json', '') for file in listdir(config.FEEDS_PATH)]
    total_countries_supported = len([x.split('_')[0] for x in categories if 'general' in x]) # Total countries supported

    total_news = 0 # Total news presented
    total_feeds = 0 # Total feeds
    for category in categories:
        news_feeds = read_json(f'{config.FEEDS_PATH}/{category}')
        total_feeds += len(news_feeds)

        try:
            news_cache = read_json(f'{config.CACHE_PATH}/{category}')
        except FileNotFoundError:
            continue
        
        for item in news_cache:
            if 'page' in item:
                total_news += len(item)
        timestamp = news_cache['created_at']
    
    last_updated = datetime.fromtimestamp(timestamp).strftime('%Y/%m/%d at %H:%M') # Last updated
    
    comments = read_json(config.COMMENTS_PATH)
    total_comments = 0 # Total comments
    for news_id in comments:
        if news_id != 'enabled':
            total_comments += len(comments[news_id])

    timestamp_string = current_timestamp.isoformat()
    data = {
        'current_time': formatted_time,
        'timestamp': timestamp_string,
        'total_countries_supported': total_countries_supported,
        'total_news': total_news,
        'total_feeds': total_feeds,
        'total_comments': total_comments,
        'last_updated': last_updated
    }
    
    write_json(data, config.STATISTICS_PATH)
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
    """Takes a CAPTCHA token and checks if it is valid."""
    SECRET_KEY = config.CAPTCHA_SECRET_KEY
    VERIFY_URL = "https://api.hcaptcha.com/siteverify"

    # Build payload with secret key and token.
    data = {
        'secret': SECRET_KEY, 
        'response': token
    }

    # Make POST request with data payload to hCaptcha API endpoint.
    response = requests.post(url=VERIFY_URL, data=data)

    # Parse JSON from response. Check for success or error codes.
    response_json = json.loads(response.content)
    success = response_json['success']
    return success

def is_strong_password(password):
    """Takes a password and checks if it is a strong password based on certain criteria."""
    
    # Check for at least a total of ten characters
    if len(password) < 10 or len(password) > 50:
        return False

    # Check for at least one lowercase character
    if not search_regex(r'[a-z]', password):
        return False

    # Check for at least one uppercase character
    if not search_regex(r'[A-Z]', password):
        return False

    # Check for at least one digit
    if not search_regex(r'\d', password):
        return False

    # Check for at least one special character
    if not search_regex(r'[!@#$%^&*()_+{}\[\]:;<>,.?~\\/-]', password):
        return False

    # If all checks pass, the password is strong
    return True
