import feedparser
import threading
import logging
import pymysql
import requests
import yake

from random import shuffle, choice
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

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


def prune_old_stories(days: int = 7) -> dict:
    """
    Delete stories older than `days` and any associated tags.
    Returns counts of deleted rows.
    """
    try:
        # Use a concrete cutoff timestamp to avoid INTERVAL param quirks
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        db_connection.ping(reconnect=True)

        with db_connection.cursor() as cursor:
            # 1) Remove tags for stories older than cutoff (harmless if FK cascade exists)
            delete_tags_sql = """
                DELETE t
                FROM tags AS t
                JOIN stories AS s ON s.id = t.story_id
                WHERE s.pub_date < %s
            """
            cursor.execute(delete_tags_sql, (cutoff,))
            tags_deleted = cursor.rowcount

            # 2) Remove the old stories
            delete_stories_sql = """
                DELETE FROM stories
                WHERE pub_date < %s
            """
            cursor.execute(delete_stories_sql, (cutoff,))
            stories_deleted = cursor.rowcount

        db_connection.commit()
        log_message(
            f"Pruned {stories_deleted} stories and {tags_deleted} tags older than {days} days."
        )
        return {"stories_deleted": stories_deleted, "tags_deleted": tags_deleted}

    except Exception as e:
        db_connection.rollback()
        log_message(f"Error pruning old stories: {e}")
        return {"stories_deleted": 0, "tags_deleted": 0}


def extract_yake(text: str, lang_code: str = "en", top_n: int = 5) -> tuple:
    kw_extractor = yake.KeywordExtractor(lan=lang_code, n=2, top=top_n)
    return (kw for kw, score in kw_extractor.extract_keywords(text))


def log_message(message):
    print(f"[~] {message}")
    # logging.info(message)


def insert_stories_to_database(stories, category_name, category_id):
    """
    Bulk-inserts stories and tags for a given category.
    Returns the number of exceptions encountered (should be zero).
    """
    exceptions = 0
    with db_connection.cursor() as cursor:
        try:
            # 1) Bulk-insert all stories at once
            story_sql = """
              INSERT IGNORE INTO stories
                (title, lang, author, description, url, url_hash, pub_date, category_id, publisher_id)
              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            story_values = [
                (
                    s["story_title"],
                    s["story_lang"],
                    s["story_author"],
                    s["story_description"],
                    s["story_url"],
                    s["story_url_hash"],
                    s["story_pubdate"],
                    category_id,
                    s["publisher_id"],
                )
                for s in stories
            ]
            cursor.executemany(story_sql, story_values)

            # 2) Fetch IDs for all inserted (or pre-existing) stories in one go
            url_hashes = tuple(s["story_url_hash"] for s in stories)
            # Note: if there's only one element, make sure it's still a tuple
            if len(url_hashes) == 1:
                url_hashes = (url_hashes[0], url_hashes[0])
            cursor.execute(
                "SELECT id, url_hash FROM stories WHERE url_hash IN %s",
                (url_hashes,),
            )
            id_map = {row["url_hash"]: row["id"] for row in cursor.fetchall()}

            # 3) Bulk-insert all tags at once
            tag_sql = """
              INSERT IGNORE INTO tags (story_id, tag)
              VALUES (%s, %s)
            """
            tag_values = []
            for s in stories:
                sid = id_map.get(s["story_url_hash"])
                if not sid:
                    # This should not happen unless something weird occurred
                    continue
                for tag in s["story_tags"]:
                    tag = tag.strip()
                    if tag:
                        tag_values.append((sid, tag))

            if tag_values:
                cursor.executemany(tag_sql, tag_values)

            db_connection.commit()

        except Exception as e:
            # If anything goes wrong, roll back and count it as an exception
            db_connection.rollback()
            log_message(f"Error bulk inserting stories/tags: {e}")
            exceptions += 1

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
    publisher_url = publisher.get("feed_url")  # or publisher.get("site_url")
    if not input_sanitization.is_valid_url(publisher_url):
        log_message(f"Invalid url: {publisher_url}")
        return {}

    is_invalid_feed = False
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
        is_invalid_feed = True

    if is_invalid_feed:
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
            "rss",
            "index.xml",
            "feed/index.php",
            "feed.xml",
            "feed.atom",
            "feed.rss",
            "feed.json",
            "feed.php",
            "feed.asp",
            "posts.rss",
            "blog.xml",
            "atom.xml",
            "podcasts.xml",
            "main.atom",
            "main.xml",
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

    # 👇 auto-delete anything older than 7 days
    prune_old_stories(days=7)

    log_message("Finished!")


if __name__ == "__main__":
    main()
