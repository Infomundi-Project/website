import feedparser
import threading
import logging
import pymysql
import requests
import yake
import os

from random import shuffle, choice
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager

from website_scripts import (
    config,
    input_sanitization,
    immutable,
    hashing_util,
    qol_util,
)

# Database connection parameters
db_params = {
    "host": config.MYSQL_HOST,
    "user": config.MYSQL_USERNAME,
    "password": config.MYSQL_PASSWORD,
    "db": config.MYSQL_DATABASE,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

# Thread-local storage for database connections
thread_local = threading.local()

# Ensure logs directory exists
log_dir = f"{config.LOCAL_ROOT}/logs"
os.makedirs(log_dir, exist_ok=True)

# Setup logging
logging.basicConfig(
    filename=f"{log_dir}/create_cache.log",
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
)

# Configuration
MAX_WORKERS = 20  # Limit concurrent threads
REQUEST_TIMEOUT = 5  # Seconds

@contextmanager
def get_db_connection():
    """
    Thread-safe context manager for database connections.
    Each thread gets its own connection from thread-local storage.
    """
    if not hasattr(thread_local, "connection") or thread_local.connection is None:
        thread_local.connection = pymysql.connect(**db_params)

    connection = thread_local.connection
    try:
        connection.ping(reconnect=True)
        yield connection
    except Exception as e:
        log_message(f"Database connection error: {e}")
        # Close bad connection and create new one
        try:
            connection.close()
        except:
            pass
        thread_local.connection = pymysql.connect(**db_params)
        yield thread_local.connection


def prune_old_stories(days: int = 7) -> dict:
    """
    Delete stories older than `days` and any associated tags.
    Returns counts of deleted rows.
    """
    try:
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        with get_db_connection() as db_connection:
            with db_connection.cursor() as cursor:
                # 1) Remove tags for stories older than cutoff
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
        log_message(f"Error pruning old stories: {e}")
        return {"stories_deleted": 0, "tags_deleted": 0}


def extract_yake(text: str, lang_code: str = "en", top_n: int = 5) -> tuple:
    """Extract keywords using YAKE."""
    try:
        kw_extractor = yake.KeywordExtractor(lan=lang_code, n=2, top=top_n)
        return tuple(kw for kw, score in kw_extractor.extract_keywords(text))
    except Exception as e:
        log_message(f"YAKE extraction error: {e}")
        return tuple()


def log_message(message):
    print(f"[~] {message}")
    logging.info(message)


def insert_stories_to_database(stories, category_name, category_id):
    """
    Bulk-inserts stories and tags for a given category.
    Uses thread-safe database connection.
    Returns the number of exceptions encountered (should be zero).
    """
    if not stories:
        return 0

    exceptions = 0

    with get_db_connection() as db_connection:
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

                # 2) Fetch IDs for all inserted stories
                url_hashes = tuple(s["story_url_hash"] for s in stories)
                if len(url_hashes) == 1:
                    url_hashes = (url_hashes[0], url_hashes[0])

                cursor.execute(
                    "SELECT id, url_hash FROM stories WHERE url_hash IN %s",
                    (url_hashes,),
                )
                id_map = {row["url_hash"]: row["id"] for row in cursor.fetchall()}

                # 3) Bulk-insert all tags
                tag_sql = """
                  INSERT IGNORE INTO tags (story_id, tag)
                  VALUES (%s, %s)
                """
                tag_values = []
                for s in stories:
                    sid = id_map.get(s["story_url_hash"])
                    if not sid:
                        continue
                    for tag in s["story_tags"]:
                        tag = tag.strip()
                        if tag:
                            tag_values.append((sid, tag))

                if tag_values:
                    cursor.executemany(tag_sql, tag_values)

                db_connection.commit()

            except Exception as e:
                db_connection.rollback()
                log_message(f"Error bulk inserting stories/tags: {e}")
                exceptions += 1

    return exceptions


def fetch_feed(publisher: dict, news_filter: str):
    """
    Fetch RSS feed and return processed news items.
    Now returns data instead of appending to shared list (thread-safe).
    """
    publisher_url = publisher.get("feed_url")
    if not input_sanitization.is_valid_url(publisher_url):
        log_message(f"Invalid url: {publisher_url}")
        return {}

    try:
        response = requests.get(
            publisher_url,
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": choice(immutable.USER_AGENTS),
                "Referer": "www.google.com",
            },
        )
        feed = feedparser.parse(response.content)

    except Exception as e:
        log_message(f"Exception fetching {publisher_url}: {e}")
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
            if story_author == "None":
                story_author = None

            if not story_title:
                continue

            story_title = input_sanitization.gentle_cut_text(250, story_title)
            story_description = input_sanitization.gentle_cut_text(
                500, story_description
            )

            story_categories = [tag.term for tag in story.get("tags", [])]

            story_url = story.get("link")
            if not input_sanitization.is_valid_url(story_url) or len(story_url) > 512:
                continue

            pubdate = (
                story.get("published_parsed")
                or story.get("published")
                or story.get("updated")
            )

            story_pubdate = format_date(pubdate).get(
                "datetime", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            story_lang = qol_util.detect_language(f"{story_title} {story_description}")

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

        log_message(f"Successfully processed feed for {publisher['name']}!")
        return data

    except Exception as err:
        log_message(f"Exception processing {publisher_url} ({news_filter}): {err}")
        return {}


def format_date(date) -> dict:
    """
    Converts a date object or ISO formatted date string into MySQL DATETIME format.
    """
    if isinstance(date, str):
        try:
            date = datetime.fromisoformat(date).timetuple()
        except ValueError:
            return {"error": "Invalid date format"}

    if isinstance(date, tuple):
        date = datetime(*date[:6])

    if not isinstance(date, datetime):
        return {"error": "Invalid date format"}

    return {"datetime": date.strftime("%Y-%m-%d %H:%M:%S")}


def find_rss_feed(base_url, candidates=None, timeout=5):
    """
    Attempts to discover a valid RSS/Atom feed for the given base URL.
    """
    discovered = []

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

    endpoints = discovered + candidates

    for endpoint in endpoints:
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
    """Fetch all categories from database."""
    log_message("Fetching categories from the database")

    with get_db_connection() as db_connection:
        try:
            with db_connection.cursor() as cursor:
                cursor.execute("SELECT * FROM categories")
                categories = cursor.fetchall()
        except Exception as e:
            log_message(f"Error fetching categories: {e}")
            return []

    # e.g. [(15, 'cl_general'), (194, 'as_general'), ...]
    category_list = [(row["id"], row["name"]) for row in categories]
    shuffle(category_list)

    log_message(f"Got {len(category_list)} categories from the database")
    return category_list


def fetch_publishers_from_database(category_id: int):
    """Fetch publishers for a specific category."""
    log_message(f"Fetching publishers for category ID: {category_id}")

    with get_db_connection() as db_connection:
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
    """Main execution function with controlled concurrency."""
    total_done = 0
    categories = fetch_categories_from_database()

    if not categories:
        log_message("No categories found!")
        return

    for category_id, category_name in categories:
        if config.SEARCH_NEWS_DEBUG:
            if category_name != "br_general":
                continue

        # Fixed percentage calculation
        percentage = (total_done / len(categories)) * 100
        log_message(f"\n[{round(percentage, 2)}%] Handling {category_name}...")

        publishers = fetch_publishers_from_database(category_id)
        if not publishers:
            log_message(f"No publishers for {category_name}")
            total_done += 1
            continue

        # Use ThreadPoolExecutor with limited workers
        result_list = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all tasks
            future_to_publisher = {
                executor.submit(fetch_feed, publisher, category_name): publisher
                for publisher in publishers
            }

            # Collect results as they complete
            for future in as_completed(future_to_publisher):
                try:
                    data = future.result(timeout=REQUEST_TIMEOUT + 5)
                    if data:
                        result_list.append(data)
                except Exception as e:
                    publisher = future_to_publisher[future]
                    log_message(
                        f"Exception for {publisher.get('name', 'unknown')}: {e}"
                    )

        # Merge all articles
        merged_articles = []
        for rss_data in result_list:
            if rss_data and "items" in rss_data:
                merged_articles.extend(rss_data["items"])

        if not merged_articles:
            log_message(f"[-] Empty cache: {category_name}")
            total_done += 1
            continue

        shuffle(merged_articles)
        exceptions_count = insert_stories_to_database(
            merged_articles, category_name, category_id
        )
        total_done += 1

        log_message(
            f"[{len(merged_articles) - exceptions_count} articles] Saved for {category_name}."
        )

    # Auto-delete anything older than 7 days
    prune_old_stories(days=7)

    log_message("Finished!")


if __name__ == "__main__":
    main()