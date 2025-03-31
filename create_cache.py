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


def insert_stories_to_database(stories: list, category_name: str, category_id: int, categories, publishers) -> int:
    """Inserts a list of stories into the database with associated categories and publishers.

    Parameters:
        stories (list): A list of dictionaries containing story details.
        category_name (str): The name of the category to which these stories belong.

    Returns:
        int: Exceptions count, if any.
    """
    exceptions_count = 0

    with db_connection.cursor() as cursor:
        for story in stories:
            try:
                # Get publisher ID
                publisher_id = [x['id'] for x in publishers if x['url_hash'] == story['publisher_url_hash']][0]
                if publisher_id:
                    print('a publisher is found!')
                    exit()

                # Insert story
                cursor.execute("""
                    INSERT INTO stories (title, description, url, url_hash, pub_date, category_id, publisher_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    story['story_title'],
                    story['story_description'],
                    story['story_url'],
                    story['story_url_hash'],
                    story['story_pubdate'],
                    category_id,
                    publisher_id
                ))
                log_message(f'Inserting new story')
            except Exception as err:
                exceptions_count += 1
                log_message(f"Error inserting story: {err}")

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
        log_message(f'Trying {possibility} against {rss_url}')
        
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
            story_url = story.link.strip()

            # Checks to see if the urls are valid
            if not input_sanitization.is_valid_url(publisher_link) or not input_sanitization.is_valid_url(story_url):
                log_message(f'Either the feed link ({publisher_link}) or the story link ({story_url}) is not valid. Skipping.')
                continue

            if story.has_key('published_parsed'):
                pubdate = story.published_parsed
            elif story.has_key('published'):
                pubdate = story.published
            else:
                pubdate = story.updated
            
            # Creates the url hashes
            url_hash = hashing_util.string_to_md5_binary(story_url)
            publisher_url_hash = hashing_util.string_to_md5_binary(publisher_link)
            
            # Tries to format pubdate
            story_pubdate = format_date(pubdate).get('datetime', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            new_story = {
                'story_title': story_title,
                'story_description': story_description,
                'story_pubdate': story_pubdate,
                'story_url_hash': url_hash,
                'story_url': story_url,

                'publisher_name': publisher_name,
                'publisher_link': publisher_link,
                'publisher_url_hash': publisher_url_hash,
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


def fetch_categories_from_database():
    log_message('Fetching categories from the database')
    try:
        with db_connection.cursor() as cursor:
            cursor.execute("SELECT * FROM categories")
            categories = cursor.fetchall()
    except Exception as e:
        log_message(f"Error fetching categories: {e}")
        return []
    
    category_list = [(row['id'], row['name']) for row in categories]
    shuffle(category_list)
    
    log_message(f'Got {len(category_list)} categories from the database')
    return category_list


def fetch_publishers_from_database(category_id: int):
    log_message(f'Fetching publishers for category ID: {category_id}')
    try:
        with db_connection.cursor() as cursor:
            cursor.execute("SELECT id, name, url, url_hash FROM publishers WHERE category_id = %s", (category_id,))
            publishers = cursor.fetchall()
    except Exception as e:
        log_message(f"Error fetching publishers: {e}")
        return []
    
    log_message(f'Got {len(publishers)} publishers from the database')
    print(publishers)
    return publishers


def main():
    total_done = 0
    categories = fetch_categories_from_database()

    for category_id, category_name in categories:
        percentage = (total_done // len(categories)) * 100
        log_message(f"\n[{round(percentage, 2)}%] Handling {category_name}...")

        rss_feeds = fetch_publishers_from_database(category_id)
        all_rss_data = []

        threads = []
        result_list = []

        for feed_info in rss_feeds:
            thread = threading.Thread(target=fetch_feed, args=(feed_info["url"], category_name, result_list))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        for rss_data in result_list:
            if not rss_data:
                continue
            
            rss_data["site"] = feed_info["name"]
            all_rss_data.append(rss_data)

        merged_articles = []
        for rss_data in all_rss_data:
            merged_articles.extend(rss_data["items"])

        if not merged_articles:
            log_message(f"[-] Empty cache: {category_name}")
            continue

        shuffle(merged_articles)

        exceptions_count = insert_stories_to_database(merged_articles, category_name, category_id, categories, rss_feeds)
        total_done += 1

        log_message(f"[{len(merged_articles) - exceptions_count} articles] Saved for {category_name}.")
    
    log_message('Finished!')



if __name__ == "__main__":
    main()
