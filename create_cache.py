import time, threading
from feedparser import parse
from requests import get
from datetime import datetime
from random import shuffle
from bs4 import BeautifulSoup
from os import listdir
from hashlib import md5
from sys import exit

from website_scripts.config import *
from website_scripts.scripts import read_json, write_json

def get_img(feed, item):
    """Extract image source from RSS item."""
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
            if ".jpg" in entry['href']:
                return entry['href']
    #src = get_link_preview(item.link)
    src = 'static/img/infomundi2.png'
    return src

def fetch_rss_feed(rss_url, news_filter, result_list):
    """Fetch RSS feed and store relevant information in a result list."""
    headers = {
        'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }
    try:
        response = get(rss_url, timeout=7, headers=headers)
        if response.status_code == 200:
            feed = parse(response.content)
        else:
            raise Exception
    except KeyboardInterrupt:
        exit()
    except Exception as err:
        print(f'[!] {rss_url} // {response.status_code}')
        return {}

    icon = ''
    try:
        icon = feed.feed.image.href
    except:
        if 'logo' in feed.feed.keys():
            icon = feed.feed.logo

    if icon == "":
        feed = read_json(f'{FEEDS_PATH}/{news_filter}')
        for entry in feed:
            if entry['url'] == rss_url and 'favicon' in entry.keys():
                icon = entry['favicon']

    try:
        data = {
            'title': feed.feed.title,
            'link': feed.feed.link,
            'items': [
                {
                    'title': item.title,
                    'description': item.description if 'description' in item else 'No description provided',
                    'feed_icon': icon,
                    'id': f'{md5(item.title.encode()).hexdigest()}',
                    'publisher': feed.feed.title,
                    'publisher_link': feed.feed.link,
                    'link': item.link,
                    'pubDate': item.published,
                    'media_content': {
                        'url': item.media_content[0]['url'] if 'media_content' in item else get_img(feed, item),
                    }
                }
                for item in feed.entries
            ]
        }
    except:
        print(f"[!] Exception getting {rss_url} ({news_filter})")
        data = {}

    result_list.append(data)

def main():
    """Main function to fetch and cache RSS feeds."""
    categories = [file.replace(".json", "") for file in listdir(f"{FEEDS_PATH}")]
    month_text = time.strftime("%B")
    current_month = datetime.today().month

    for selected_filter in categories:
        now = time.time()
        cache_exists = True

        try:
            cache = read_json(f"{CACHE_PATH}/{selected_filter}")

            if int(now - float(cache["created_at"])) < 21600 or selected_filter == '': # change time
                print(f"[~] Skipping {selected_filter}")
                continue
        except:
            pass

        print(f"[~] Handling cache for {selected_filter}...")
        rss_feeds = read_json(f"{FEEDS_PATH}/{selected_filter}")
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
            for item in rss_data["items"]:
                title = item["title"]
                if len(title) > 90:
                    item["title"] = title[:85] + "..."
                pubdate = item['pubDate']
                if pubdate.startswith('2023'):
                    pubdate = pubdate[:10]
                elif pubdate[3] == ',':
                    pubdate = pubdate[5:16]
                else:
                    pubdate = pubdate[:11]
                item['pubDate'] = pubdate
            rss_data["site"] = feed_info["site"]
            all_rss_data.append(rss_data)
            # Merge articles from different feeds into a single list

        merged_articles = []
        for rss_data in all_rss_data:
            merged_articles.extend(rss_data["items"])

        # Shuffle merged articles to mix them up
        shuffle(merged_articles)
        page_separated_articles = {}
        page_separated_articles["created_at"] = now
        index = 0
        total_pages = len(merged_articles) // 100
        if total_pages == 0:
            total_pages += 1
        for page in range(1, total_pages + 1):
            page_separated_articles[f"page_{str(page)}"] = []
            try:
                page_separated_articles[f"page_{str(page)}"].extend(merged_articles[index:index+100])
                index += 100
            except:
                page_separated_articles[f"page_{str(page)}"].extend(merged_articles)
        if len(merged_articles) != 0:
            write_json(page_separated_articles, f"{CACHE_PATH}/{selected_filter}")
            print(f"[{total_pages} pages // {len(merged_articles)} articles] Wrote json for {selected_filter}.")
        else:
            print(f"[-] Empty cache: {selected_filter}")

if __name__ == "__main__":
    main()
