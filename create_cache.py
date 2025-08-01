import feedparser
import threading
import logging
import pymysql
import requests
import yake

from random import shuffle, choice
from urllib.parse import urljoin
from datetime import datetime
from bs4 import BeautifulSoup

from website_scripts import (
    config,
    input_sanitization,
    immutable,
    hashing_util,
    qol_util,
)

# Database connection parameters
db_params = {
    "host": "127.0.0.1",
    "user": config.MYSQL_USERNAME,
    "password": config.MYSQL_PASSWORD,
    "db": config.MYSQL_DATABASE,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

db_connection = pymysql.connect(**db_params)

# Setup logging
logging.basicConfig(
    filename=f"{config.LOCAL_ROOT}/logs/create_cache.log",
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
)


def extract_yake(text: str, lang_code: str = "en", top_n: int = 5) -> tuple:
    kw_extractor = yake.KeywordExtractor(lan=lang_code, n=2, top=top_n)
    return (kw for kw, score in kw_extractor.extract_keywords(text))


def log_message(message):
    print(f"[~] {message}")
    # logging.info(message)


def insert_story_and_tags(cursor, story, category_id):
    # 1) Insert the story
    story_sql = """
      INSERT IGNORE INTO stories
        (title, lang, author, description, url, url_hash, pub_date, category_id, publisher_id)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    cursor.execute(
        story_sql,
        (
            story["story_title"],
            story["story_lang"],
            story["story_author"],
            story["story_description"],
            story["story_url"],
            story["story_url_hash"],
            story["story_pubdate"],
            category_id,
            story["publisher_id"],
        ),
    )
    # 2) If the story was new, grab its ID
    if cursor.lastrowid:
        new_story_id = cursor.lastrowid
    else:
        # it was ignored (duplicate); fetch existing ID
        cursor.execute(
            "SELECT id FROM stories WHERE url_hash = %s", (story["story_url_hash"],)
        )
        new_story_id = cursor.fetchone()["id"]

    # 3) Insert tags in bulk for this story
    tag_values = [
        (new_story_id, tag.strip()) for tag in story["story_tags"] if tag.strip()
    ]
    if tag_values:
        tags_sql = """
          INSERT IGNORE INTO tags (story_id, tag)
          VALUES (%s, %s)
        """
        cursor.executemany(tags_sql, tag_values)


def insert_stories_to_database(stories, category_name, category_id):
    exceptions = 0
    with db_connection.cursor() as cursor:
        for story in stories:
            try:
                insert_story_and_tags(cursor, story, category_id)
            except Exception as e:
                log_message(f"Error inserting story or tags: {e}")
                exceptions += 1
        db_connection.commit()
    return exceptions


def fetch_feed(publisher: dict, news_filter: str, result_list: list):
    """
    Fetch RSS feed and store relevant information in a result list.

    Args:
        publisher (dict): The publisher data.
        news_filter (str): A filter keyword for news items.
        result_list (list): A list to store the fetched and processed news items.

    Appends the fetched and processed news items to the result_list.
    """
    publisher_url = publisher.get("feed_url") or publisher.get("site_url")
    if not input_sanitization.is_valid_url(publisher_url):
        log_message(f"Invalid url: {publisher_url}")
        return {}

    # Removes the ending slash if it ends with one
    if publisher_url.endswith("/"):
        publisher_url = publisher_url[:-1]

    invalid_feed = False
    try:
        response = requests.get(
            publisher_url,
            timeout=5,
            headers={
                "User-Agent": choice(immutable.USER_AGENTS),
                "Referer": "www.google.com",
            },
        )

        feed = feedparser.parse(response.content)
    except Exception as e:
        log_message(f"Exception: {e}")
        invalid_feed = True

    # Tries to find the RSS feed endpoint
    if invalid_feed:
        feed = find_rss_feed(publisher_url)

    if not feed:
        log_message(f"Could not find feed for {publisher_url}, skipping...")
        return {}

    try:
        data = {
            "title": getattr(feed.feed, "title", "Unknown Publisher").strip(),
            "link": getattr(feed.feed, "link", "Unknown Link").strip(),
            "items": [],
        }

        for story in feed.entries:
            story_title = input_sanitization.sanitize_html(
                input_sanitization.decode_html_entities(story.get("title"))
            )
            story_description = input_sanitization.sanitize_html(
                input_sanitization.decode_html_entities(
                    story.get("description") or story.get("summary")
                )
            )

            story_author = input_sanitization.sanitize_html(
                input_sanitization.decode_html_entities(story.get("author"))
            )
            if story_author == "None":  # this actually happens
                story_author = None

            if not story_title:
                log_message("No story title was identified, skipping")
                continue

            # Gentle cuts text (without breaking off words)
            story_title = input_sanitization.gentle_cut_text(250, story_title)
            story_description = input_sanitization.gentle_cut_text(
                500, story_description
            )

            story_categories = [tag.term for tag in story.get("tags", [])]

            # Checks to see if the url is valid
            story_url = story.get("link")
            if not input_sanitization.is_valid_url(story_url) or len(story_url) > 512:
                log_message(f"Story link ({story_url}) is not valid. Skipping.")
                continue

            pubdate = (
                story.get("published_parsed")
                or story.get("published")
                or story.get("updated")
            )

            # Tries to format pubdate
            story_pubdate = format_date(pubdate).get(
                "datetime", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            story_lang = qol_util.detect_language(
                f"{story_title} {story_description}"
            )  # Returns language code (en, pt, es...)

            story_tags = extract_yake(
                f"{story_title} {story_description}", lang_code=story_lang
            )

            new_story = {
                "story_title": story_title,
                "story_categories": story_categories,
                "story_tags": story_tags,
                "story_lang": story_lang,
                "story_author": story_author,
                "story_description": story_description,
                "story_pubdate": story_pubdate,
                "story_url_hash": hashing_util.string_to_md5_binary(story_url),
                "story_url": story_url,
                "publisher_id": publisher["id"],
            }

            data["items"].append(new_story)

    except Exception as err:
        log_message(f"Exception getting {publisher_url} ({news_filter}) // {err}")
        data = {}

    log_message(f"Successfully processed feed for {publisher['name']}!")
    result_list.append(data)


def format_date(date) -> dict:
    """
    Converts a date object or ISO formatted date string into a readable MySQL DATETIME format.
    """

    # Convert date to a 9-tuple if it's a string in ISO format
    if isinstance(date, str):
        try:
            date = datetime.fromisoformat(date).timetuple()
        except ValueError:
            return {"error": "Invalid date format"}

    # Convert the 9-tuple date to a datetime object
    if isinstance(date, tuple):
        date = datetime(*date[:6])

    # Ensure it's a datetime object
    if not isinstance(date, datetime):
        return {"error": "Invalid date format"}

    return {"datetime": date.strftime("%Y-%m-%d %H:%M:%S")}


def find_rss_feed(base_url, candidates=None, timeout=5):
    """
    Attempts to discover a valid RSS/Atom feed for the given base URL by
    1) Crawling <link> tags in the HTML head for feeds.
    2) Testing a list of common feed endpoint paths.

    Args:
        base_url (str): The news website's base URL (e.g., https://example.com).
        candidates (list): Optional list of feed endpoint paths to try.
        timeout (int): Request timeout in seconds.

    Returns:
        str or None: The full URL to a discovered feed, or None if none found.
    """
    discovered = []
    # 1) Crawl HTML for <link rel="alternate"> tags
    try:
        resp = requests.get(base_url, timeout=timeout)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.find_all(
                "link", rel=lambda x: x and "alternate" in x.lower()
            ):
                t = link.get("type", "").lower()
                if "rss" in t or "atom" in t or "xml" in t:
                    href = link.get("href")
                    if href:
                        full = urljoin(base_url, href)
                        discovered.append(full)
    except requests.RequestException:
        pass

    # 2) Fallback: common endpoints
    if candidates is None:
        candidates = [
            "/rss",
            "/rss.xml",
            "/feed",
            "/feed.xml",
            "/atom.xml",
            "/index.rdf",
        ]

    # Prepend discovered feeds so they get tested first
    endpoints = discovered + candidates

    # Test each endpoint
    for endpoint in endpoints:
        # If endpoint looks like full URL, use it; else join with base
        feed_url = (
            endpoint
            if (endpoint.startswith("http") or endpoint.startswith("https"))
            else urljoin(base_url, endpoint)
        )
        try:
            resp = requests.get(feed_url, timeout=timeout)
            ct = resp.headers.get("Content-Type", "")
            if resp.status_code == 200 and "xml" in ct:
                parsed = feedparser.parse(resp.content)
                if parsed.bozo == 0 and parsed.entries:
                    return feed_url
        except requests.RequestException:
            continue

    return None


def fetch_categories_from_database():
    log_message("Fetching categories from the database")
    try:
        with db_connection.cursor() as cursor:
            cursor.execute("SELECT * FROM categories")
            categories = cursor.fetchall()
    except Exception as e:
        log_message(f"Error fetching categories: {e}")
        return []

    # DEBUG if row["name"] == "br_general"
    category_list = [(row["id"], row["name"]) for row in categories]
    shuffle(category_list)

    log_message(f"Got {len(category_list)} categories from the database")
    return category_list


def fetch_publishers_from_database(category_id: int):
    log_message(f"Fetching publishers for category ID: {category_id}")
    try:
        with db_connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM publishers WHERE category_id = %s",
                (category_id,),
            )
            publishers = cursor.fetchall()
    except Exception as e:
        log_message(f"Error fetching publishers: {e}")
        return []

    log_message(f"Got {len(publishers)} publishers from the database")
    return publishers


def main():
    total_done = 0
    categories = fetch_categories_from_database()

    for category_id, category_name in categories:
        percentage = (total_done // len(categories)) * 100
        log_message(f"\n[{round(percentage, 2)}%] Handling {category_name}...")

        threads = []
        result_list = []

        publishers = fetch_publishers_from_database(category_id)
        for publisher in publishers:
            thread = threading.Thread(
                target=fetch_feed, args=(publisher, category_name, result_list)
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Merges all articles in a single list
        merged_articles = []
        for rss_data in result_list:
            if not rss_data:
                continue

            merged_articles.extend(rss_data["items"])

        if not merged_articles:
            log_message(f"[-] Empty cache: {category_name}")
            continue

        shuffle(merged_articles)

        exceptions_count = insert_stories_to_database(
            merged_articles, category_name, category_id
        )
        total_done += 1

        log_message(
            f"[{len(merged_articles) - exceptions_count} articles] Saved for {category_name}."
        )

    log_message("Finished!")


if __name__ == "__main__":
    main()
