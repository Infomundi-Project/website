import asyncio
import argparse
import logging
import os
import signal
import sys

import aiohttp
import aiomysql
import feedparser
import pymysql
import yake

from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from random import shuffle, choice
from rich import box
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, MofNCompleteColumn
from rich.table import Table
from urllib.parse import urljoin

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
}

# Async database pool (initialized in main)
db_pool = None

# Process pool for CPU-bound YAKE extraction
process_pool = None

# Rich console for colored output
console = Console()

# Ensure logs directory exists
log_dir = f"{config.WEBSITE_ROOT}/logs"
os.makedirs(log_dir, exist_ok=True)

# Setup logging
logging.basicConfig(
    filename=f"{log_dir}/create_cache.log",
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
)

# Configuration
MAX_WORKERS = 25  # Limit concurrent threads (increased for better I/O parallelization)
REQUEST_TIMEOUT = 5  # Seconds (reduced from 5 for faster failure detection)

# Global state for graceful shutdown
shutdown_requested = False

# Statistics tracking
stats = {
    "total_articles": 0,
    "total_errors": 0,
    "category_stats": {},
    "error_types": {"timeouts": 0, "invalid_feeds": 0, "db_errors": 0, "other": 0},
    "start_time": None,
}


async def init_db_pool():
    """Initialize the async database connection pool."""
    global db_pool
    db_pool = await aiomysql.create_pool(
        host=db_params["host"],
        user=db_params["user"],
        password=db_params["password"],
        db=db_params["db"],
        charset=db_params["charset"],
        minsize=5,
        maxsize=20,
        autocommit=False,
        cursorclass=aiomysql.DictCursor,
    )
    return db_pool


@asynccontextmanager
async def get_db_connection():
    """
    Async context manager for database connections from the pool.
    """
    async with db_pool.acquire() as connection:
        try:
            yield connection
        except Exception as e:
            log_message(f"Database connection error: {e}")
            raise


async def prune_old_stories(days: int = 7) -> dict:
    """
    Delete stories older than `days` and any associated tags.
    Returns counts of deleted rows.
    """
    try:
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        async with get_db_connection() as db_connection:
            async with db_connection.cursor() as cursor:
                # 1) Remove tags for stories older than cutoff
                delete_tags_sql = """
                    DELETE t
                    FROM tags AS t
                    JOIN stories AS s ON s.id = t.story_id
                    WHERE s.pub_date < %s
                """
                await cursor.execute(delete_tags_sql, (cutoff,))
                tags_deleted = cursor.rowcount

                # 2) Remove the old stories
                delete_stories_sql = """
                    DELETE FROM stories
                    WHERE pub_date < %s
                """
                await cursor.execute(delete_stories_sql, (cutoff,))
                stories_deleted = cursor.rowcount

            await db_connection.commit()

        log_message(
            f"Pruned {stories_deleted} stories and {tags_deleted} tags older than {days} days.",
            level="success"
        )
        return {"stories_deleted": stories_deleted, "tags_deleted": tags_deleted}

    except Exception as e:
        log_message(f"Error pruning old stories: {e}", level="error")
        stats["error_types"]["db_errors"] += 1
        return {"stories_deleted": 0, "tags_deleted": 0}


def extract_yake_sync(text: str, lang_code: str = "en", top_n: int = 5) -> tuple:
    """
    Extract keywords using YAKE (synchronous, for use in process pool).
    """
    try:
        kw_extractor = yake.KeywordExtractor(lan=lang_code, n=2, top=top_n)
        return tuple(kw for kw, score in kw_extractor.extract_keywords(text))
    except Exception:
        return tuple()


async def extract_yake_batch(texts_with_langs: list) -> list:
    """
    Extract keywords for multiple texts using process pool for CPU-bound work.
    texts_with_langs: list of (text, lang_code) tuples
    Returns: list of keyword tuples
    """
    if not texts_with_langs:
        return []

    loop = asyncio.get_event_loop()

    # Run CPU-bound YAKE extraction in process pool
    try:
        results = await loop.run_in_executor(
            process_pool,
            _extract_yake_batch_sync,
            texts_with_langs
        )
        return results
    except Exception as e:
        log_message(f"YAKE batch extraction error: {e}")
        return [tuple() for _ in texts_with_langs]


def _extract_yake_batch_sync(texts_with_langs: list) -> list:
    """Synchronous batch extraction for process pool."""
    results = []
    # Cache extractors by language within this batch
    extractors = {}
    for text, lang_code in texts_with_langs:
        try:
            if lang_code not in extractors:
                extractors[lang_code] = yake.KeywordExtractor(lan=lang_code, n=2, top=5)
            kw_extractor = extractors[lang_code]
            keywords = tuple(kw for kw, score in kw_extractor.extract_keywords(text))
            results.append(keywords)
        except Exception:
            results.append(tuple())
    return results


def log_message(message, level="info", style=None):
    """
    Log message with rich console colors.
    Levels: info (blue), success (green), warning (yellow), error (red)
    """
    styles = {
        "info": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "red",
    }

    color = style or styles.get(level, "white")
    console.print(f"[{color}][~] {message}[/{color}]")
    logging.info(message)


async def get_existing_url_hashes(url_hashes: list) -> set:
    """
    Query existing URL hashes to avoid processing duplicates.
    Returns a set of hashes that already exist in the database.
    """
    if not url_hashes:
        return set()

    async with get_db_connection() as db_connection:
        async with db_connection.cursor() as cursor:
            # Handle single hash case
            if len(url_hashes) == 1:
                url_hashes = (url_hashes[0], url_hashes[0])
            else:
                url_hashes = tuple(url_hashes)

            placeholders = ",".join(["%s"] * len(url_hashes))
            await cursor.execute(
                f"SELECT url_hash FROM stories WHERE url_hash IN ({placeholders})",
                url_hashes,
            )
            rows = await cursor.fetchall()
            return {row["url_hash"] for row in rows}


async def insert_stories_to_database(stories, category_name, category_id):
    """
    Bulk-inserts stories and tags for a given category.
    Uses async database connection from pool.
    Returns the number of exceptions encountered (should be zero).
    """
    if not stories:
        return 0

    exceptions = 0
    BATCH_SIZE = 500  # Insert in batches for better performance

    async with get_db_connection() as db_connection:
        async with db_connection.cursor() as cursor:
            try:
                # 1) Bulk-insert all stories in batches
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

                # Insert in batches
                for i in range(0, len(story_values), BATCH_SIZE):
                    batch = story_values[i:i + BATCH_SIZE]
                    await cursor.executemany(story_sql, batch)

                # 2) Fetch IDs for all inserted stories
                url_hashes = [s["story_url_hash"] for s in stories]
                if len(url_hashes) == 1:
                    url_hashes = (url_hashes[0], url_hashes[0])
                else:
                    url_hashes = tuple(url_hashes)

                placeholders = ",".join(["%s"] * len(url_hashes))
                await cursor.execute(
                    f"SELECT id, url_hash FROM stories WHERE url_hash IN ({placeholders})",
                    url_hashes,
                )
                rows = await cursor.fetchall()
                id_map = {row["url_hash"]: row["id"] for row in rows}

                # 3) Bulk-insert all tags in batches
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
                    for i in range(0, len(tag_values), BATCH_SIZE):
                        batch = tag_values[i:i + BATCH_SIZE]
                        await cursor.executemany(tag_sql, batch)

                await db_connection.commit()

            except Exception as e:
                await db_connection.rollback()
                log_message(f"Error bulk inserting stories/tags: {e}", level="error")
                stats["error_types"]["db_errors"] += 1
                exceptions += 1

    return exceptions


async def fetch_feed(session: aiohttp.ClientSession, publisher: dict, news_filter: str):
    """
    Fetch RSS feed asynchronously and return processed news items.
    Uses aiohttp for non-blocking I/O.
    """
    publisher_url = publisher.get("feed_url")
    if not input_sanitization.is_valid_url(publisher_url):
        log_message(f"Invalid url: {publisher_url}")
        return {}

    try:
        # Use separate timeouts like requests did - more generous for real-world feeds
        timeout = aiohttp.ClientTimeout(
            total=REQUEST_TIMEOUT * 3,    # Total operation timeout
            connect=REQUEST_TIMEOUT,       # Connection timeout
            sock_read=REQUEST_TIMEOUT * 2  # Read timeout
        )
        headers = {
            "User-Agent": choice(immutable.USER_AGENTS),
            "Referer": "www.google.com",
        }
        async with session.get(publisher_url, timeout=timeout, headers=headers) as response:
            content = await response.read()
            feed = feedparser.parse(content)

    except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
        stats["error_types"]["timeouts"] += 1
        log_message(f"Timeout fetching {publisher_url}", level="warning")
        return {}
    except aiohttp.ClientError as e:
        stats["error_types"]["other"] += 1
        log_message(f"Connection error fetching {publisher_url}: {e}", level="warning")
        return {}
    except Exception as e:
        stats["error_types"]["other"] += 1
        log_message(f"Exception fetching {publisher_url}: {e}", level="error")
        return {}

    try:
        data = {
            "title": getattr(feed.feed, "title", "Unknown Publisher").strip(),
            "link": getattr(feed.feed, "link", "Unknown Link").strip(),
            "items": [],
            "texts_for_yake": [],  # Collect texts for batch YAKE processing
        }

        # First pass: collect all story data without YAKE extraction
        pending_stories = []
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

            combined_text = f"{story_title} {story_description}"
            story_lang = qol_util.detect_language(combined_text)

            pending_stories.append({
                "story_title": story_title,
                "story_categories": story_categories,
                "story_lang": story_lang,
                "story_author": story_author,
                "story_description": story_description,
                "story_pubdate": story_pubdate,
                "story_url_hash": hashing_util.string_to_md5_binary(story_url),
                "story_url": story_url,
                "publisher_id": publisher["id"],
                "combined_text": combined_text,
            })

        # Batch YAKE extraction for all stories
        if pending_stories:
            texts_with_langs = [
                (s["combined_text"], s["story_lang"]) for s in pending_stories
            ]
            tags_list = await extract_yake_batch(texts_with_langs)

            for story, tags in zip(pending_stories, tags_list):
                story["story_tags"] = tags
                del story["combined_text"]  # Remove temporary field
                data["items"].append(story)

        if data["items"]:
            log_message(f"Successfully processed feed for {publisher['name']} ({len(data['items'])} items)", level="success")
        else:
            stats["error_types"]["invalid_feeds"] += 1
            log_message(f"No valid items in feed for {publisher['name']}", level="warning")

        return data

    except Exception as err:
        stats["error_types"]["other"] += 1
        log_message(f"Exception processing {publisher_url} ({news_filter}): {err}", level="error")
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


async def find_rss_feed(base_url, candidates=None, timeout=5):
    """
    Attempts to discover a valid RSS/Atom feed for the given base URL.
    Uses async aiohttp for non-blocking I/O.
    """
    discovered = []
    client_timeout = aiohttp.ClientTimeout(total=timeout)

    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        try:
            async with session.get(base_url) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    soup = BeautifulSoup(text, "html.parser")
                    for link in soup.find_all(
                        "link", rel=lambda x: x and "alternate" in x.lower()
                    ):
                        t = link.get("type", "").lower()
                        if "rss" in t or "atom" in t or "xml" in t:
                            href = link.get("href")
                            if href:
                                full = urljoin(base_url, href)
                                discovered.append(full)
        except aiohttp.ClientError:
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
                async with session.get(feed_url) as resp:
                    ct = resp.headers.get("Content-Type", "")
                    if resp.status == 200 and "xml" in ct:
                        content = await resp.read()
                        parsed = feedparser.parse(content)
                        if parsed.bozo == 0 and parsed.entries:
                            return feed_url
            except aiohttp.ClientError:
                continue

    return None


async def fetch_categories_from_database():
    """Fetch all categories from database."""
    log_message("Fetching categories from the database", level="info")

    async with get_db_connection() as db_connection:
        try:
            async with db_connection.cursor() as cursor:
                await cursor.execute("SELECT * FROM categories")
                categories = await cursor.fetchall()
        except Exception as e:
            log_message(f"Error fetching categories: {e}", level="error")
            stats["error_types"]["db_errors"] += 1
            return []

    # e.g. [(15, 'cl_general'), (194, 'as_general'), ...]
    category_list = [(row["id"], row["name"]) for row in categories]
    shuffle(category_list)

    log_message(f"Got {len(category_list)} categories from the database", level="success")
    return category_list


async def fetch_publishers_from_database(category_id: int):
    """Fetch publishers for a specific category."""

    async with get_db_connection() as db_connection:
        try:
            async with db_connection.cursor() as cursor:
                await cursor.execute(
                    "SELECT * FROM publishers WHERE category_id = %s",
                    (category_id,),
                )
                publishers = await cursor.fetchall()
        except Exception as e:
            log_message(f"Error fetching publishers: {e}", level="error")
            stats["error_types"]["db_errors"] += 1
            return []

    return publishers


async def process_category(session: aiohttp.ClientSession, category_id, category_name, category_index, total_categories, args=None):
    """
    Process a single category: fetch feeds from all publishers and save articles.
    Returns the number of articles saved.
    """
    if config.SEARCH_NEWS_DEBUG:
        if category_name != "br_general":
            return 0

    if shutdown_requested:
        return 0

    # Progress tracking
    percentage = (category_index / total_categories) * 100
    if not args or not args.quiet:
        log_message(f"[{round(percentage, 2)}%] Handling {category_name}...", level="info")

    publishers = await fetch_publishers_from_database(category_id)
    if not publishers:
        if not args or not args.quiet:
            log_message(f"No publishers for {category_name}", level="warning")
        return 0

    # Fetch all feeds concurrently using asyncio.gather with semaphore
    semaphore = asyncio.Semaphore(MAX_WORKERS)

    async def fetch_with_semaphore(publisher):
        async with semaphore:
            return await fetch_feed(session, publisher, category_name)

    tasks = [fetch_with_semaphore(publisher) for publisher in publishers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect successful results
    result_list = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            log_message(f"Exception for {publishers[i].get('name', 'unknown')}: {result}")
        elif result:
            result_list.append(result)

    # Merge all articles
    merged_articles = []
    for rss_data in result_list:
        if rss_data and "items" in rss_data:
            merged_articles.extend(rss_data["items"])

    if not merged_articles:
        if not args or not args.quiet:
            log_message(f"Empty cache: {category_name}", level="warning")
        stats["category_stats"][category_name] = {
            "articles": 0,
            "feeds_ok": len(result_list),
            "feeds_total": len(publishers),
            "errors": len(publishers) - len(result_list),
        }
        return 0

    # Pre-filter: check which URL hashes already exist
    url_hashes = [article["story_url_hash"] for article in merged_articles]
    existing_hashes = await get_existing_url_hashes(url_hashes)

    # Filter out already-existing articles
    new_articles = [
        article for article in merged_articles
        if article["story_url_hash"] not in existing_hashes
    ]

    skipped_count = len(merged_articles) - len(new_articles)
    if skipped_count > 0 and args and args.verbose:
        log_message(f"Skipped {skipped_count} existing articles for {category_name}", level="info")

    if not new_articles:
        if not args or not args.quiet:
            log_message(f"No new articles for {category_name}", level="info")
        stats["category_stats"][category_name] = {
            "articles": 0,
            "feeds_ok": len(result_list),
            "feeds_total": len(publishers),
            "errors": len(publishers) - len(result_list),
            "skipped": skipped_count,
        }
        return 0

    shuffle(new_articles)

    # Handle dry-run mode
    if args and args.dry_run:
        articles_saved = len(new_articles)
        exceptions_count = 0
        if args.verbose:
            log_message(f"[DRY RUN] Would save {articles_saved} articles for {category_name}", level="info")
    else:
        exceptions_count = await insert_stories_to_database(
            new_articles, category_name, category_id
        )
        articles_saved = len(new_articles) - exceptions_count

    # Track statistics
    stats["category_stats"][category_name] = {
        "articles": articles_saved,
        "feeds_ok": len(result_list),
        "feeds_total": len(publishers),
        "errors": len(publishers) - len(result_list),
        "skipped": skipped_count,
    }
    stats["total_articles"] += articles_saved

    if not args or not args.quiet:
        log_message(f"[{articles_saved} articles] Saved for {category_name}", level="success")

    return articles_saved


def display_summary(total_articles, execution_time, args):
    """Display a comprehensive summary table of the operation."""
    console.print("\n")

    # Summary title
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
    console.print("[bold cyan]                    EXECUTION SUMMARY[/bold cyan]")
    console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]\n")

    # Overall statistics
    table = Table(title="Overall Statistics", box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", width=30)
    table.add_column("Value", style="green", justify="right")

    table.add_row("Total Articles", str(total_articles))
    table.add_row("Total Categories", str(len(stats["category_stats"])))
    table.add_row("Execution Time", str(execution_time).split('.')[0])

    if total_articles > 0 and execution_time.total_seconds() > 0:
        rate = total_articles / execution_time.total_seconds()
        table.add_row("Articles/Second", f"{rate:.2f}")

    console.print(table)
    console.print()

    # Error summary (if any errors occurred)
    total_errors = sum(stats["error_types"].values())
    if total_errors > 0:
        error_table = Table(title="Error Summary", box=box.ROUNDED, show_header=True, header_style="bold red")
        error_table.add_column("Error Type", style="yellow")
        error_table.add_column("Count", style="red", justify="right")

        for error_type, count in stats["error_types"].items():
            if count > 0:
                error_table.add_row(error_type.replace("_", " ").title(), str(count))

        console.print(error_table)
        console.print()

    # Category breakdown (top 10 by article count)
    if stats["category_stats"] and not args.quiet:
        cat_table = Table(
            title="Top Categories by Articles",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold green",
        )
        cat_table.add_column("Category", style="cyan", width=20)
        cat_table.add_column("Articles", style="green", justify="right")
        cat_table.add_column("Feeds", style="blue", justify="center")
        cat_table.add_column("Errors", style="red", justify="right")

        # Sort by article count and show top 10
        sorted_cats = sorted(
            stats["category_stats"].items(),
            key=lambda x: x[1]["articles"],
            reverse=True,
        )[:10]

        for cat_name, cat_data in sorted_cats:
            cat_table.add_row(
                cat_name,
                str(cat_data["articles"]),
                f"{cat_data['feeds_ok']}/{cat_data['feeds_total']}",
                str(cat_data["errors"]),
            )

        console.print(cat_table)
        console.print()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="News RSS Feed Aggregator with parallel processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--categories",
        type=str,
        help="Comma-separated list of specific categories to process (e.g., 'tech,sports')",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=50,
        help="Maximum number of concurrent workers for fetching feeds (default: 50)",
    )

    parser.add_argument(
        "--category-workers",
        type=int,
        default=3,
        help="Number of categories to process in parallel (default: 3)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview mode - fetch feeds but don't save to database",
    )

    parser.add_argument(
        "--skip-prune",
        action="store_true",
        help="Skip pruning old stories at the end",
    )

    parser.add_argument(
        "--prune-days",
        type=int,
        default=7,
        help="Number of days to keep stories before pruning (default: 7)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output - only show summary",
    )

    return parser.parse_args()


def signal_handler(signum, frame):
    """Handle graceful shutdown on SIGINT/SIGTERM."""
    global shutdown_requested
    if not shutdown_requested:
        console.print("\n[yellow]⚠ Shutdown requested. Finishing current operations...[/yellow]")
        shutdown_requested = True
    else:
        console.print("\n[red]⚠ Force quit. Some operations may be incomplete.[/red]")
        sys.exit(1)


async def async_main():
    """Main async execution function with concurrent category processing."""
    global stats, MAX_WORKERS, REQUEST_TIMEOUT, process_pool, db_pool

    # Parse CLI arguments
    args = parse_arguments()

    # Update configuration from arguments
    MAX_WORKERS = args.workers
    REQUEST_TIMEOUT = args.timeout

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Track start time
    stats["start_time"] = datetime.now()

    # Initialize database pool
    await init_db_pool()
    log_message("Database connection pool initialized", level="success")

    # Initialize process pool for CPU-bound YAKE extraction
    process_pool = ProcessPoolExecutor(max_workers=4)

    try:
        categories = await fetch_categories_from_database()

        if not categories:
            log_message("No categories found!", level="error")
            return

        # Filter categories if specified
        if args.categories:
            category_filter = [c.strip() for c in args.categories.split(",")]
            categories = [(cid, cname) for cid, cname in categories if cname in category_filter]
            if not categories:
                log_message(f"No matching categories found for: {args.categories}", level="error")
                return
            log_message(f"Processing {len(categories)} filtered categories", level="info")

        if args.dry_run:
            console.print("[yellow]DRY RUN MODE - No data will be saved to database[/yellow]\n")

        total_articles_saved = 0

        # Create aiohttp session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=0,                 # No total limit (semaphore controls concurrency)
            limit_per_host=5,        # Per-host limit to avoid hammering single servers
            ttl_dns_cache=300,       # DNS cache TTL in seconds
            enable_cleanup_closed=True,
            force_close=False,       # Keep connections alive for reuse
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            # Process categories with progress tracking
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TextColumn("•"),
                TimeElapsedColumn(),
                console=console,
                transient=False,
            ) as progress:
                category_task = progress.add_task(
                    "[cyan]Processing categories...", total=len(categories)
                )

                # Process categories in batches for controlled concurrency
                category_semaphore = asyncio.Semaphore(args.category_workers)

                async def process_with_semaphore(cat_id, cat_name, idx):
                    async with category_semaphore:
                        if shutdown_requested:
                            return 0
                        return await process_category(
                            session, cat_id, cat_name, idx, len(categories), args
                        )

                # Create tasks for all categories
                tasks = [
                    process_with_semaphore(cat_id, cat_name, idx)
                    for idx, (cat_id, cat_name) in enumerate(categories)
                ]

                # Process and collect results as they complete
                for coro in asyncio.as_completed(tasks):
                    if shutdown_requested:
                        log_message("Shutdown in progress - cancelling remaining tasks", level="warning")
                        break

                    try:
                        articles_saved = await coro
                        total_articles_saved += articles_saved
                    except Exception as e:
                        log_message(f"Exception processing category: {e}", level="error")
                        stats["error_types"]["other"] += 1

                    progress.update(category_task, advance=1)

        # Calculate execution time
        execution_time = datetime.now() - stats["start_time"]

        # Display summary statistics
        display_summary(total_articles_saved, execution_time, args)

        # Auto-delete anything older than specified days
        if not args.skip_prune and not args.dry_run:
            console.print(f"\n[cyan]Pruning stories older than {args.prune_days} days...[/cyan]")
            await prune_old_stories(days=args.prune_days)

        log_message("Finished!", level="success")

    finally:
        # Cleanup
        if process_pool:
            process_pool.shutdown(wait=False)
        if db_pool:
            db_pool.close()
            await db_pool.wait_closed()


def main():
    """Entry point - runs the async main function."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
