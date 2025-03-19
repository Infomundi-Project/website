import threading
import logging
import pymysql

from requests import get as get_request
from random import shuffle, choice
from unidecode import unidecode
from bs4 import BeautifulSoup
from datetime import datetime
from feedparser import parse
from sys import exit

from website_scripts import config, input_sanitization, immutable, hashing_util


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
    #logging.info(message)


def insert_to_database(stories: list, category_name: str) -> int:
    """Inserts a list of stories into the database with associated categories and publishers.

    Parameters:
        stories (list): A list of dictionaries containing story details.
        category_name (str): The name of the category to which these stories belong.

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
                    "INSERT INTO categories (name) VALUES (%s) "
                    "ON DUPLICATE KEY UPDATE name = name", 
                    (category_name,)
                )

                # Insert or update the publisher
                cursor.execute("""
                    INSERT INTO publishers (md5_hash, name, link) 
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE name = VALUES(name), link = VALUES(link)
                """, (item['md5_hash'], item['publisher'], item['publisher_link']))

                # Insert the story
                cursor.execute("""
                    INSERT INTO stories (story_id, title, description, link, pub_date, category_name, publisher_id, media_content_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    item['id'], 
                    item['title'], 
                    item['description'], 
                    item['link'], 
                    item['pub_date'], 
                    category_name, 
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


def fetch_feed(rss_url: str, news_filter: str, result_list: list):
    """
    Fetch RSS feed and store relevant information in a result list.

    Args:
        rss_url (str): The URL of the RSS feed to fetch.
        news_filter (str): A filter keyword for news items.
        result_list (list): A list to store the fetched and processed news items.

    Appends the fetched and processed news items to the result_list.
    """
    if not input_sanitization.is_valid_url(rss_url):
        log_message(f'Invalid url: {rss_url}')
        return {}

    # Removes the ending slash if it ends with one
    if rss_url.endswith('/'):
        rss_url = rss_url[:-1]
    
    # Tries to find the RSS feed endpoint
    for possibility in immutable.RSS_ENDPOINTS:
        headers = {
            'User-Agent': choice(immutable.USER_AGENTS),
            'Referer': 'www.google.com'
        }

        try:
            response = get_request(rss_url + possibility, timeout=5, headers=headers)

            feed = parse(response.content)
            break
        except Exception:
            continue

    try:
        data = {
            'title': getattr(feed.feed, 'title', 'Unknown Publisher').strip(),
            'link': getattr(feed.feed, 'link', 'Unknown Link').strip(),
            'items': []
        }

        for story in feed.entries:
            # Decodes and removes html entities from text
            publisher_name = input_sanitization.sanitize_html(input_sanitization.decode_html_entities(data['title']))
            story_title = input_sanitization.sanitize_html(input_sanitization.decode_html_entities(story.get('title', f'No title was provided').strip()))
            story_description = input_sanitization.sanitize_html(input_sanitization.decode_html_entities(story.get('description', 'No description was provided').strip()))
            
            # Gentle cut (without cutting off words)
            publisher_name = input_sanitization.gentle_cut_text(80, publisher_name)
            story_title = input_sanitization.gentle_cut_text(120, story_title)
            story_description = input_sanitization.gentle_cut_text(500, story_description)
            
            publisher_link = feed.feed.link.strip()
            story_link = item.link.strip()

            # Checks to see if the urls are valid
            if not input_sanitization.is_valid_url(publisher_link) or not input_sanitization.is_valid_url(story_link):
                log_message(f'Either the feed link ({publisher_link}) or the item link ({story_link}) is not valid. Skipping.')
                continue

            if story.has_key('published_parsed'):
                pubdate = story.published_parsed
            elif story.has_key('published'):
                pubdate = story.published
            else:
                pubdate = story.updated
            
            # Creates the item hash ready to be insterted to the database
            story_hash = hashing_util.string_to_md5_binary(unidecode(
                story_title.lower() + story_link.lower())
            )

            # Creates the publisher hash ready to be insterted to the database
            publisher_hash = hashing_util.string_to_md5_binary(publisher_link)
            
            # Tries to format pubdate
            story_pubdate = format_date(pubdate).get('datetime', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            new_story = {
                'story_title': story_title,
                'story_description': story_description,
                'story_hash': story_hash,
                'story_link': story_link,
                'story_pubdate': story_pubdate,

                'publisher_name': publisher_name,
                'publisher_link': publisher_link,
                'publisher_hash': publisher_hash,
                }

            data['items'].append(new_story)
    
    except Exception as err:
        log_message(f"Exception getting {rss_url} ({news_filter}) // {err}")
        data = {}

    result_list.append(data)


def format_date(date) -> dict:
    """
    Converts a date object or ISO formatted date string into a readable MySQL DATETIME format.
    """

    # Convert date to a 9-tuple if it's a string in ISO format
    if isinstance(date, str):
        try:
            date = datetime.fromisoformat(date_str).timetuple()
        except ValueError:
            return {'error': 'Invalid date format'}

    # Convert the 9-tuple date to a datetime object
    if isinstance(date, tuple):
        date = datetime(*date[:6])

    # Ensure it's a datetime object
    if not isinstance(date, datetime):
        return {'error': 'Invalid date format'}

    return {'datetime': date.strftime('%Y-%m-%d %H:%M:%S')}


def fetch_categories():
    log_message('Fetching categories from the database')
    try:
        with db_connection.cursor() as cursor:
            # Construct the SQL query to fetch category IDs
            sql_query = "SELECT name FROM categories"
            cursor.execute(sql_query)
            categories = cursor.fetchall()

            category_database = [row['name'] for row in categories]
            shuffle(category_database)
    except pymysql.MySQLError as e:
        log_message(f"Error fetching categories: {e}")
        return []
    
    log_message(f'Got a total of {len(category_database)} categories from the database')
    return category_database


def fetch_feeds_from_database(category_id: str):
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
        log_message(f"\n[{round(percentage, 2)}%] Handling {selected_filter}...")
        
        # Read the feeds for current category
        rss_feeds = fetch_feeds_from_database(selected_filter)
        all_rss_data = []

        # Use threads to fetch concurrently
        threads = []
        result_list = []

        for feed_info in rss_feeds:
            thread = threading.Thread(target=fetch_feed, args=(feed_info["url"], selected_filter, result_list))
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
