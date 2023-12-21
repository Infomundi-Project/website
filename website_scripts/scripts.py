from re import search as search_regex, compile as re_compile, match as re_match
from requests import get as get_request, post as post_request
from pytz import timezone as pytz_timezone
from datetime import datetime, timedelta
from base64 import b64encode, b64decode
from os import listdir, urandom, path
from json import loads as json_loads
from difflib import SequenceMatcher
from urllib.parse import urlparse
from unidecode import unidecode
from bs4 import BeautifulSoup
from hashlib import md5

from . import config, json_util, immutable, notifications


def scrape_stock_data(country_name: str) -> list:
    """Uses tradingeconomics website to scrape stock info. Takes a country name as argument and returns a list of dictionaries related to stocks on that country."""
    country_name = country_name.lower().replace(' ', '-')

    # Checks if cache is old enough (12 hours)
    filepath = f'{config.STOCK_PATH}/{country_name}_stock'
    if not is_cache_old(f'{filepath}.json', 12):
        stock_data = json_util.read_json(filepath)
        return stock_data

    url = f"https://tradingeconomics.com/{country_name}/stock-market"
    
    # We need to use a fake header, otherwise we'll get blocked (code 403)
    headers = {
        'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }

    response = get_request(url, headers=headers)
    if response.status_code != 200:
        return []

    stock_data = []

    soup = BeautifulSoup(response.content, 'html.parser')
    for tr in soup.find_all('tr', {'data-decimals': '2'}):  # Filter based on the data-decimals attribute
        symbol = tr.get('data-symbol')

        name_element = tr.find('td', style="max-width: 150px;")
        name = name_element.text.strip() if name_element else None

        price_element = tr.find('td', id="p")
        price = price_element.text.strip() if price_element else None

        day_element = tr.find('td', id="pch")
        day = day_element.text.strip() if day_element else None

        date_element = tr.find('td', id="date")
        date = date_element.text.strip() if date_element else None

        year_element = tr.find('td', class_='d-none d-sm-table-cell', style='text-align: center;')
        year = year_element.text.strip() if year_element else None

        # Check if the 'market_cap' element is present
        market_cap_element = tr.find('td', {'class': 'd-none d-md-table-cell', 'data-value': True})
        market_cap = market_cap_element.text.strip() if market_cap_element else None

        stock_info = {
            'symbol': symbol,
            'name': name,
            'price': price,
            'day_change': day,
            'year_change': year,
            'date': date,
            'market_cap': market_cap
        }

        stock_data.append(stock_info)

    json_util.write_json(stock_data, filepath)
    return stock_data


def log(text: str, log_type: str='exception') -> bool:
    """Receives text and log_type. Both are required, but log_type has a default value set to 'Exception'. It writes to different log files based on the type of the log."""
    log_type = log_type.lower()
    if log_type not in ['exception', 'mail']:
        return False

    log_file = f'{config.LOGS_PATH}/{log_type}.log'
    try:
        with open(log_file, 'a') as f:
            f.write(f'{text}\n')
    except Exception:
        return False

    return True


def is_cache_old(file_path: str, threshold_hours: int=24) -> bool:
    """Checks the modification date of a desired file and compares it with a default threshold of 24 hours. If lower than 24 hours since last modification, return False. Else, return True.

    Arguments
        file_path: str
            File path to compare

        threshold_hours: int
            Default of 24. User may change it accordingly. Time to compare.

    Return: bool"""

    # Get the modification time of the file (os.path)
    try:
        file_mtime = datetime.fromtimestamp(path.getmtime(file_path))
    except FileNotFoundError:
        return True
    
    # Calculate the time difference between now and the file modification time
    time_difference = datetime.now() - file_mtime
    
    # Compare with the threshold
    return time_difference > timedelta(hours=threshold_hours)


def get_nation_data(cca2: str) -> dict:
    """Takes cca2 (country code) and returns a bunch of data about the specified country"""
    config_filepath = f'{config.COUNTRIES_DATA_PATH}/{cca2}'
    
    # 720 hours = 30 days (just for convencience)
    if not is_cache_old(f'{config_filepath}.json', 720):
        data = json_util.read_json(config_filepath)
    else:
        URL = f"https://restcountries.com/v3.1/alpha/{cca2.lower()}"
        r = get_request(URL)
        data = json_loads(r.text)
        json_util.write_json(data, config_filepath)
    
    for country in config.HDI_DATA:
        if country['cca2'].lower() == cca2.lower():
            country_name = country['country']
            hdi_rate = country['Hdi2021']
            hdi_tier = country['HdiTier']
            break
    else:
        country_name = ''
        hdi_rate = 'No information'
        hdi_tier = 'No information'
    
    leader = ''
    for country in config.PRESIDENTS_DATA:
        if country.lower() == country_name.lower():
            leader = config.PRESIDENTS_DATA[country]
            break
    else:
        leader = 'No information'
    
    if isinstance(data, list):
        data = data[0]
    
    try:
        borders = data['borders']
        currencies = data['currencies']
    except Exception:
        borders = ''
        currencies = ''

    formatted_borders = []
    for cca3 in borders:
        for item in config.COUNTRY_TO_CODE_LIST:
            if item['cca3'] == cca3:
                formatted_borders.append(item['name'])

    try:
        return {
        'area': f"{int(data['area']):,} km²",
        'borders': ', '.join(formatted_borders),
        'population': f"{data['population']:,}",
        'hdi': f'{hdi_rate} ({hdi_tier} - data from 2021)',
        'capital': ', '.join(data['capital']),
        'leader': leader,
        'currency': f"{currencies[list(currencies)[0]]['name']}, {currencies[list(currencies)[0]]['symbol']}",
        'united_nations_member': 'Yes' if {data['unMember']} else 'No',
        'languages': ', '.join(list(data['languages'].values())),
        'timezones': ', '.join(data['timezones']),
        'top_level_domain': data['tld'][0]
        }
    except Exception:
        return {}


def send_verification_token(email: str, username: str) -> bool:
    try:
        tokens = json_util.read_json(config.TOKENS_PATH)
    except Exception:
        tokens = {}
    
    if email in tokens:
        return False

    verification_token = md5(urandom(20)).hexdigest()
    
    tokens[email] = verification_token
    json_util.write_json(tokens, config.TOKENS_PATH)

    message = f"""Hello {username}, 

Welcome to Infomundi! If you've received this message in error, feel free to disregard it. However, if you're here to verify your account, we've made it quick and easy for you. Simply click on the following link to complete the verification process: 

https://infomundi.net/auth/verify?token={verification_token}

Looking forward to seeing you explore our platform!

Best regards,
The Infomundi Team"""

    subject = 'Infomundi - Verify Your Account'
    notifications.send_email(email, subject, message)
    return True


def check_verification_token(token: str) -> bool:
    tokens = json_util.read_json(config.TOKENS_PATH)
    for email in tokens:
        if tokens[email] == token:
            delete_token = email
            break
    else:
        delete_token = ''

    if delete_token:
        del tokens[delete_token]
        json_util.write_json(tokens, config.TOKENS_PATH)

    return bool(delete_token)


def parse_utc_offset(offset_str: str):
    """Takes an offset string (i.e UTC-04:00) and converts to a valid format in order to get the current time on the time zone."""
    sign = offset_str[0]
    hours = int(offset_str[1:3])
    minutes = int(offset_str[4:])

    total_minutes = hours * 60 + minutes

    if sign == '-':
        total_minutes = -total_minutes

    utc_offset = timedelta(minutes=total_minutes)
    return utc_offset


def get_current_time_in_timezone(cca2: str) -> str:
    data = json_util.read_json(f'{config.COUNTRIES_DATA_PATH}/{cca2}')
    current_utc_time = datetime.utcnow()

    try:
        capital = data['capital'][0]
        capitals_time = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/capitals_time')

        timezone = [x['gmt_offset'] for x in capitals_time if x['capital'].lower() == unidecode(capital).lower()][0]
    except Exception:
        timezone = ''

    if '+' in timezone or '-' in timezone:
        utc_offset = parse_utc_offset(timezone)
        current_time = current_utc_time + utc_offset
    else:
        current_time = current_utc_time
    
    formatted_time = current_time.strftime("%Y/%m/%d - %H:%M:%S")
    return formatted_time


def get_gdp(country_name: str, is_per_capita: bool=False) -> dict:
    """Takes the country name and wether is per capta or not (optional, default=False). Also, updates the saved database if the current save is more than 30 days old.

    Arguments
        country_name: str
            The name of the country to get gdp information. Full name, example: 'China', 'Russia', 'India' and so on.

        is_per_capta: bool
            Set default to False. Returns gdp per capta if True.

    Return: dict
        Returns a dictionary containing gdp value and date. An example would be:

        {
            "Austria": {
                "gdp_per_capita": "58,013 (IMF)",
                "date": "2023"
            }
        }
    """
    country_name = country_name.lower()
    cache_filepath = f"{config.WEBSITE_ROOT}/data/json/gdp{'_per_capita' if is_per_capita else ''}"
    
    if not is_cache_old(f'{cache_filepath}.json', 720):
        cache_data = json_util.read_json(cache_filepath)
        for index, value in enumerate(cache_data):
            if list(value.keys())[0].lower() == country_name:
                return cache_data[index]

    url = f"https://en.wikipedia.org/wiki/List_of_countries_by_GDP_(nominal){'_per_capita' if is_per_capita else ''}"
    response = get_request(url)

    if response.status_code != 200:
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')

    data = []
    for row in soup.find_all('tr'):
        cols = row.find_all(['td', 'th'])
        cols = [col.text.strip() for col in cols]
        data.append(cols)

    save_list = []
    for row in data:
        if row and len(row) > 5:
            country = row[0]
            save = {}
            
            # Primarily collects GDP from IMF (International Monetary Fund)
            
            gdp = row[2] if len(row) > 2 else "N/A"
            gdp_date = row[3] if len(row) > 3 else "N/A"
            gdp_publisher = 'IMF'
            
            # If there's no data from the IMF, use World Bank instead.
            if ',' in gdp_date:
                gdp = row[3] if len(row) > 3 else "N/A" 
                gdp_date = row[4] if len(row) > 4 else "N/A"
                gdp_publisher = 'World Bank'
        
            if not is_per_capita:
                # Removes ',' and multiplies by one million
                try:
                    gdp = int(gdp.replace(',', '')) * 1000000
                    gdp = '{:,}'.format(gdp)
                except ValueError as err:
                    pass

            save[country] = {}
            save[country]['gdp'] = f'${gdp} ({gdp_publisher})'
            save[country]['date'] = gdp_date
            save_list.append(save)

    json_util.write_json(save_list[2:], cache_filepath)
    for index, value in enumerate(save_list):
            if list(value.keys())[0].lower() == country_name:
                return save_list[index]


def detect_mobile(request) -> bool:
    """Uses a request object to check if the user is using a mobile device or not. If mobile, return True. Else, return False."""
    user_agent = request.user_agent.string

    if 'Mobile' in user_agent or 'Android' in user_agent:
        return True
    
    return False


def encode_base64(input_string: str) -> str:
    return b64encode(input_string.encode('utf-8')).decode('utf-8')


def decode_base64(encoded_string: str) -> str:
    return b64decode(encoded_string).decode('utf-8')


def is_valid_url(url: str) -> bool:
    """Takes a string and checks if it is a url. Return True if is indeed a url or if the string is empty, else False."""
    if not url:
        return True
    
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def is_valid_email(email: str) -> bool:
    if len(email) < 10 or '@' not in email or len(email) > 60:
        return False

    domain = email.split('@')[1]
    if domain not in immutable.EMAIL_DOMAINS:
        return False
    
    return True


def is_url_or_domain(input_str: str) -> str:
    """Takes a string and uses regex expressions to return 'Url' if the string is an url, 'Domain' if the string is a domain name and 'neither' if the string is neither a domain name or an url.

    Arguments
        input_str: str
            String to compare.
    """
    url_pattern = re_compile(r'^https?://\S+')

    domain_pattern = re_compile(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    if re_match(url_pattern, input_str):
        return "Url"
    elif re_match(domain_pattern, input_str):
        return "Domain"
    else:
        return "Neither"


def check_in_badlist(data: dict):
    """Takes data related to a comment. Uses notifications.py's post_webhook to send information about the comment to the admins discord server.
    
    Arguments
        data: dict
            Data related to a comment. Should have the following keys:
            {
                'name': 'username',
                'text': 'comment',
                'link': 'https://infomundi.net/comments?id=something&category=something'
            }
    """
    text_combined = data['name'] + ' ' + data['text']
    suspicious_words = []
    
    in_badlist = False
    for word in text_combined.lower().split(' '):
        if word in immutable.BADLIST:
            suspicious_words.append(word)
            in_badlist = True

    if in_badlist:
        webhook_data = {
            'embed': {
                'title': '🔔 Suspicious Comment',
                'description': f"{data['name']} posted a suspicious comment.",
                    'color': 0xFF0000,
                    'fields': [
                        {"name": "👤 Username", "value": data['name'], "inline": True},
                        {"name": "💬 Comment", "value": data['text'], "inline": True},
                        {"name": "🔗 Link", "value": data['link'], "inline": False}
                    ],
                    'footer': {'text': f"Comment ID: {data['id']}! Suspicious word{'s' if len(suspicious_words) > 1 else ''}: {' // '.join(suspicious_words)}"}
                },
                'message': 'We got a suspicious comment @everyone'
            }
        notifications.post_webhook(webhook_data)


def get_link_preview(url: str) -> dict:
    """Takes an URL as input and returns a dictionary with link preview information such as image, description and title."""
    try:
        headers = {
            'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        }
        # Send a GET request to the URL
        response = get_request(url, timeout=5, headers=headers)
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


def create_comment_id() -> str:
    """Simply uses os.urandom and md5 to generate a unique ID."""
    return md5(urandom(20)).hexdigest()


def string_similarity(s1: str, s2: str) -> float:
    """Takes two strings and returns the similarity percentage between them."""
    matcher = SequenceMatcher(None, s1, s2)
    return matcher.ratio() * 100 # Returns percentage of similarity


def add_click(news_id: str):
    """Takes the news id and add a click to the specified news in the telemetry file."""
    telemetry = json_util.read_json(config.TELEMETRY_PATH)
    current_timestamp = datetime.now()
    timestamp_string = current_timestamp.isoformat()
    
    if news_id not in telemetry:
        telemetry[news_id] = {}
        telemetry[news_id]['clicks'] = 0
        telemetry[news_id]['timestamp'] = timestamp_string

    to_remove = []
    for item in list(telemetry.keys()):
        saved_timestamp = datetime.fromisoformat(telemetry[item]['timestamp'])
        
        time_difference = current_timestamp - saved_timestamp
        if time_difference < timedelta(days=7):
            break
        
        to_remove.append(item)

    for key in to_remove:
        del telemetry[key]
    
    telemetry[news_id]['clicks'] += 1
    telemetry[news_id]['timestamp'] = timestamp_string
    
    json_util.write_json(telemetry, config.TELEMETRY_PATH)


def get_statistics() -> dict:
    """Handles the statistics for Infomundi. Returns a dict with related information."""
    statistics = json_util.read_json(config.STATISTICS_PATH)

    current_timestamp = datetime.now()
    formatted_time = current_timestamp.strftime('%Y/%m/%d %H:%M')  # Local Time

    saved_timestamp = datetime.fromisoformat(statistics['timestamp'])
    time_difference = current_timestamp - saved_timestamp
    
    if time_difference < timedelta(minutes=15):
        statistics['current_time'] = formatted_time
        return statistics

    categories = [file.replace('.json', '') for file in listdir(config.FEEDS_PATH)]
    total_countries_supported = len([x.split('_')[0] for x in categories if 'general' in x])  # Total countries supported

    total_news = 0
    total_feeds = 0

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
        
        try:
            timestamp = news_cache['created_at']
        except KeyError:
            continue
    
    time_comparison = int((current_timestamp - datetime.fromtimestamp(timestamp)).total_seconds())
    if time_comparison < 3600: 
        minutes = time_comparison // 60
        last_updated_message = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        hours = time_comparison // 3600
        last_updated_message = f"{hours} hour{'s' if hours > 1 else ''} ago"
        
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


def valid_category(category: str) -> bool:
    """Takes a category and checks if it is a valid category based on existing JSON files."""
    categories = [file.replace('.json', '') for file in listdir(config.FEEDS_PATH)]
    
    if category not in categories:
        return False
    
    return True


def get_supported_categories(country_code: str) -> list:
    """Returns a list of supported categories"""
    return [file.split('_')[1].replace('.json', '') for file in listdir(config.FEEDS_PATH) if file.startswith(country_code)]


def valid_captcha(token: str) -> bool:
    """Uses the cloudflare turnstile API to check if the user passed the CAPTCHA challenge. Returns bool."""
    if not token:
        return False

    VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    # Build payload with secret key and token.
    data = {
        'secret': config.CAPTCHA_SECRET_KEY, 
        'response': token
    }

    # Make POST request with data payload to hCaptcha API endpoint.
    response = post_request(url=VERIFY_URL, data=data)

    # Parse JSON from response and return if was a success (True or False).
    return json_loads(response.content)['success']


def is_strong_password(password: str) -> bool:
    """Takes a password and checks if it is a strong password based on Infomundi password policy. That is: at least 1 number, and 8 characters"""

    #if not search_regex(r'[a-z]', password) or not search_regex(r'[A-Z]', password) or not search_regex(r'\d', password) or not search_regex(r'[!@#$%^&*()_+{}\[\]:;<>,.?~\\/-]', password) or len(password) < 12 or len(password) > 50:
        #return False

    if not search_regex(r'\d', password) or len(password) < 8 or len(password) > 50:
        return False
    
    return True


def remove_html_tags(text_with_html: str) -> str:
    return BeautifulSoup(text_with_html, 'html.parser').get_text()