import threading
import logging
import pymysql
import os

from requests import get as get_request
from random import shuffle, choice
from unidecode import unidecode
from bs4 import BeautifulSoup
from datetime import datetime
from feedparser import parse
from hashlib import md5
from sys import exit

from website_scripts import json_util, config, input_sanitization, immutable


# Database connection parameters
db_params = {
    'host': '127.0.0.1',
    'user': config.MYSQL_USERNAME,
    'password': config.MYSQL_PASSWORD,
    'db': config.MYSQL_DATABASE,
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

db_connection = pymysql.connect(**db_params)

# Setup logging
logging.basicConfig(filename=f'{config.LOCAL_ROOT}/logs/create_cache.log', level=logging.INFO, format='[%(asctime)s] %(message)s')


def log_message(message):
    print(f'[~] {message}')
    logging.info(message)


def insert_to_database(stories: list, category_id: str) -> int:
    """Inserts a list of stories into the database with associated categories and publishers.

    Parameters:
        stories (list): A list of dictionaries containing story details.
        category_id (str): The ID of the category to which these stories belong.

    Returns:
        int: Exceptions count, if any.
    """
    exceptions_count = 0

    # Open a database cursor
    with db_connection.cursor() as cursor:
        # Iterate over each story in the provided list
        for item in stories:
            try:
                # Insert or update the category
                cursor.execute(
                    "INSERT INTO categories (category_id) VALUES (%s) "
                    "ON DUPLICATE KEY UPDATE category_id = category_id", 
                    (category_id,)
                )

                # Insert or update the publisher
                cursor.execute("""
                    INSERT INTO publishers (publisher_id, name, link) 
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE name = VALUES(name), link = VALUES(link)
                """, (item['publisher_id'], item['publisher'], item['publisher_link']))

                # Insert the story
                cursor.execute("""
                    INSERT INTO stories (story_id, title, description, link, pub_date, category_id, publisher_id, media_content_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    item['id'], 
                    item['title'], 
                    item['description'], 
                    item['link'], 
                    item['pub_date'], 
                    category_id, 
                    item['publisher_id'], 
                    item['media_content']['url']
                ))
            except Exception as err:
                # Handle any exceptions that occur during insertion
                exceptions_count += 1
                log_message(f"[-] {err}")

    # Commit all changes to the database
    db_connection.commit()
    
    return exceptions_count


def fetch_rss_feed(rss_url: str, news_filter: str, result_list: list):
    """
    Fetch RSS feed and store relevant information in a result list.

    Args:
        rss_url (str): The URL of the RSS feed to fetch.
        news_filter (str): A filter keyword for news items.
        result_list (list): A list to store the fetched and processed news items.

    Appends the fetched and processed news items to the result_list.
    """
    headers = {
        'User-Agent': choice(immutable.USER_AGENTS),
        'Referer': 'www.google.com'
    }

    if not input_sanitization.is_valid_url(rss_url):
        log_message(f'Invalid url: {rss_url}')
        return {}
    
    for possibility in ('', 'feed', 'rss'):
        try:
            response = get_request(rss_url + f'/{possibility}' if not rss_url.endswith('/') else possibility, timeout=5, headers=headers)
            if response.status_code not in (200, 301, 302):
                log_message(f"[Invalid HTTP Status Code] {rss_url} --> Status: {response.status_code}")
                continue

            feed = parse(response.content)
        except Exception:
            continue

    # Tries to parse the content
    try:
        feed = parse(response.content)
    except Exception:
        return {}

    try:
        data = {
            'title': feed.feed.title,
            'link': feed.feed.link,
            'items': []
        }

        for item in feed.entries:
            # Decodes and removes html entities from text
            feed_publisher = input_sanitization.sanitize_html(input_sanitization.decode_html_entities(feed.feed.title.strip()))
            item_title = input_sanitization.sanitize_html(input_sanitization.decode_html_entities(item.get('title', f'No title was provided').strip()))
            item_description = input_sanitization.sanitize_html(input_sanitization.decode_html_entities(item.get('description', 'No description was provided').strip()))
            
            # Gentle cut (without cutting off words)
            feed_publisher = input_sanitization.gentle_cut_text(80, feed_publisher)
            item_title = input_sanitization.gentle_cut_text(120, item_title)
            item_description = input_sanitization.gentle_cut_text(500, item_description)
            
            feed_link = feed.feed.link.strip()
            item_link = item.link.strip()

            # Checks to see if the url is valid
            if not input_sanitization.is_valid_url(feed_link) or not input_sanitization.is_valid_url(item_link):
                log_message(f'Either the feed link ({feed_link}) or the item link ({item_link}) is not valid. Skipping.')
                continue

            if item.has_key('published_parsed'):
                pubdate = item.published_parsed
            elif item.has_key('published'):
                pubdate = item.published
            else:
                pubdate = item.updated
            
            # Creates the item ID based on a MD5 summary of item title + item link.
            item_id = md5(unidecode( item_title.lower() + item_link.lower() ).encode()).hexdigest()

            # Creates the publisher id based on a MD5 summary of the feed link.
            publisher_id = md5(unidecode(feed_link).encode()).hexdigest()
            
            # Tries to format pubdate
            pubdate = format_date(pubdate)
            if 'error' in pubdate.keys():
                # If errors out, well... We use today's date, what else could we do? :D 
                pubdate_full = datetime.now().date().strftime('%Y/%m/%d')
            else:
                pubdate_full = pubdate['full']

            new_story = {
                'title': item_title,
                'description': item_description,
                'id': item_id,
                'publisher': feed_publisher,
                'publisher_link': feed_link,
                'publisher_id': publisher_id,
                'link': item_link,
                'pub_date': pubdate_full,
                'media_content': {
                    'url': 'static/img/infomundi-white-darkbg-square.webp'
                    }
                }

            data['items'].append(new_story)
    
    except Exception as err:
        log_message(f"[!] Exception getting {rss_url} ({news_filter}) // {err}")
        data = {}

    result_list.append(data)


def iso_to_tuple(date_str: str) -> tuple:
    """Convert ISO format date string to a 9-tuple date."""
    return datetime.fromisoformat(date_str).timetuple()


def format_date(date) -> dict:
    """
    Converts a date object or ISO formatted date string into a readable string format 
    for displaying on the news page. Returns a dictionary with both short and full date formats.

    Args:
        date (str or tuple): A date in ISO format string ('YYYY-MM-DD') or a 9-tuple date.

    Returns:
        dict: A dictionary with 'short' and 'full' keys containing the formatted date strings.

    Examples:
        >>> format_date('2024-06-24')
        {'short': 'Today', 'full': '2024/06/24'}

        >>> format_date('2024-06-19')
        {'short': '5 days ago', 'full': '2024/06/19'}

        >>> format_date('2024-05-01')
        {'full': '2024/05/01'}

        >>> format_date((2024, 6, 24, 0, 0, 0, 0, 0, 0))
        {'short': 'Today', 'full': '2024/06/24'}

        >>> format_date('24-06-2024')
        {'error': 'Invalid date format'}

        >>> format_date((2024, 6, 19, 0, 0, 0, 0, 0, 0))
        {'short': '5 days ago', 'full': '2024/06/19'}
    """

    # Convert date to a 9-tuple if it's a string in ISO format
    if isinstance(date, str):
        try:
            date = iso_to_tuple(date)
        except ValueError:
            # Handle invalid date string format
            return {'error': 'Invalid date format'}

    # Convert the 9-tuple date to a datetime.date object
    if isinstance(date, tuple):
        date = datetime(*date[:6]).date()

    date_result = {}  # Dictionary to hold the formatted date strings

    today = datetime.now().date()  # Get today's date

    # Check if the date is today
    if date == today:
        date_result['short'] = 'Today'
    else:
        # Calculate the difference in days from today
        days_diff = (today - date).days
        if 1 <= days_diff <= 15:
            date_result['short'] = f"{days_diff} day{'s' if days_diff > 1 else ''} ago"

    # Set the 'full' format to 'YYYY/MM/DD'
    date_result['full'] = date.strftime('%Y/%m/%d')
    
    return date_result


def fetch_categories():
    log_message('Fetching categories from the database')
    try:
        with db_connection.cursor() as cursor:
            # Construct the SQL query to fetch category IDs
            sql_query = "SELECT category_id FROM categories"
            cursor.execute(sql_query)
            categories = cursor.fetchall()

            category_database = [row['category_id'] for row in categories]
            shuffle(category_database)
    except pymysql.MySQLError as e:
        log_message(f"Error fetching categories: {e}")
        return []
    
    log_message(f'Got a total of {len(category_database)} categories from the database')
    return category_database


def fetch_feed(category_id: str):
    log_message(f'Fetching feeds from {category_id}')
    try:
        with db_connection.cursor() as cursor:
            # Construct the SQL query to fetch category IDs
            sql_query = """
                SELECT site, url FROM feeds 
                WHERE category_id = %s
            """
            cursor.execute(sql_query, (category_id))
            categories = cursor.fetchall()
    except pymysql.MySQLError as e:
        log_message(f"Error fetching categories: {e}")
        return []
    
    log_message(f'Got categories from the database')
    return categories


def main():
    total_done = 0
    
    categories = fetch_categories()
    for selected_filter in categories:
        percentage = (total_done // len(categories)) * 100
        log_message(f"\n[{round(percentage, 2)}%] Handling cache for {selected_filter}...")
        
        # Read the RSS feeds configuration for the current category
        rss_feeds = fetch_feed(selected_filter)
        all_rss_data = []

        # Use threads to fetch RSS feeds concurrently
        threads = []
        result_list = []

        for feed_info in rss_feeds:
            thread = threading.Thread(target=fetch_rss_feed, args=(feed_info["url"], selected_filter, result_list))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Process and collect data from each RSS feed
        for rss_data in result_list:
            if len(rss_data) == 0:
                continue
            
            rss_data["site"] = feed_info["site"]
            all_rss_data.append(rss_data)
        
        # Merge articles from different feeds into a single list
        merged_articles = []
        for rss_data in all_rss_data:
            merged_articles.extend(rss_data["items"])

        # Skip if no articles were found
        if not merged_articles:
            log_message(f"[-] Empty cache: {selected_filter}")
            continue

        # Shuffle merged articles to mix them up
        shuffle(merged_articles)

        # Insert articles into the database and count any exceptions
        exceptions_count = insert_to_database(merged_articles, selected_filter)
        total_done += 1
        
        log_message(f"[{len(merged_articles) - exceptions_count} articles] Saved for {selected_filter}.")
    
    log_message('Finished!')


if __name__ == "__main__":
    main()
