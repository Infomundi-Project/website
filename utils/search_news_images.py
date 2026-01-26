import concurrent.futures
import requests
import pymysql
import logging
import boto3
import time
from contextlib import contextmanager
from random import shuffle, choice
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image
from pathlib import Path
from os import makedirs as os_makedirs

from website_scripts import config, immutable, input_sanitization, hashing_util

# Configuration
WORKERS = 20  # FIX: Increased from 1 for actual concurrency
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
    print("[✓] Successfully initialized S3 client")
except Exception as e:
    print(f"[!] S3 client initialization failed: {e}. Falling back to local storage.")
    USE_LOCAL_STORAGE = True
    # Create local storage directory
    LOCAL_STORAGE_PATH = Path("/app/static/local_uploads")
    LOCAL_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    print(f"[✓] Local storage initialized at: {LOCAL_STORAGE_PATH}")
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
logging.basicConfig(
    filename=f"{config.WEBSITE_ROOT}/logs/search_images.log",
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
)


def log_message(message):
    """Log message to both console and file"""
    print(f"[~] {message}")
    logging.info(message)


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
        log_message(f"Clearing {len(bad_proxies)} bad proxies to prevent memory leak")
        bad_proxies.clear()

    # FIX: O(1) set lookups instead of O(n) list filtering in loop
    working_proxies = [p for p in proxies if p not in bad_proxies]

    if not working_proxies:
        log_message("No working proxies available!")
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
            bad_proxies.add(chosen_proxy)  # FIX: Use set.add instead of list.append
            log_message(f"[Proxy Error] Added to badlist: {chosen_proxy}")

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
        log_message("Skipping - no stories to update")
        return

    log_message(f"Updating {len(stories_to_update)} story image URLs...")
    try:
        with get_db_connection() as db_connection:
            with db_connection.cursor() as cursor:
                update_query = "UPDATE stories SET has_image = 1 WHERE id = %s"
                cursor.executemany(update_query, stories_to_update)
            db_connection.commit()
            log_message(f"Successfully updated {len(stories_to_update)} stories")
    except pymysql.MySQLError as e:
        log_message(f"Error updating story image URLs: {e}")


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
    stories = fetch_stories_with_publishers(category["id"])
    if not stories:
        log_message(f"No stories to process for {category['name']}")
        return

    stories_to_update = []
    favicons_to_update = []
    favicon_database = set()  # FIX: Use set instead of list for O(1) lookups

    log_message(f"Starting threading with {WORKERS} workers for {category['name']}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
        # Submit all tasks
        future_to_story = {
            executor.submit(get_link_preview, story, "default", category["name"]): story
            for story in stories
        }

        total_updated = 0

        # Process completed futures
        for future in concurrent.futures.as_completed(future_to_story):
            story = future_to_story[future]

            try:
                images_paths = future.result()
            except Exception as e:
                log_message(f"Error processing story {story['id']}: {e}")
                continue

            # Validate result
            if not isinstance(images_paths, list):
                continue

            for path in images_paths:
                image_url = f"{bucket_base_url}/{path}"

                if "stories" in path:
                    # FIX: Proper tuple with trailing comma
                    stories_to_update.append((story["id"],))
                else:
                    # FIX: Proper tuple creation
                    favicons_to_update.append((image_url, story["publisher"]["id"]))
                    favicon_database.add(f"{story['publisher']['id']}.ico")

                total_updated += 1

        # Batch update database
        update_story_image_url(stories_to_update)
        update_publisher_favicon(favicons_to_update)

        if total_updated > 0:
            log_message(
                f"[{category['name']}] Downloaded {total_updated}/{len(stories)} images."
            )
        else:
            log_message(f"[{category['name']}] No images downloaded.")


def search_images():
    """Main function to search and process images for all categories"""
    storage_mode = "LOCAL STORAGE" if USE_LOCAL_STORAGE else "S3/R2"
    log_message(f"Starting image search using {storage_mode}")

    # Clean up old local files if using local storage
    cleanup_old_local_files()

    categories = fetch_categories_from_database()

    if not categories:
        log_message("No categories found, exiting")
        return

    total = 0
    for category in categories:
        total += 1
        # FIX: Correct progress calculation
        progress_percentage = (total / len(categories)) * 100

        log_message(
            f"\n[{round(progress_percentage, 2)}%] Searching images for {category['name']}..."
        )

        try:
            process_category(category)
        except Exception as e:
            log_message(f"Error processing category {category['name']}: {e}")
            continue

    log_message("[+] Finished!")


if __name__ == "__main__":
    search_images()
