import json
from datetime import datetime, timedelta
from requests import get as get_request
from difflib import SequenceMatcher
from unidecode import unidecode
from bs4 import BeautifulSoup
from random import choice
from os import path

from . import config, json_util, immutable, notifications, models, extensions, qol_util


@extensions.cache.memoize(timeout=60*60*8) # 8 hours
def home_processing() -> dict:
    """This function processes data for the home endpoint and caches it to speed up performance"""
    statistics = get_statistics()

    crypto_data = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/crypto')
    world_stocks = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/stocks')
    currencies = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/currencies')

    us_indexes = world_stocks[:3]

    # Removes unused US stocks
    del world_stocks[1:3]

    home_data = {
        'stock_date': world_stocks[0]['date'],
        'us_indexes': us_indexes,
        'crypto_data': crypto_data,
        'world_stocks': world_stocks,
        'currencies': currencies,
        'statistics': statistics
    }

    return home_data


@extensions.cache.memoize(timeout=60*60*6) # 6 hours
def news_page_processing(country_name: str) -> dict:
    country_name = country_name.lower()

    # Get area ranking
    area_ranks = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/area_ranking')
    for rank in area_ranks:
        if rank['country'].lower() == country_name:
            area_rank = rank
            break
    else:
        area_rank = ''

    # Get religion info
    religions = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/religions')
    for country, religion in religions.items():
        if country.lower() == country_name:
            main_religion = religion
            break
    else:
        main_religion = ''

    # There are countries with no national stock data available, so we use global stocks if that is the case.
    is_global = False
    stock_data = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/stock_data/{country_name}_stock')
    if not stock_data or stock_data[0]['market_cap'] == None:
        stock_data = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/stock_data/united-states_stock')
        is_global = True

    # Gets the date from the first stock
    stock_date = stock_data[0]['date']

    try:
        country_index = [x for x in json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/stocks') if x['country']['name'].lower() == country_name][0]
        currency_info = [x for x in json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/currencies') if x['country']['name'].lower() == country_name.replace(' ', '-')][0]
        country_index['currency'] = currency_info
    except IndexError as err:
        country_index = ''

    # Get page language
    page_languages = []
    languages = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/langcodes')
    for lang in languages:
        if lang['country'].lower() == country_name:
            page_languages.append(lang)

    news_page_data = {
        'area_rank': area_rank,
        'main_religion': main_religion,
        'is_global': is_global,
        'stocks': {
            'data': stock_data,
            'date': stock_date
        },
        'page_languages': page_languages,
        'country_index': country_index
    }
    return news_page_data


def get_statistics() -> dict:
    """Handles the statistics for Infomundi. Returns a dict with related information."""
    return models.SiteStatistics.query.order_by(models.SiteStatistics.id.desc()).first()


@extensions.cache.memoize(timeout=60*60*16) # 16 hours
def get_nation_data(cca2: str) -> dict:
    """Takes cca2 (country code) and returns a bunch of data about the specified country"""
    config_filepath = f'{config.COUNTRIES_DATA_PATH}/{cca2}'
    
    # 720 hours = 30 days
    if not qol_util.is_file_creation_within_threshold_minutes(f'{config_filepath}.json', 720, is_hours=True):
        data = json_util.read_json(config_filepath)
    else:
        URL = f"https://restcountries.com/v3.1/alpha/{cca2.lower()}"
        r = get_request(URL)
        data = json.loads(r.text)
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

    if isinstance(data, list):
        data = data[0]

    try:
        country_capital = unidecode(data['capital'][0].lower())
        capitals_time = json_util.read_json(f'{config.WEBSITE_ROOT}/data/json/capitals_time')

        for item in capitals_time:
            if country_capital in unidecode(item['capital']).lower():
                timezone = item['gmt_offset']
                break
        else:
            timezone = ''
    except Exception as err:
        timezone = ''

    if '+' in timezone or '-' in timezone:
        utc_offset = parse_utc_offset(timezone)
        current_time = current_utc_time + utc_offset
    else:
        current_time = current_utc_time
    
    formatted_time = current_time.strftime("%Y/%m/%d - %H:%M:%S")
    return formatted_time


@extensions.cache.memoize(timeout=60*60*16) # 16 hours
def get_gdp(country_name: str, is_per_capita: bool=False) -> dict:
    """Takes the country name and wether is per capta or not (optional, default=False). 
    Also, updates the saved database if the current save is more than 30 days old.

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
    
    if not qol_util.is_file_creation_within_threshold_minutes(f'{cache_filepath}.json', 720, is_hours=True):
        cache_data = json_util.read_json(cache_filepath)
        for index, value in enumerate(cache_data):
            if list(value.keys())[0].lower() == country_name:
                return cache_data[index]

    url = f"https://en.wikipedia.org/wiki/List_of_countries_by_GDP_(nominal){'_per_capita' if is_per_capita else ''}"
    
    headers = {
        'User-Agent': choice(immutable.USER_AGENTS)
    }
    response = get_request(url, headers=headers)

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

    if not save_list:
        return []
    
    json_util.write_json(save_list[2:], cache_filepath)
    for index, value in enumerate(save_list):
            if list(value.keys())[0].lower() == country_name:
                return save_list[index]


def get_link_preview(url: str) -> dict:
    """Takes an URL as input and returns a dictionary with link preview information such as image, description and title."""
    try:
        headers = {
            'User-Agent': choice(immutable.USER_AGENTS)
        }

        response = get_request(url, timeout=5, headers=headers)
        
        if response.status_code != 200:
            raise Exception

        response.encoding = 'utf-8'
        # Parse the HTML content of the page
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract relevant information
        title = soup.title.text.strip() if soup.title else "No title"
        
        description = soup.find('meta', {'name': 'description'})
        description = description.get('content').strip() if description else "No description"
        
        image = soup.find('meta', {'property': 'og:image'})
        image = image.get('content').strip() if image else "static/img/infomundi-white-darkbg-square.webp"

        # Remove some potentially harmful characters
        for character in immutable.SPECIAL_CHARACTERS:
            title.replace(character, '')
            description.replace(character, '')

        return {
            'image': image,
            'description': description,
            'title': title
        }
    except Exception:
        return {
            'image': 'static/img/infomundi-white-darkbg-square.webp',
            'description': 'No description was provided',
            'title': 'No title was provided'
        }


def string_similarity(s1: str, s2: str) -> float:
    """Takes two strings and returns the similarity percentage between them."""
    matcher = SequenceMatcher(None, s1, s2)
    return matcher.ratio() * 100


#@extensions.cache.memoize(timeout=60*60*12) # 12 hours
def is_valid_category(category: str) -> bool:
    """Takes a category and checks if it is a valid category based on existing JSON files."""
    categories = [x.name for x in extensions.db.session.query(models.Category).all()]
    
    if category not in categories:
        return False
    
    return True


@extensions.cache.memoize(timeout=60*60*12) # 12 hours
def country_code_to_name(cca2: str) -> str:
    countries = config.COUNTRY_LIST
    for item in countries:
        if item['code'].lower() == cca2:
            country_name = item['name']
            break
    else:
        country_name = ''

    return country_name


@extensions.cache.memoize(timeout=60*60*12) # 12 hours
def get_supported_categories(country_code: str) -> list:
    """Returns a list of supported categories"""
    categories = [x.name for x in extensions.db.session.query(models.Category).all()]
    
    return [category.split('_')[1] for category in categories if category.startswith(country_code)]


def get_current_date_and_time() -> str:
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
