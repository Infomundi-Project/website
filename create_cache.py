import time, threading
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from feedparser import parse
from random import shuffle
from requests import get
from hashlib import md5
from os import listdir
from sys import exit

from website_scripts.scripts import remove_html_tags
from website_scripts import json_util
from website_scripts import config

def get_img(feed, item) -> str:
    """Returns img url associated with the RSS item."""
    src = ""
    try:
        src = item.contributors[0]['href']
        return src
    except:
        if not item.has_key('summary') and not item.has_key('description'):
            return ''
        soup = BeautifulSoup(item.summary, 'html.parser')
        img_tags = soup.find_all('img')
        for img_tag in img_tags:
            src = img_tag.get('src')
            return src
    for entry in item.links:
        if "href" in entry.keys():
            if ".jpg" in entry['href'] or ".png" in entry['href'] or ".webp" in entry['href']:
                return entry['href']
    #src = get_link_preview(item.link)
    src = 'static/img/infomundi-white-darkbg-square.webp'
    return src

def fetch_rss_feed(rss_url: str, news_filter: str, result_list: list):
    """Fetch RSS feed and store relevant information in a result list."""
    headers = {
        'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }
    
    response = get(rss_url, timeout=7, headers=headers)
    if response.status_code != 200:
        print(f"[!] {rss_url} // {response.status_code}")
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
            'items': [
                {
                    'title': item.title,
                    'description': f'{remove_html_tags(item.description)[:500]}' if 'description' in item else 'No description provided',
                    'id': f'{md5(item.title.encode()).hexdigest()}',
                    'publisher': feed.feed.title,
                    'publisher_link': feed.feed.link,
                    'link': item.link,
                    'pubDate': format_date(item.published_parsed),
                    'media_content': {
                        'url': item.media_content[0]['url'] if 'media_content' in item else get_img(feed, item),
                    }
                }
                for item in feed.entries
            ]
        }
    except Exception as err:
        print(f"[!] Exception getting {rss_url} ({news_filter}) // {err}")
        data = {}

    result_list.append(data)

def format_date(date) -> str:
    """Takes a pythonic date object and converts into a string to show in the news page"""
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
    now = time.time()
    for selected_filter in categories:
        print(f"[~] Handling cache for {selected_filter}...")
        
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

        page_separated_articles = {}
        page_separated_articles['created_at'] = now
        
        total_pages = len(merged_articles) // 100
        if total_pages == 0:
            total_pages += 1
        
        index = 0
        for page in range(1, total_pages + 1):
            page_separated_articles[f"page_{str(page)}"] = []
            try:
                page_separated_articles[f"page_{str(page)}"].extend(merged_articles[index:index+100])
                index += 100
            except:
                page_separated_articles[f"page_{str(page)}"].extend(merged_articles)

        json_util.write_json(page_separated_articles, f"{config.CACHE_PATH}/{selected_filter}")
        print(f"[{total_pages} pages // {len(merged_articles)} articles] Wrote json for {selected_filter}.")

if __name__ == "__main__":
    main()
