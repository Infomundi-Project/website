import time, threading, os, pymysql

from datetime import datetime, timedelta
from random import shuffle, choice
from unidecode import unidecode
from bs4 import BeautifulSoup
from feedparser import parse
from requests import get
from hashlib import md5
from sys import exit

from website_scripts import json_util, config, scripts, immutable


# Database connection parameters
db_params = {
    'host': 'localhost',
    'user': config.MYSQL_USERNAME,
    'password': config.MYSQL_PASSWORD,
    'db': 'infomundi',
    'charset': 'utf8mb4'
}

db_connection = pymysql.connect(**db_params)


def insert_to_database(stories: list, category_id: str):
    with db_connection.cursor() as cursor:
        for item in stories:
            try:
                # Insert category
                cursor.execute("INSERT INTO categories (category_id) VALUES (%s) ON DUPLICATE KEY UPDATE category_id = category_id", (category_id,))

                # Insert publisher
                cursor.execute("""
                    INSERT INTO publishers (publisher_id, name, link) VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE name = VALUES(name), link = VALUES(link)
                """, (item['publisher_id'], item['publisher'], item['publisher_link']))

                # Insert story
                cursor.execute("""
                    INSERT INTO stories (story_id, title, description, link, pub_date, category_id, publisher_id, media_content_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (item['id'], item['title'], item['description'], item['link'], item['pubDate'], category_id, item['publisher_id'], item['media_content']['url']))
            except Exception as err:
                print(f"[-] {err}")

    db_connection.commit()


def fetch_rss_feed(rss_url: str, news_filter: str, result_list: list):
    """Fetch RSS feed and store relevant information in a result list."""
    headers = {
        'User-Agent': choice(immutable.USER_AGENTS)
    }
    
    try:
        response = get(rss_url, timeout=7, headers=headers)
        if response.status_code != 200:
            print(f"[!] {rss_url} // {response.status_code}")
            return {}
    except Exception:
        return {}

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
            feed_publisher = feed.feed.title
            feed_link = feed.feed.link

            item_title = item.get('title', f'No title was provided')
            item_description = scripts.remove_html_tags(item.get('description', 'No description was provided'))[:1500]
            item_link = item.link
            
            for character in immutable.SPECIAL_CHARACTERS:
                feed_publisher = feed_publisher.replace(character, '')
                feed_link = feed_link.replace(character, '')

                item_title = item_title.replace(character, '')
                item_link = item_link.replace(character, '')

            feed_publisher = feed_publisher.split('-')[0]

            if not scripts.is_valid_url(feed_link) or not scripts.is_valid_url(item_link):
                print(f'[-] Either the feed link ({feed_link}) or the item link ({item_link}) is not valid. Skipping.')
                continue

            if item.has_key('published_parsed'):
                pubdate = item.published_parsed
            elif item.has_key('published'):
                pubdate = item.published
            else:
                pubdate = item.updated

            # Manual correction :)
            feed_link = feed_link.replace('https://redir.folha.com.br/redir/online/emcimadahora/rss091/', '')
            item_link = item_link.replace('https://redir.folha.com.br/redir/online/emcimadahora/rss091/', '')
            
            item_id = f'{md5(unidecode( item_title.lower() + item_link.lower() ).encode()).hexdigest()}'
            
            if os.path.isfile(f'{config.WEBSITE_ROOT}/static/img/stories/{news_filter}/{item_id}.webp'):
                item_image = f'static/img/stories/{news_filter}/{item_id}.webp'
            else:
                item_image = 'static/img/infomundi-white-darkbg-square.webp'
            
            pubdate = format_date(pubdate)
            
            pubdate_full = ''
            pubdate_short = ''
            if isinstance(pubdate, dict):
                pubdate_full = pubdate['full']
                pubdate_short = pubdate['short']
            else:
                pubdate_full = pubdate

            new_story = {
                'title': item_title,
                'description': item_description,
                'id': item_id,
                'publisher': feed_publisher,
                'publisher_link': feed_link,
                'publisher_id': f'{md5(unidecode(feed_link).encode()).hexdigest()}',
                'link': item_link,
                'pubDate': pubdate_full,
                'pubDate_short': pubdate_short,
                'media_content': {
                    'url': item_image
                    }
                }

            data['items'].append(new_story)
    
    except Exception as err:
        print(f"[!] Exception getting {rss_url} ({news_filter}) // {err}")
        data = {}

    result_list.append(data)


def format_date(date) -> str:
    """Takes a pythonic date object and converts into a string to show in the news page"""
    if not isinstance(date, tuple):
        if date.startswith('2024') or date.startswith('2023'):
            date_object = datetime.fromisoformat(date)
            # Convert to 9-tuple
            date = date_object.timetuple()
        else:
            if '2024' in date:
                date_string = ' '.join(date.split('2024')[:3])
            else:
                date_string = ' '.join(date.split('2023')[:3])
            return date_string

    date_result = {}

    today = datetime.now().date()

    if isinstance(date, tuple):
        date = datetime(*date[:6]).date()
    
    if date == today:
        date_result['short'] = 'Today'

    for day in range(1, 16):
        comparison = today - timedelta(days=day)
        if date == comparison:
            date_result['short'] = f"{day} day{'s' if day > 1 else ''} ago"

    date_result['full'] = date.strftime('%Y/%m/%d')
    return date_result


def main():
    """Main function to fetch and cache RSS feeds."""
    categories = [file.replace(".json", "") for file in os.listdir(f"{config.FEEDS_PATH}")]

    total_done = 0
    
    for selected_filter in categories:
        percentage = (total_done * 100) // len(categories)
        print(f"\n[{percentage}%] Handling cache for {selected_filter}...")
        
        rss_feeds = json_util.read_json(f"{config.FEEDS_PATH}/{selected_filter}")
        all_rss_data = []

        # Use threads to fetch RSS feeds concurrently
        threads = []
        result_list = []

        for feed_info in rss_feeds:
            thread = threading.Thread(target=fetch_rss_feed, args=(feed_info["url"], selected_filter, result_list))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        for rss_data in result_list:
            if len(rss_data) == 0:
                continue
            
            rss_data["site"] = feed_info["site"]
            all_rss_data.append(rss_data)
        
        # Merge articles from different feeds into a single list
        merged_articles = []
        for rss_data in all_rss_data:
            merged_articles.extend(rss_data["items"])

        if not merged_articles:
            print(f"[-] Empty cache: {selected_filter}")
            continue

        # Shuffle merged articles to mix them up
        shuffle(merged_articles)

        insert_to_database(merged_articles, selected_filter)
        total_done += 1
        
        print(f"[{len(merged_articles)} articles] Saved for {selected_filter}.")
    
    return print('[+] Finished!')

if __name__ == "__main__":
    main()
