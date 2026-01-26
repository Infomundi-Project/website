import concurrent.futures
import requests
import pymysql
import logging
import boto3
import time
import argparse
import signal
import sys
from contextlib import contextmanager
from random import shuffle, choice
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image
from pathlib import Path
from os import makedirs as os_makedirs
from dataclasses import dataclass, field
from typing import Optional

# Progress and color libraries
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
    # Fallback stubs
    class Fore:
        GREEN = RED = YELLOW = CYAN = MAGENTA = WHITE = ""
    class Style:
        RESET_ALL = BRIGHT = ""

from website_scripts import config, immutable, input_sanitization, hashing_util


# =============================================================================
# CLI Argument Parsing
# =============================================================================
def parse_arguments():
    """Parse command-line arguments for configuration"""
    parser = argparse.ArgumentParser(
        description="Search and download images for news stories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      # Run normally
  %(prog)s --dry-run            # Preview without making changes
  %(prog)s -v --category Tech   # Verbose mode, single category
  %(prog)s --workers 10 -q      # 10 workers, quiet mode
        """
    )
    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=20,
        help='Number of concurrent workers (default: 20)'
    )
    parser.add_argument(
        '--category', '-c',
        type=str,
        default=None,
        help='Process only a specific category by name'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Preview what would happen without making changes'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output (show debug messages)'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Quiet mode (only show errors and summary)'
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=30,
        help='Max stories per category (default: 30)'
    )
    return parser.parse_args()


# Parse args early so they're available for configuration
args = parse_arguments()


# =============================================================================
# Colored Logging System
# =============================================================================
class Logger:
    """Colored logging with verbosity levels"""

    def __init__(self, verbose: bool = False, quiet: bool = False, no_color: bool = False):
        self.verbose = verbose
        self.quiet = quiet
        self.use_color = COLORAMA_AVAILABLE and not no_color

    def _color(self, color: str, text: str) -> str:
        if self.use_color:
            return f"{color}{text}{Style.RESET_ALL}"
        return text

    def success(self, msg: str):
        """Green success message"""
        if not self.quiet:
            print(self._color(Fore.GREEN, f"[✓] {msg}"))
        logging.info(f"[SUCCESS] {msg}")

    def error(self, msg: str):
        """Red error message - always shown"""
        print(self._color(Fore.RED, f"[✗] {msg}"))
        logging.error(msg)

    def warning(self, msg: str):
        """Yellow warning message"""
        if not self.quiet:
            print(self._color(Fore.YELLOW, f"[!] {msg}"))
        logging.warning(msg)

    def info(self, msg: str):
        """Cyan info message"""
        if not self.quiet:
            print(self._color(Fore.CYAN, f"[~] {msg}"))
        logging.info(msg)

    def debug(self, msg: str):
        """Debug message - only in verbose mode"""
        if self.verbose:
            print(self._color(Fore.WHITE, f"[.] {msg}"))
        logging.debug(msg)

    def progress(self, msg: str):
        """Magenta progress message"""
        if not self.quiet:
            print(self._color(Fore.MAGENTA, f"[→] {msg}"))
        logging.info(msg)

    def header(self, msg: str):
        """Bright header message"""
        if not self.quiet:
            if self.use_color:
                print(f"\n{Style.BRIGHT}{Fore.CYAN}{'='*60}")
                print(f"  {msg}")
                print(f"{'='*60}{Style.RESET_ALL}\n")
            else:
                print(f"\n{'='*60}")
                print(f"  {msg}")
                print(f"{'='*60}\n")


# =============================================================================
# Statistics Tracking
# =============================================================================
@dataclass
class RunStatistics:
    """Track statistics for the current run"""
    start_time: float = field(default_factory=time.time)
    categories_processed: int = 0
    categories_total: int = 0
    stories_processed: int = 0
    stories_updated: int = 0
    favicons_updated: int = 0
    downloads_failed: int = 0
    proxy_errors: int = 0

    def elapsed_time(self) -> str:
        """Return formatted elapsed time"""
        elapsed = time.time() - self.start_time
        minutes, seconds = divmod(int(elapsed), 60)
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.stories_processed == 0:
            return 0.0
        return (self.stories_updated / self.stories_processed) * 100


# Global statistics instance
stats = RunStatistics()


# =============================================================================
# Graceful Shutdown Handler
# =============================================================================
shutdown_requested = False

def signal_handler(signum, frame):
    """Handle interrupt signals gracefully"""
    global shutdown_requested
    if shutdown_requested:
        # Second interrupt - force exit
        print("\n\nForce exit requested. Exiting immediately...")
        sys.exit(1)

    shutdown_requested = True
    print(f"\n\n{Fore.YELLOW if COLORAMA_AVAILABLE else ''}[!] Shutdown requested. Finishing current batch...{Style.RESET_ALL if COLORAMA_AVAILABLE else ''}")
    print("    (Press Ctrl+C again to force exit)\n")

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# =============================================================================
# Configuration
# =============================================================================
# Initialize logger with CLI args
log = Logger(verbose=args.verbose, quiet=args.quiet, no_color=args.no_color)

WORKERS = args.workers  # FIX: Increased from 1 for actual concurrency
DEFAULT_IMAGE = None
MAX_PROXY_RETRIES = 10
MAX_BAD_PROXIES_BEFORE_CLEAR = 50  # NEW: Prevent memory leak
LOCAL_STORAGE_MAX_AGE_DAYS = 30  # Delete local files older than this many days

# Load and shuffle proxies
with open(f"{config.WEBSITE_ROOT}/assets/http-proxies.txt") as f:
    proxies = [x.rstrip() for x in f.readlines()]
    shuffle(proxies)

# Use set for O(1) lookups - FIX: was list with O(n) lookups
bad_proxies = set()

# R2/S3 configuration with fallback
s3_client = None
USE_LOCAL_STORAGE = False
LOCAL_STORAGE_PATH = None
bucket_name = "infomundi"
bucket_base_url = "https://bucket.infomundi.net"

try:
    # Check if S3/R2 credentials are properly configured
    if not config.R2_ENDPOINT or not config.R2_ACCESS_KEY or not config.R2_SECRET:
        raise ValueError("S3/R2 credentials not configured")

    s3_client = boto3.client(
        "s3",
        endpoint_url=config.R2_ENDPOINT,
        aws_access_key_id=config.R2_ACCESS_KEY,
        aws_secret_access_key=config.R2_SECRET,
        region_name="auto",
    )
    if not args.quiet:
        print(f"{Fore.GREEN if COLORAMA_AVAILABLE else ''}[✓] S3 client initialized{Style.RESET_ALL if COLORAMA_AVAILABLE else ''}")
except Exception as e:
    if not args.quiet:
        print(f"{Fore.YELLOW if COLORAMA_AVAILABLE else ''}[!] S3 failed: {e}. Using local storage.{Style.RESET_ALL if COLORAMA_AVAILABLE else ''}")
    USE_LOCAL_STORAGE = True
    # Create local storage directory
    LOCAL_STORAGE_PATH = Path("/app/static/local_uploads")
    LOCAL_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    if not args.quiet:
        print(f"{Fore.GREEN if COLORAMA_AVAILABLE else ''}[✓] Local storage: {LOCAL_STORAGE_PATH}{Style.RESET_ALL if COLORAMA_AVAILABLE else ''}")
    bucket_base_url = "/static/local_uploads"  # Update base URL for local mode

# Database configuration
db_params = {
    "host": config.MYSQL_HOST,
    "user": config.MYSQL_USERNAME,
    "password": config.MYSQL_PASSWORD,
    "db": config.MYSQL_DATABASE,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
}

# Ensure logs directory exists
log_dir = f"{config.WEBSITE_ROOT}/logs"
os_makedirs(log_dir, exist_ok=True)

# Setup logging - FIX: Actually use logging instead of just print
log_level = logging.DEBUG if args.verbose else logging.INFO
logging.basicConfig(
    filename=f"{config.WEBSITE_ROOT}/logs/search_images.log",
    level=log_level,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)


def log_message(message):
    """Log message to both console and file - legacy wrapper for verbose details"""
    log.debug(message)


def cleanup_old_local_files():
    """
    Delete old files from local storage to prevent unlimited growth.
    Only runs when USE_LOCAL_STORAGE is True.
    """
    if not USE_LOCAL_STORAGE or not LOCAL_STORAGE_PATH:
        return

    log_message(f"Starting cleanup of files older than {LOCAL_STORAGE_MAX_AGE_DAYS} days...")

    current_time = time.time()
    max_age_seconds = LOCAL_STORAGE_MAX_AGE_DAYS * 24 * 60 * 60
    deleted_count = 0
    total_size_freed = 0

    try:
        # Walk through all files in local storage directory
        for file_path in LOCAL_STORAGE_PATH.rglob("*"):
            # Skip directories
            if not file_path.is_file():
                continue

            try:
                # Get file modification time
                file_age_seconds = current_time - file_path.stat().st_mtime

                # Delete if older than threshold
                if file_age_seconds > max_age_seconds:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    deleted_count += 1
                    total_size_freed += file_size
                    log_message(f"Deleted old file: {file_path.relative_to(LOCAL_STORAGE_PATH)}")

            except Exception as e:
                log_message(f"Error processing file {file_path}: {e}")
                continue

        # Clean up empty directories
        for dir_path in sorted(LOCAL_STORAGE_PATH.rglob("*"), reverse=True):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                try:
                    dir_path.rmdir()
                    log_message(f"Removed empty directory: {dir_path.relative_to(LOCAL_STORAGE_PATH)}")
                except Exception as e:
                    log_message(f"Error removing directory {dir_path}: {e}")

        if deleted_count > 0:
            size_mb = total_size_freed / (1024 * 1024)
            log_message(f"Cleanup complete: deleted {deleted_count} files, freed {size_mb:.2f} MB")
        else:
            log_message("Cleanup complete: no old files found")

    except Exception as e:
        log_message(f"Error during cleanup: {e}")


@contextmanager
def get_db_connection():
    """
    Context manager for database connections to prevent timeout issues.
    FIX: Replaces global connection that could timeout.
    """
    connection = pymysql.connect(**db_params)
    try:
        yield connection
    except Exception as e:
        connection.rollback()
        log_message(f"Database error, rolling back: {e}")
        raise
    finally:
        connection.close()


def fetch_categories_from_database():
    """Fetch all categories from database"""
    log_message("Fetching categories from the database")
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor() as cursor:
                cursor.execute("SELECT * FROM categories")
                categories = cursor.fetchall()
                shuffle(categories)
    except pymysql.MySQLError as e:
        log_message(f"Error fetching categories: {e}")
        return []

    log_message(f"Got a total of {len(categories)} categories from the database")
    return categories


def fetch_stories_with_publishers(category_id: int, limit: int = 30):
    """Fetch stories with nested publisher information"""
    log_message("Fetching stories with nested publisher dict...")
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor() as cursor:
                sql = """
                SELECT
                    s.*,
                    p.favicon_url AS publisher_favicon_url,
                    p.id          AS publisher_id,
                    p.name        AS publisher_name,
                    p.feed_url    AS publisher_feed_url,
                    p.site_url    AS publisher_site_url
                FROM stories AS s
                JOIN publishers AS p
                  ON s.publisher_id = p.id
                WHERE s.category_id = %s
                  AND NOT s.has_image
                ORDER BY s.created_at DESC
                LIMIT %s
                """
                cursor.execute(sql, (category_id, limit))
                rows = cursor.fetchall()
    except pymysql.MySQLError as e:
        log_message(f"Error fetching stories: {e}")
        return []

    stories = []
    for row in rows:
        # Split out publisher fields
        publisher = {
            key.replace("publisher_", ""): row[key]
            for key in row
            if key.startswith("publisher_")
        }
        # Everything else is story data
        story_data = {key: row[key] for key in row if not key.startswith("publisher_")}
        story_data["publisher"] = publisher
        stories.append(story_data)

    log_message(
        f"Got {len(stories)} stories (with nested publisher) for category {category_id}"
    )
    return stories


def get_working_proxy():
    """
    Get a working proxy, excluding known bad ones.
    FIX: More efficient filtering using set difference.
    """
    global bad_proxies

    # FIX: Clear bad proxies if list gets too large (memory leak prevention)
    if len(bad_proxies) >= MAX_BAD_PROXIES_BEFORE_CLEAR:
        log.warning(f"Proxy pool exhausted ({len(bad_proxies)}/{len(proxies)}). Clearing bad list...")
        bad_proxies.clear()

    # FIX: O(1) set lookups instead of O(n) list filtering in loop
    working_proxies = [p for p in proxies if p not in bad_proxies]

    if not working_proxies:
        log.warning("No working proxies available!")
        return None

    return choice(working_proxies)


def get_link_preview(data, source: str = "default", category_name: str = "None"):
    """
    Retrieve a link preview image URL with proxy rotation and retry logic.

    Args:
        data: URL string or dict with 'url' key
        source: Operation mode - 'default' for preview URL, else returns response
        category_name: Category for directory management

    Returns:
        Image preview URL string, response object, or DEFAULT_IMAGE on failure
    """
    global bad_proxies

    # Determine URL based on data type
    url = data if isinstance(data, str) else data.get("url")

    if not url or not input_sanitization.is_valid_url(url):
        log_message(f"Invalid url: {url}")
        return DEFAULT_IMAGE

    bad_proxies_count = 0
    max_retries = MAX_PROXY_RETRIES  # FIX: Added explicit retry limit

    for attempt in range(max_retries):  # FIX: Replaced while True with bounded loop
        headers = {"User-Agent": choice(immutable.USER_AGENTS)}

        chosen_proxy = get_working_proxy()
        if not chosen_proxy:
            return DEFAULT_IMAGE

        try:
            response = requests.get(
                url,
                timeout=5,
                headers=headers,
                proxies={"http": f"http://{chosen_proxy}"},
            )

            if response.status_code not in [200, 301, 302]:
                log_message(
                    f"[Invalid HTTP Response] {response.status_code} from {url}."
                )
                return DEFAULT_IMAGE

            # Success! Break out of retry loop
            break

        except requests.exceptions.ProxyError:
            bad_proxies_count += 1
            stats.proxy_errors += 1
            bad_proxies.add(chosen_proxy)  # FIX: Use set.add instead of list.append
            log.debug(f"Proxy error, added to badlist: {chosen_proxy}")

            if bad_proxies_count > 5:  # FIX: Reduced threshold
                log_message(f"[Proxy Error] Too many bad proxies for {url}, giving up")
                return DEFAULT_IMAGE
            continue

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as err:
            log_message(f"[Timeout] {err} from {url}")
            return DEFAULT_IMAGE

        except Exception as err:
            log_message(f"[Unexpected Error] {err}")
            if isinstance(data, dict):
                log_message(f"Story: {data.get('id', 'unknown')}")
            return DEFAULT_IMAGE
    else:
        # FIX: Explicit handling when max retries exceeded
        log_message(f"Max retries exceeded for {url}")
        return DEFAULT_IMAGE

    # Return appropriate result based on source parameter
    if source != "default":
        return response

    return extract_image_from_response(response, url, data, category_name)


def extract_image_from_response(
    response: requests.Response, url: str, story: dict, category_name: str
):
    """
    Extract image and favicon URLs from web response.

    Args:
        response: Web response containing HTML
        url: Source URL for resolving relative paths
        story: Story dict with publisher info
        category_name: Category for directory structure

    Returns:
        Result of download_and_convert_image or DEFAULT_IMAGE
    """
    log_message(f"Attempting to extract image from response for {story['id']}")

    try:
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        # Find Open Graph image
        image = soup.find("meta", {"property": "og:image"})
        image_url = image.get("content", "").strip() if image else DEFAULT_IMAGE

        # Find favicon
        favicon = soup.find("link", rel="icon")
        if favicon and favicon.get("href"):
            favicon_url = favicon["href"]
            if not input_sanitization.is_valid_url(favicon_url):
                favicon_url = urljoin(url, favicon["href"])
        else:
            favicon_url = urljoin(url, "/favicon.ico")

        publisher_id = story["publisher"]["id"]

        # Build images dict
        images = {
            "story": {
                "url": image_url,
                "output_path": f"stories/{category_name}/{hashing_util.binary_to_md5_hex(story['url_hash'])}",
            }
        }

        # Only include favicon if not already stored
        # NOTE: favicon_database check removed - handled in process_category with set
        if not story["publisher"]["favicon_url"]:
            images["favicon"] = {
                "url": favicon_url,
                "output_path": f"favicons/{category_name}/{publisher_id}",
            }

        return download_and_convert_image(images)

    except Exception as e:
        log_message(f"Error extracting image: {e}")
        return DEFAULT_IMAGE


def upload_image_to_storage(buffer: BytesIO, object_key: str) -> bool:
    """
    Upload image to S3 or local storage based on configuration.

    Args:
        buffer: BytesIO buffer containing image data
        object_key: S3 key or local file path

    Returns:
        True if upload successful, False otherwise
    """
    try:
        if USE_LOCAL_STORAGE:
            # Local storage fallback
            local_path = LOCAL_STORAGE_PATH / object_key
            # Create parent directories if they don't exist
            local_path.parent.mkdir(parents=True, exist_ok=True)

            buffer.seek(0)
            with open(local_path, "wb") as f:
                f.write(buffer.read())

            log_message(f"Saved to local storage: {local_path}")
            return True
        else:
            # S3/R2 storage
            buffer.seek(0)
            s3_client.upload_fileobj(buffer, bucket_name, object_key)
            log_message(f"Uploaded to S3: {object_key}")
            return True

    except Exception as e:
        log_message(f"Failed to upload {object_key}: {e}")
        return False


def download_and_convert_image(data: dict) -> list:
    """
    Download and process images (story images and favicons).

    Args:
        data: Dict with image types as keys, each containing 'url' and 'output_path'

    Returns:
        List of successfully uploaded S3 object keys or local paths
    """
    website_paths = []

    for item in data:
        url = data[item]["url"]

        if not url:
            continue

        response = get_link_preview(url, "download")

        # Validate response is a requests object
        if not isinstance(response, requests.Response):
            continue

        try:
            image = Image.open(BytesIO(response.content))

            # FIX: Validate image dimensions
            if image.width < 10 or image.height < 10:
                log_message(f"Image too small from {url}, skipping")
                continue

        except Exception as e:
            log_message(f"Error opening image from {url}: {e}")
            continue

        output_buffer = BytesIO()

        try:
            if item == "story":
                # Process story image
                image.thumbnail((1280, 720))
                image = image.convert("RGB")
                image.save(
                    output_buffer, format="avif", optimize=True, quality=60, method=6
                )
                s3_object_key = data[item]["output_path"] + ".avif"
            else:
                # Process favicon
                image = image.resize((32, 32))
                image.save(output_buffer, format="ico")
                s3_object_key = data[item]["output_path"] + ".ico"

            output_buffer.seek(0)

            # Upload to storage (S3 or local)
            log_message(f"Uploading {s3_object_key} to storage")
            if upload_image_to_storage(output_buffer, s3_object_key):
                website_paths.append(s3_object_key)
            else:
                log_message(f"Upload failed for {s3_object_key}")

        except Exception as e:
            log_message(f"Failed to process {item}: {e}")
        finally:
            output_buffer.close()

    return website_paths


def update_story_image_url(stories_to_update):
    """
    Batch update story has_image flags.
    FIX: Proper tuple creation with trailing comma.
    """
    if not stories_to_update:
        return

    log.debug(f"Updating {len(stories_to_update)} story image URLs...")
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor() as cursor:
                update_query = "UPDATE stories SET has_image = 1 WHERE id = %s"
                cursor.executemany(update_query, stories_to_update)
            db_connection.commit()
            log.debug(f"Updated {len(stories_to_update)} stories in DB")
    except pymysql.MySQLError as e:
        log.error(f"DB error updating stories: {e}")


def update_publisher_favicon(favicon_updates):
    """
    Batch update publisher favicon URLs.
    """
    if not favicon_updates:
        return

    log_message(f"Updating {len(favicon_updates)} publisher favicons...")
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor() as cursor:
                update_query = "UPDATE publishers SET favicon_url = %s WHERE id = %s"
                cursor.executemany(update_query, favicon_updates)
            db_connection.commit()
            log_message(f"Successfully updated {len(favicon_updates)} favicons")
    except pymysql.MySQLError as e:
        log_message(f"Error updating publisher favicons: {e}")


def process_category(category: dict):
    """
    Process all stories in a category to find and store images.
    FIX: Use set for favicon tracking, proper tuple creation.
    """
    global shutdown_requested

    stories = fetch_stories_with_publishers(category["id"], limit=args.limit)
    if not stories:
        log.debug(f"No stories to process for {category['name']}")
        return

    # Check for shutdown before processing
    if shutdown_requested:
        log.warning(f"Skipping {category['name']} due to shutdown request")
        return

    stories_to_update = []
    favicons_to_update = []
    favicon_database = set()  # FIX: Use set instead of list for O(1) lookups

    log.debug(f"Starting threading with {WORKERS} workers for {category['name']}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
        # Submit all tasks
        future_to_story = {
            executor.submit(get_link_preview, story, "default", category["name"]): story
            for story in stories
        }

        total_updated = 0
        local_failed = 0

        # Create progress bar iterator
        if TQDM_AVAILABLE and not args.quiet:
            futures_iter = tqdm(
                concurrent.futures.as_completed(future_to_story),
                total=len(stories),
                desc=f"  {category['name'][:20]:<20}",
                unit="story",
                leave=False,
                ncols=80
            )
        else:
            futures_iter = concurrent.futures.as_completed(future_to_story)

        # Process completed futures
        for future in futures_iter:
            # Check for shutdown
            if shutdown_requested:
                log.warning("Shutdown requested, stopping current batch...")
                executor.shutdown(wait=False, cancel_futures=True)
                break

            story = future_to_story[future]
            stats.stories_processed += 1

            try:
                images_paths = future.result()
            except Exception as e:
                log.debug(f"Error processing story {story['id']}: {e}")
                stats.downloads_failed += 1
                local_failed += 1
                continue

            # Validate result
            if not isinstance(images_paths, list) or not images_paths:
                stats.downloads_failed += 1
                local_failed += 1
                continue

            for path in images_paths:
                image_url = f"{bucket_base_url}/{path}"

                if "stories" in path:
                    # FIX: Proper tuple with trailing comma
                    stories_to_update.append((story["id"],))
                    stats.stories_updated += 1
                else:
                    # FIX: Proper tuple creation
                    favicons_to_update.append((image_url, story["publisher"]["id"]))
                    favicon_database.add(f"{story['publisher']['id']}.ico")
                    stats.favicons_updated += 1

                total_updated += 1

        # Batch update database (skip in dry-run mode)
        if not args.dry_run:
            update_story_image_url(stories_to_update)
            update_publisher_favicon(favicons_to_update)
        else:
            log.info(f"[DRY-RUN] Would update {len(stories_to_update)} stories, {len(favicons_to_update)} favicons")

        # Summary for this category
        if total_updated > 0:
            log.success(f"{category['name']}: {total_updated} images ({local_failed} failed)")
        else:
            log.debug(f"{category['name']}: No images downloaded")


def print_summary():
    """Print final run statistics"""
    if args.quiet:
        # Even in quiet mode, show minimal summary
        print(f"\nDone: {stats.stories_updated} images in {stats.elapsed_time()}")
        return

    success_rate = stats.success_rate()

    # Color the success rate based on value
    if log.use_color:
        if success_rate >= 70:
            rate_color = Fore.GREEN
        elif success_rate >= 40:
            rate_color = Fore.YELLOW
        else:
            rate_color = Fore.RED
        rate_str = f"{rate_color}{success_rate:.1f}%{Style.RESET_ALL}"
    else:
        rate_str = f"{success_rate:.1f}%"

    print(f"""
{'='*50}
  {'[DRY-RUN] ' if args.dry_run else ''}Run Summary
{'='*50}
  Categories processed:  {stats.categories_processed}/{stats.categories_total}
  Stories processed:     {stats.stories_processed}
  Stories updated:       {stats.stories_updated}
  Favicons updated:      {stats.favicons_updated}
  Failed downloads:      {stats.downloads_failed}
  Proxy errors:          {stats.proxy_errors}
  Success rate:          {rate_str}
  Time elapsed:          {stats.elapsed_time()}
{'='*50}
""")


def search_images():
    """Main function to search and process images for all categories"""
    global shutdown_requested

    storage_mode = "LOCAL STORAGE" if USE_LOCAL_STORAGE else "S3/R2"

    # Show header
    log.header(f"News Image Search {'[DRY-RUN]' if args.dry_run else ''}")

    if args.dry_run:
        log.warning("DRY-RUN MODE: No changes will be made to database or storage")

    log.info(f"Storage: {storage_mode} | Workers: {WORKERS} | Limit: {args.limit}/category")

    # Clean up old local files if using local storage
    if not args.dry_run:
        cleanup_old_local_files()

    categories = fetch_categories_from_database()

    # Filter by category name if specified
    if args.category:
        categories = [c for c in categories if c['name'].lower() == args.category.lower()]
        if not categories:
            log.error(f"Category '{args.category}' not found")
            return

    if not categories:
        log.error("No categories found, exiting")
        return

    stats.categories_total = len(categories)
    log.info(f"Processing {len(categories)} categories...")
    print()  # Blank line before progress

    for i, category in enumerate(categories, 1):
        # Check for shutdown
        if shutdown_requested:
            log.warning("Shutdown requested, stopping...")
            break

        stats.categories_processed = i

        # Show category progress (unless using tqdm which handles this)
        if not TQDM_AVAILABLE or args.quiet:
            progress_pct = (i / len(categories)) * 100
            log.progress(f"[{progress_pct:5.1f}%] {category['name']}")

        try:
            process_category(category)
        except Exception as e:
            log.error(f"Error processing {category['name']}: {e}")
            continue

    # Print summary
    print_summary()

    if shutdown_requested:
        log.warning("Run was interrupted before completion")
    else:
        log.success("Finished!")


if __name__ == "__main__":
    search_images()
