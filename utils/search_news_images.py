import asyncio
import aiohttp
import aiomysql
import logging
import boto3
import time
import argparse
import signal
import sys
from contextlib import asynccontextmanager
from random import shuffle, choice
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image
from pathlib import Path
from os import makedirs as os_makedirs
from dataclasses import dataclass, field
from typing import Optional, Set, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

# Progress and color libraries
try:
    from tqdm import tqdm
    from tqdm.asyncio import tqdm as async_tqdm
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
        default=50,
        help='Number of concurrent workers (default: 50)'
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
    parser.add_argument(
        '--timeout', '-t',
        type=float,
        default=10.0,
        help='Request timeout in seconds (default: 10.0)'
    )
    parser.add_argument(
        '--connect-timeout',
        type=float,
        default=5.0,
        help='Connection timeout in seconds (default: 5.0)'
    )
    parser.add_argument(
        '--no-proxy',
        action='store_true',
        help='Disable proxy usage (connect directly)'
    )
    parser.add_argument(
        '--proxy-file',
        type=str,
        default=None,
        help='Path to custom proxy file (one proxy per line, format: host:port)'
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
    head_request_skips: int = 0

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

WORKERS = args.workers
DEFAULT_IMAGE = None
MAX_PROXY_RETRIES = 10
MAX_BAD_PROXIES_BEFORE_CLEAR = 50
LOCAL_STORAGE_MAX_AGE_DAYS = 30
REQUEST_TIMEOUT = args.timeout
CONNECT_TIMEOUT = args.connect_timeout

# Load and shuffle proxies (if not disabled)
USE_PROXIES = not args.no_proxy
all_proxies = []

if USE_PROXIES:
    # Determine proxy file path
    if args.proxy_file:
        proxy_file_path = args.proxy_file
    else:
        proxy_file_path = f"{config.WEBSITE_ROOT}/assets/http-proxies.txt"

    try:
        with open(proxy_file_path) as f:
            all_proxies = [x.rstrip() for x in f.readlines() if x.strip()]
            shuffle(all_proxies)
        if not args.quiet:
            print(f"{Fore.GREEN if COLORAMA_AVAILABLE else ''}[✓] Loaded {len(all_proxies)} proxies from {proxy_file_path}{Style.RESET_ALL if COLORAMA_AVAILABLE else ''}")
    except FileNotFoundError:
        print(f"{Fore.RED if COLORAMA_AVAILABLE else ''}[✗] Proxy file not found: {proxy_file_path}{Style.RESET_ALL if COLORAMA_AVAILABLE else ''}")
        print(f"    Please ensure the file exists or use --no-proxy to connect directly.")
        sys.exit(1)
    except Exception as e:
        print(f"{Fore.RED if COLORAMA_AVAILABLE else ''}[✗] Error loading proxies: {e}{Style.RESET_ALL if COLORAMA_AVAILABLE else ''}")
        sys.exit(1)
else:
    if not args.quiet:
        print(f"{Fore.YELLOW if COLORAMA_AVAILABLE else ''}[!] Proxy usage disabled - connecting directly{Style.RESET_ALL if COLORAMA_AVAILABLE else ''}")

# Proxy management with pre-filtered sets for O(1) operations
bad_proxies: Set[str] = set()
working_proxies: Set[str] = set(all_proxies)

# R2/S3 configuration with fallback
s3_client = None
USE_LOCAL_STORAGE = False
LOCAL_STORAGE_PATH = None
bucket_name = "infomundi"
bucket_base_url = "https://bucket.infomundi.net"

# Thread pool for CPU-bound image processing (PIL operations)
image_executor = ThreadPoolExecutor(max_workers=min(8, (WORKERS // 4) or 2))

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

# Database configuration for aiomysql pool
db_params = {
    "host": config.MYSQL_HOST,
    "user": config.MYSQL_USERNAME,
    "password": config.MYSQL_PASSWORD,
    "db": config.MYSQL_DATABASE,
    "charset": "utf8mb4",
    "autocommit": False,
    "minsize": 2,
    "maxsize": 10,
}

# Global database pool (initialized in main)
db_pool: Optional[aiomysql.Pool] = None

# Ensure logs directory exists
log_dir = f"{config.WEBSITE_ROOT}/logs"
os_makedirs(log_dir, exist_ok=True)

# Setup logging
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


async def init_db_pool():
    """Initialize the async database connection pool"""
    global db_pool
    db_pool = await aiomysql.create_pool(
        host=db_params["host"],
        user=db_params["user"],
        password=db_params["password"],
        db=db_params["db"],
        charset=db_params["charset"],
        autocommit=db_params["autocommit"],
        minsize=db_params["minsize"],
        maxsize=db_params["maxsize"],
        cursorclass=aiomysql.DictCursor,
    )
    log.debug("Database connection pool initialized")


async def close_db_pool():
    """Close the database connection pool"""
    global db_pool
    if db_pool:
        db_pool.close()
        await db_pool.wait_closed()
        log.debug("Database connection pool closed")


@asynccontextmanager
async def get_db_connection():
    """
    Async context manager for database connections from pool.
    """
    async with db_pool.acquire() as connection:
        try:
            yield connection
        except Exception as e:
            await connection.rollback()
            log_message(f"Database error, rolling back: {e}")
            raise


async def fetch_categories_from_database() -> List[Dict]:
    """Fetch all categories from database"""
    log_message("Fetching categories from the database")
    try:
        async with get_db_connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT * FROM categories")
                categories = await cursor.fetchall()
                categories = list(categories)
                shuffle(categories)
    except Exception as e:
        log_message(f"Error fetching categories: {e}")
        return []

    log_message(f"Got a total of {len(categories)} categories from the database")
    return categories


async def fetch_stories_with_publishers(category_id: int, limit: int = 30) -> List[Dict]:
    """Fetch stories with nested publisher information"""
    log_message("Fetching stories with nested publisher dict...")
    try:
        async with get_db_connection() as connection:
            async with connection.cursor() as cursor:
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
                await cursor.execute(sql, (category_id, limit))
                rows = await cursor.fetchall()
    except Exception as e:
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


def get_working_proxy() -> Optional[str]:
    """
    Get a working proxy using pre-filtered sets for O(1) operations.
    Returns None if proxies are disabled.
    """
    global bad_proxies, working_proxies

    # Return None if proxies are disabled
    if not USE_PROXIES:
        return None

    # Clear and reset if pool exhausted
    if len(bad_proxies) >= MAX_BAD_PROXIES_BEFORE_CLEAR or not working_proxies:
        log.warning(f"Proxy pool exhausted ({len(bad_proxies)}/{len(all_proxies)}). Resetting...")
        bad_proxies.clear()
        working_proxies = set(all_proxies)

    if not working_proxies:
        log.warning("No working proxies available!")
        return None

    return choice(tuple(working_proxies))


def mark_proxy_bad(proxy: str):
    """Mark a proxy as bad and remove from working set"""
    global bad_proxies, working_proxies
    bad_proxies.add(proxy)
    working_proxies.discard(proxy)
    stats.proxy_errors += 1


async def check_content_type(session: aiohttp.ClientSession, url: str, proxy: Optional[str]) -> bool:
    """
    Perform HEAD request to validate content-type before downloading.
    Returns True if the URL appears to be an image or HTML page.
    """
    try:
        timeout = aiohttp.ClientTimeout(total=CONNECT_TIMEOUT)
        kwargs = {
            "timeout": timeout,
            "allow_redirects": True
        }
        if proxy:
            kwargs["proxy"] = f"http://{proxy}"

        async with session.head(url, **kwargs) as response:
            content_type = response.headers.get('Content-Type', '').lower()
            # Accept images and HTML (for scraping og:image)
            if any(t in content_type for t in ['image/', 'text/html', 'application/xhtml']):
                return True
            log_message(f"Skipping non-image/html content-type: {content_type} for {url}")
            stats.head_request_skips += 1
            return False
    except Exception:
        # If HEAD fails, proceed with GET anyway
        return True


async def get_link_preview(
    session: aiohttp.ClientSession,
    data: Any,
    source: str = "default",
    category_name: str = "None"
) -> Any:
    """
    Retrieve a link preview image URL with proxy rotation and retry logic.
    Async implementation using aiohttp.

    Args:
        session: aiohttp ClientSession for connection reuse
        data: URL string or dict with 'url' key
        source: Operation mode - 'default' for preview URL, else returns response bytes
        category_name: Category for directory management

    Returns:
        Image preview URL string, response bytes, or DEFAULT_IMAGE on failure
    """
    # Determine URL based on data type
    url = data if isinstance(data, str) else data.get("url")

    if not url or not input_sanitization.is_valid_url(url):
        log_message(f"Invalid url: {url}")
        return DEFAULT_IMAGE

    bad_proxies_count = 0
    max_retries = MAX_PROXY_RETRIES

    for attempt in range(max_retries):
        headers = {"User-Agent": choice(immutable.USER_AGENTS)}

        chosen_proxy = get_working_proxy()
        # If proxies are disabled, chosen_proxy will be None
        # If proxies are enabled but exhausted, return error
        if USE_PROXIES and not chosen_proxy:
            return DEFAULT_IMAGE

        try:
            # Validate content-type with HEAD request first (for download mode)
            if source != "default":
                is_valid = await check_content_type(session, url, chosen_proxy)
                if not is_valid:
                    return DEFAULT_IMAGE

            timeout = aiohttp.ClientTimeout(
                total=REQUEST_TIMEOUT,
                connect=CONNECT_TIMEOUT
            )

            kwargs = {
                "headers": headers,
                "timeout": timeout,
                "allow_redirects": True
            }
            if chosen_proxy:
                kwargs["proxy"] = f"http://{chosen_proxy}"

            async with session.get(url, **kwargs) as response:
                if response.status != 200:
                    log_message(f"[Invalid HTTP Response] {response.status} from {url}.")
                    return DEFAULT_IMAGE

                # For download mode, return the response content
                if source != "default":
                    content = await response.read()
                    return content

                # For default mode, parse HTML for og:image
                html_content = await response.text()
                return await extract_image_from_response(
                    session, html_content, url, data, category_name
                )

        except aiohttp.ClientProxyConnectionError:
            # Only retry with different proxy if proxies are enabled
            if USE_PROXIES and chosen_proxy:
                bad_proxies_count += 1
                mark_proxy_bad(chosen_proxy)
                log.debug(f"Proxy error, added to badlist: {chosen_proxy}")

                if bad_proxies_count > 5:
                    log_message(f"[Proxy Error] Too many bad proxies for {url}, giving up")
                    return DEFAULT_IMAGE
                continue
            else:
                # If not using proxies, this shouldn't happen, but handle it
                log_message(f"[Proxy Error] Unexpected proxy error from {url}")
                return DEFAULT_IMAGE

        except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as err:
            log_message(f"[Timeout/Connection] {err} from {url}")
            # Don't retry on connection errors if not using proxies
            if not USE_PROXIES:
                return DEFAULT_IMAGE
            # With proxies, try a different one
            if chosen_proxy:
                mark_proxy_bad(chosen_proxy)
            continue

        except Exception as err:
            log_message(f"[Unexpected Error] {err}")
            if isinstance(data, dict):
                log_message(f"Story: {data.get('id', 'unknown')}")
            return DEFAULT_IMAGE

    # Max retries exceeded
    log_message(f"Max retries exceeded for {url}")
    return DEFAULT_IMAGE


async def extract_image_from_response(
    session: aiohttp.ClientSession,
    html_content: str,
    url: str,
    story: dict,
    category_name: str
) -> Any:
    """
    Extract image and favicon URLs from HTML content.
    Uses lxml parser for better performance.

    Args:
        session: aiohttp session for downloading images
        html_content: HTML string to parse
        url: Source URL for resolving relative paths
        story: Story dict with publisher info
        category_name: Category for directory structure

    Returns:
        Result of download_and_convert_image or DEFAULT_IMAGE
    """
    log_message(f"Attempting to extract image from response for {story['id']}")

    try:
        # Use lxml parser for better performance (2-5x faster than html.parser)
        soup = BeautifulSoup(html_content, "lxml")

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
        if not story["publisher"]["favicon_url"]:
            images["favicon"] = {
                "url": favicon_url,
                "output_path": f"favicons/{category_name}/{publisher_id}",
            }

        return await download_and_convert_image(session, images)

    except Exception as e:
        log_message(f"Error extracting image: {e}")
        return DEFAULT_IMAGE


def process_image_sync(content: bytes, item_type: str, output_path: str) -> Optional[tuple]:
    """
    CPU-bound image processing - runs in thread pool.
    Returns (buffer, s3_object_key) or None on failure.
    """
    try:
        image = Image.open(BytesIO(content))

        # Validate image dimensions
        if image.width < 10 or image.height < 10:
            log_message(f"Image too small ({image.width}x{image.height}), skipping")
            return None

        output_buffer = BytesIO()

        if item_type == "story":
            # Process story image - optimize memory by checking mode first
            image.thumbnail((1280, 720))
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(
                output_buffer, format="AVIF", optimize=True, quality=60, method=6
            )
            s3_object_key = output_path + ".avif"
        else:
            # Process favicon
            image = image.resize((32, 32))
            image.save(output_buffer, format="ICO")
            s3_object_key = output_path + ".ico"

        output_buffer.seek(0)
        return (output_buffer.getvalue(), s3_object_key)

    except Exception as e:
        log_message(f"Failed to process image: {e}")
        return None


async def upload_to_storage_async(buffer_data: bytes, object_key: str) -> bool:
    """
    Upload image to S3 or local storage asynchronously.
    S3 upload runs in thread pool since boto3 is synchronous.
    """
    try:
        if USE_LOCAL_STORAGE:
            # Local storage - run in thread pool for non-blocking I/O
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                image_executor,
                _save_local_file,
                buffer_data,
                object_key
            )
            log_message(f"Saved to local storage: {object_key}")
            return True
        else:
            # S3/R2 storage - run boto3 in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                image_executor,
                _upload_to_s3,
                buffer_data,
                object_key
            )
            log_message(f"Uploaded to S3: {object_key}")
            return True

    except Exception as e:
        log_message(f"Failed to upload {object_key}: {e}")
        return False


def _save_local_file(buffer_data: bytes, object_key: str):
    """Synchronous local file save for thread pool execution"""
    local_path = LOCAL_STORAGE_PATH / object_key
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(buffer_data)


def _upload_to_s3(buffer_data: bytes, object_key: str):
    """Synchronous S3 upload for thread pool execution"""
    buffer = BytesIO(buffer_data)
    s3_client.upload_fileobj(buffer, bucket_name, object_key)


async def download_and_convert_image(session: aiohttp.ClientSession, data: dict) -> list:
    """
    Download and process images (story images and favicons) with parallel uploads.

    Args:
        session: aiohttp session for downloads
        data: Dict with image types as keys, each containing 'url' and 'output_path'

    Returns:
        List of dicts with 'type' and 'path' keys for successfully uploaded images
    """
    # Skip actual download/processing in dry-run mode
    if args.dry_run:
        # Return mock paths with type info for statistics tracking
        return [{"type": item_type, "path": item_data["output_path"] + (".avif" if item_type == "story" else ".ico")}
                for item_type, item_data in data.items() if item_data.get("url")]

    # Download all images concurrently
    download_tasks = []
    items_info = []

    for item_type, item_data in data.items():
        url = item_data["url"]
        if not url:
            continue
        download_tasks.append(get_link_preview(session, url, "download"))
        items_info.append((item_type, item_data))

    if not download_tasks:
        return []

    # Await all downloads concurrently
    download_results = await asyncio.gather(*download_tasks, return_exceptions=True)

    # Process images in thread pool (CPU-bound work)
    loop = asyncio.get_event_loop()
    process_tasks = []
    process_items_info = []

    for i, result in enumerate(download_results):
        if isinstance(result, Exception) or not isinstance(result, bytes):
            continue

        item_type, item_data = items_info[i]
        # Run PIL processing in thread pool
        task = loop.run_in_executor(
            image_executor,
            process_image_sync,
            result,
            item_type,
            item_data["output_path"]
        )
        process_tasks.append(task)
        process_items_info.append(item_type)

    if not process_tasks:
        return []

    # Await all image processing
    process_results = await asyncio.gather(*process_tasks, return_exceptions=True)

    # Upload all processed images concurrently
    upload_tasks = []
    upload_items_info = []

    for i, result in enumerate(process_results):
        if isinstance(result, Exception) or result is None:
            continue

        buffer_data, s3_object_key = result
        upload_tasks.append(upload_to_storage_async(buffer_data, s3_object_key))
        upload_items_info.append({
            "type": process_items_info[i],
            "path": s3_object_key
        })

    if not upload_tasks:
        return []

    # Await all uploads concurrently
    upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)

    # Return successful uploads with type information
    website_paths = []
    for i, result in enumerate(upload_results):
        if result is True:
            website_paths.append(upload_items_info[i])

    return website_paths


async def update_story_image_url(stories_to_update: List[tuple]):
    """
    Batch update story has_image flags.
    """
    if not stories_to_update:
        return

    log.debug(f"Updating {len(stories_to_update)} story image URLs...")
    try:
        async with get_db_connection() as connection:
            async with connection.cursor() as cursor:
                update_query = "UPDATE stories SET has_image = 1 WHERE id = %s"
                await cursor.executemany(update_query, stories_to_update)
            await connection.commit()
            log.debug(f"Updated {len(stories_to_update)} stories in DB")
    except Exception as e:
        log.error(f"DB error updating stories: {e}")


async def update_publisher_favicon(favicon_updates: List[tuple]):
    """
    Batch update publisher favicon URLs.
    """
    if not favicon_updates:
        return

    log_message(f"Updating {len(favicon_updates)} publisher favicons...")
    try:
        async with get_db_connection() as connection:
            async with connection.cursor() as cursor:
                update_query = "UPDATE publishers SET favicon_url = %s WHERE id = %s"
                await cursor.executemany(update_query, favicon_updates)
            await connection.commit()
            log_message(f"Successfully updated {len(favicon_updates)} favicons")
    except Exception as e:
        log_message(f"Error updating publisher favicons: {e}")


async def process_story(
    session: aiohttp.ClientSession,
    story: dict,
    category_name: str,
    semaphore: asyncio.Semaphore
) -> Optional[Dict]:
    """
    Process a single story with semaphore for concurrency control.
    Returns result dict with paths and story info, or None on failure.
    """
    async with semaphore:
        try:
            images_paths = await get_link_preview(session, story, "default", category_name)

            if not isinstance(images_paths, list) or not images_paths:
                return None

            return {
                "story": story,
                "paths": images_paths
            }
        except Exception as e:
            log.debug(f"Error processing story {story['id']}: {e}")
            return None


async def process_category(session: aiohttp.ClientSession, category: dict):
    """
    Process all stories in a category to find and store images.
    Uses asyncio for concurrent processing.
    """
    global shutdown_requested

    stories = await fetch_stories_with_publishers(category["id"], limit=args.limit)
    if not stories:
        log.debug(f"No stories to process for {category['name']}")
        return

    # Check for shutdown before processing
    if shutdown_requested:
        log.warning(f"Skipping {category['name']} due to shutdown request")
        return

    stories_to_update = []
    favicons_to_update = []
    favicon_database: Set[str] = set()

    log.debug(f"Starting async processing with {WORKERS} concurrent tasks for {category['name']}")

    # Semaphore to limit concurrency
    semaphore = asyncio.Semaphore(WORKERS)

    # Create all tasks
    tasks = [
        process_story(session, story, category["name"], semaphore)
        for story in stories
    ]

    total_updated = 0
    local_failed = 0

    # Process with progress bar if available
    if TQDM_AVAILABLE and not args.quiet:
        results = []
        async for result in async_tqdm(
            asyncio.as_completed(tasks),
            total=len(tasks),
            desc=f"  {category['name'][:20]:<20}",
            unit="story",
            leave=False,
            ncols=80
        ):
            if shutdown_requested:
                # Cancel remaining tasks to prevent resource leaks
                for task in tasks:
                    if not task.done():
                        task.cancel()
                # Await cancelled tasks to suppress warnings
                await asyncio.gather(*tasks, return_exceptions=True)
                break
            results.append(await result)
    else:
        # Gather all results
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    for result in results:
        stats.stories_processed += 1

        if isinstance(result, Exception) or result is None:
            stats.downloads_failed += 1
            local_failed += 1
            continue

        story = result["story"]
        images_data = result["paths"]

        for image_info in images_data:
            image_type = image_info["type"]
            image_path = image_info["path"]
            image_url = f"{bucket_base_url}/{image_path}"

            if image_type == "story":
                stories_to_update.append((story["id"],))
                stats.stories_updated += 1
            elif image_type == "favicon":
                favicons_to_update.append((image_url, story["publisher"]["id"]))
                stats.favicons_updated += 1

            total_updated += 1

    # Batch update database (skip in dry-run mode)
    if not args.dry_run:
        await update_story_image_url(stories_to_update)
        await update_publisher_favicon(favicons_to_update)
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
  HEAD request skips:    {stats.head_request_skips}
  Success rate:          {rate_str}
  Time elapsed:          {stats.elapsed_time()}
{'='*50}
""")


async def search_images():
    """Main async function to search and process images for all categories"""
    global shutdown_requested

    storage_mode = "LOCAL STORAGE" if USE_LOCAL_STORAGE else "S3/R2"

    # Show header
    log.header(f"News Image Search {'[DRY-RUN]' if args.dry_run else ''}")

    if args.dry_run:
        log.warning("DRY-RUN MODE: No changes will be made to database or storage")

    proxy_info = f"Proxies: {len(all_proxies)}" if USE_PROXIES else "Proxies: Disabled (direct connection)"
    log.info(f"Storage: {storage_mode} | Workers: {WORKERS} | Limit: {args.limit}/category")
    log.info(f"{proxy_info} | Timeouts: connect={CONNECT_TIMEOUT}s, total={REQUEST_TIMEOUT}s")

    # Initialize database pool
    await init_db_pool()

    # Clean up old local files if using local storage (run in executor to avoid blocking)
    if not args.dry_run:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, cleanup_old_local_files)

    categories = await fetch_categories_from_database()

    # Filter by category name if specified
    if args.category:
        categories = [c for c in categories if c['name'].lower() == args.category.lower()]
        if not categories:
            log.error(f"Category '{args.category}' not found")
            await close_db_pool()
            return

    if not categories:
        log.error("No categories found, exiting")
        await close_db_pool()
        return

    stats.categories_total = len(categories)
    log.info(f"Processing {len(categories)} categories...")
    print()  # Blank line before progress

    # Create a single aiohttp session for connection reuse
    connector = aiohttp.TCPConnector(
        limit=WORKERS * 2,  # Connection pool size
        limit_per_host=10,
        ttl_dns_cache=300,  # DNS cache TTL in seconds
        enable_cleanup_closed=True,
    )

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        headers={"User-Agent": choice(immutable.USER_AGENTS)}
    ) as session:
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
                await process_category(session, category)
            except Exception as e:
                log.error(f"Error processing {category['name']}: {e}")
                continue

    # Close database pool
    await close_db_pool()

    # Shutdown thread pool
    image_executor.shutdown(wait=True)

    # Print summary
    print_summary()

    if shutdown_requested:
        log.warning("Run was interrupted before completion")
    else:
        log.success("Finished!")


def main():
    """Entry point - runs the async main function"""
    try:
        asyncio.run(search_images())
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)


if __name__ == "__main__":
    main()
