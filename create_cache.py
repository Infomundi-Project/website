import time, threading
from datetime import datetime, timedelta
from random import shuffle, choice
from unidecode import unidecode
from bs4 import BeautifulSoup
from feedparser import parse
from requests import get
from hashlib import md5
from os import listdir
from sys import exit

from website_scripts import json_util, config, scripts, immutable


def get_img(feed, item, is_search: bool=False) -> str:
    """Returns img url associated with the RSS item."""
    src = "static/img/infomundi-white-darkbg-square.webp"
    
    try:
        src = item.contributors[0]['href']
        return src
    except Exception:
        if not item.has_key('summary') and not item.has_key('description'):
            return scripts.get_link_preview(item.link, source='cache')
        
        soup = BeautifulSoup(item.summary, 'html.parser')
        img_tags = soup.find_all('img')
        for img_tag in img_tags:
            src = img_tag.get('src')
            return src
    
    return src


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
            image_url = item.media_content[0]['url'] if 'media_content' in item else ''
            if not image_url:
                image_url = get_img(feed, item)

            feed_publisher = feed.feed.title
            feed_link = feed.feed.link

            item_title = item.get('title', f'No title was provided')
            item_description = scripts.remove_html_tags(item.get('description', 'No description was provided'))[:700]
            item_link = item.link
            
            for character in immutable.SPECIAL_CHARACTERS:
                feed_publisher = feed_publisher.replace(character, '')
                feed_link = feed_link.replace(character, '')

                item_title = item_title.replace(character, '')
                item_link = item_link.replace(character, '')

            if not scripts.is_valid_url(feed_link) or not scripts.is_valid_url(item_link):
                print(f'[-] Either the feed link ({feed_link}) or the item link ({item_link}) is not valid. Skipping.')
                continue

            if item.has_key('published_parsed'):
                pubdate = item.published_parsed
            elif item.has_key('published'):
                pubdate = item.published
            else:
                pubdate = item.updated

            data['items'].append(
                {
                'title': item_title,
                'description': item_description,
                'id': f'{md5(unidecode(item_title.lower()).encode()).hexdigest()}',
                'publisher': feed_publisher,
                'publisher_link': feed_link,
                'link': item_link,
                'pubDate': format_date(pubdate),
                'media_content': {
                    'url': image_url
                    }
                })
    
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

    today = datetime.now().date()

    if isinstance(date, tuple):
        date = datetime(*date[:6]).date()
    
    if date == today:
        return 'Today'

    for day in range(1, 16):
        comparison = today - timedelta(days=day)
        if date == comparison:
            return f"{day} day{'s' if day > 1 else ''} ago"

    return date.strftime('%Y/%m/%d')


def main():
    """Main function to fetch and cache RSS feeds."""
    current_month = datetime.today().month

    categories = [file.replace(".json", "") for file in listdir(f"{config.FEEDS_PATH}")]
    now = datetime.now()

    for selected_filter in categories:
        print(f"\n[~] Handling cache for {selected_filter}...")

        cache_file_path = f'{config.CACHE_PATH}/{selected_filter}'

        # We check wether the cache already exist or not.
        is_new = False
        try:
            cache = json_util.read_json(cache_file_path)
        except FileNotFoundError:
            cache = {}
            cache['created_at'] = now.isoformat()
            is_new = True

        #if not scripts.is_cache_old(f'{cache_file_path}.json', 1):
        #    print(f'[-] Cache for {selected_filter} is not old enough.')
        #    continue
        
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

        # It may be a good idea to overwrite the cache with a time span of 7 days
        saved_timestamp = datetime.fromisoformat(cache['created_at'])

        time_difference = now - saved_timestamp
        if time_difference > timedelta(days=7) or is_new:
            cache['stories'] = []
            print('------------- Deleting all stories ----------')

        # Correct date
        try:
            updated_timestamp = datetime.fromisoformat(cache['updated_at'])
        except KeyError:
            updated_timestamp = now
            cache['updated_at'] = now
        
        time_difference = now - updated_timestamp
        if time_difference > timedelta(days=1):
            for story in cache['stories']:
                pubdate = story['pubDate']

                if pubdate == 'Today':
                    story['pubDate'] = '1 day ago'
                elif 'ago' in pubdate:
                    days = int(pubdate[0])
                    story['pubDate'] = f'{days + 1} days ago'
                else:
                    continue

        existing_ids = [x['id'] for x in cache['stories']]

        # Removes all repeated articles
        articles_to_add = [x for x in merged_articles if x['id'] not in existing_ids]

        if not articles_to_add:
            print(f'[+] Cache for {selected_filter} is full. No need to write anything.')
            continue

        cache['updated_at'] = now.isoformat()

        # Add newer articles to the beginning of the cache
        articles_to_add.extend(cache['stories'])
        cache['stories'] = articles_to_add

        json_util.write_json(cache, f"{config.CACHE_PATH}/{selected_filter}")
        print(f"[{len(articles_to_add)} articles] Wrote json for {selected_filter}.")
    
    return print('Finished.')

if __name__ == "__main__":
    main()
