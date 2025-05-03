import concurrent.futures
import pillow_avif
import requests
import pymysql
import logging
import boto3

from requests.exceptions import ProxyError, ConnectionError, Timeout
from random import shuffle, choice
from sqlalchemy import or_, and_
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image
from sys import exit

from website_scripts import config, immutable, input_sanitization, hashing_util

WORKERS = 2
DEFAULT_IMAGE = None

# Define proxies variable as global and load proxy list from file
with open(f"{config.LOCAL_ROOT}/assets/http-proxies.txt") as f:
    proxies = [x.rstrip() for x in f.readlines()]
    shuffle(proxies)

# Global list to keep track of bad proxies
bad_proxies = []

# r2 configuration
s3_client = boto3.client(
    "s3",
    endpoint_url=config.R2_ENDPOINT,
    aws_access_key_id=config.R2_ACCESS_KEY,
    aws_secret_access_key=config.R2_SECRET,
    region_name="auto",
)
bucket_name = "infomundi"
bucket_base_url = "https://bucket.infomundi.net"

db_params = {
    "host": "127.0.0.1",
    "user": config.MYSQL_USERNAME,
    "password": config.MYSQL_PASSWORD,
    "db": "infomundi",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}
db_connection = pymysql.connect(**db_params)


# Setup logging
logging.basicConfig(
    filename=f"{config.LOCAL_ROOT}/logs/search_images.log",
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
)


def log_message(message):
    print(f"[~] {message}")
    # logging.info(message)


def fetch_categories_from_database():
    log_message("Fetching categories from the database")
    try:
        with db_connection.cursor() as cursor:
            # Construct the SQL query to fetch category IDs
            sql_query = "SELECT * FROM categories"
            cursor.execute(sql_query)
            categories = cursor.fetchall()

            shuffle(categories)
    except pymysql.MySQLError as e:
        log_message(f"Error fetching categories: {e}")
        return []

    log_message(f"Got a total of {len(categories)} categories from the database")
    return categories


def fetch_publishers_from_database(category_id: int):
    log_message(f"Fetching publishers for category ID: {category_id}")
    try:
        with db_connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM publishers WHERE category_id = %s", (category_id,)
            )
            publishers = cursor.fetchall()
    except Exception as e:
        log_message(f"Error fetching publishers: {e}")
        return []

    log_message(f"Got {len(publishers)} publishers from the database")
    return publishers


def fetch_stories_from_database(category_id: int, limit: int = 250):
    log_message(f"Fetching stories...")
    try:
        with db_connection.cursor() as cursor:
            # Construct the SQL query with a LIMIT clause
            sql_query = """
                SELECT * FROM stories 
                WHERE category_id = %s AND NOT has_image 
                ORDER BY created_at DESC
                LIMIT %s
            """
            # Execute the query
            cursor.execute(sql_query, (category_id, limit))

            # Fetch all the results
            stories = cursor.fetchall()
    except pymysql.MySQLError as e:
        log_message(f"Error fetching stories: {e}")
        stories = []

    log_message(f"Got a total of {len(stories)} for category id {category_id}")
    return stories


def get_link_preview(data, source: str = "default", category_name: str = "None"):
    """
    Attempts to retrieve a link preview image URL for a given URL. Handles proxy rotation
    and retries upon failure. Can return either a preview image URL or, under certain conditions,
    a response object directly.

    Parameters:
        data (str or dict): If a dict, expects 'link' key with the URL. Otherwise, directly uses the string as the URL.
        source (str): Determines the mode of operation. If not 'default', the raw response object is returned for further processing.
        category_name (str): Not directly used in this function but passed to subsequent functions for directory management.

    Returns:
        str or requests.Response: Returns the image preview URL as a string under normal operation. If source is not 'default',
        returns the response object for further processing.
    """
    global proxies
    global bad_proxies

    # Determine URL based on data type.
    if isinstance(data, str):
        url = data
    else:
        url = data["url"]

    if not input_sanitization.is_valid_url(url):
        log_message(f"Invalid url: {url}")
        return DEFAULT_IMAGE

    try:
        while True:
            # Randomly select a user agent to simulate browser requests
            headers = {"User-Agent": choice(immutable.USER_AGENTS)}

            # Filter out bad proxies identified in previous attempts
            proxies = [x for x in proxies if x not in bad_proxies]

            if not proxies:
                log_message("No proxies left! Returning default image!")
                return DEFAULT_IMAGE

            chosen_proxy = choice(proxies)

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
            except requests.exceptions.ProxyError:
                # Handle proxy errors by marking proxy as bad and retrying
                bad_proxies.append(chosen_proxy)
                log_message(f"[Proxy Error] Added to badlist: {chosen_proxy}")
                continue
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as err:
                # Connection and timeout errors handling
                log_message(f"[Timeout] {err} from {url}")
                return DEFAULT_IMAGE
            except Exception as err:
                # General error handling
                log_message(f"[Unexpected Error] {err}")
                if isinstance(data, object):
                    log_message(f"Story: {data['id']} from: {data['publisher_id']}")

                return DEFAULT_IMAGE

            break  # Break the loop if the request was successful

        if source != "default":
            # Return response object directly for non-default sources. The response object can be used to scrape the story image and favicon url.
            return response

        # Otherwise, proceed to extract and return the image URL. 'data' in this case is a models.Story object.
        return extract_image_from_response(response, url, data, category_name)
    except Exception as e:
        # Log unexpected errors encountered during execution
        log_message(f"[Unexpected] From get link preview: {e}")
        return DEFAULT_IMAGE


def extract_image_from_response(
    response: requests.Response, url: str, story: dict, category_name: str
):
    """
    Extracts and handles an image URL from a web response, with specific attention to news story imagery.

    It looks for an og:image meta tag for a primary image and a favicon as a secondary option.
    If no primary image is found, a default is used. If the image is the default or a favicon is available,
    the function attempts to store these in a structured directory based on a filter criteria.

    Parameters:
        response (requests.Response): The web response object containing the HTML content.
        url (str): The URL from which the response was fetched, used for resolving relative image URLs.
        story (dict): The story itself.
        category_name (str): A filter criteria indicating the subdirectory within which the image should be stored.

    Returns:
        The result of attempting to download and convert the found or default image, and favicon if applicable.
    """
    global favicon_database
    log_message(f"Attempting to extract image from response for {story['id']}")

    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    # Attempt to find the Open Graph image meta tag for the primary image.
    image = soup.find("meta", {"property": "og:image"})
    # If found, strip leading/trailing whitespace from the URL, otherwise use a default image.
    image_url = image.get("content").strip() if image else DEFAULT_IMAGE

    favicon = soup.find("link", rel="icon")
    if favicon:
        favicon_url = favicon["href"]

        if not input_sanitization.is_valid_url(favicon_url):
            favicon_url = urljoin(url, favicon["href"])
    else:
        favicon_url = urljoin(url, "/favicon.ico")

    log_message(
        f"Checking to see if the favicon for story {story['id']} is in the database"
    )
    favicon_file = f"{story['publisher_id']}.ico"
    # Checks to see if the favicon is already in the database so we don't send duplicate requests to the bucket (spend less cash$)

    # TODO: check favicon
    # if favicon_file in favicon_database:
    if True:
        log_message(
            f"Favicon for publisher {story['publisher_id']} is already in the database"
        )
        is_favicon_in_database = True
    else:
        is_favicon_in_database = False

    # If the favicon is already stored, there's no need for us to store it again. So, we specify only the story image information.
    if is_favicon_in_database:
        images = {
            "story": {
                "url": image_url,
                "output_path": f"stories/{category_name}/{hashing_util.binary_to_md5_hex(story['url_hash'])}",
            }
        }
    else:
        images = {
            "story": {
                "url": image_url,
                "output_path": f"stories/{category_name}/{story['story_id']}",
            },
            "favicon": {
                "url": favicon_url,
                "output_path": f"favicons/{category_name}/{story['publisher_id']}",
            },
        }

    return download_and_convert_image(images)


def download_and_convert_image(data: dict) -> list:
    """
    Downloads and processes images specified in the input dictionary.

    This function iterates over each item in the data dictionary, downloads the image from the URL,
    and then processes the image depending on whether it's a news image or a favicon. News images
    are resized and converted to the WebP format for efficiency, while favicons are resized to
    a standard 32x32 pixel size and saved as ICO files.

    Arguments:
        data (dict): A dictionary where each key is a type of image ('news' or 'favicon') and
        the value is another dictionary with 'url' and 'output_path' keys.

    Returns:
        list: A list containing the paths where the processed images were saved to.
    """
    website_paths = []
    for item in data:
        url = data[item]["url"]

        if (
            url == "https://infomundi.net/static/img/infomundi-white-darkbg-square.webp"
            or not url
        ):
            continue

        response = get_link_preview(url, "download")

        # if response is not a requests Object, then the download failed.
        if isinstance(response, str):
            continue

        try:
            # Open the image using PIL
            image = Image.open(BytesIO(response.content))
        except Exception as e:
            log_message(f"[!] Error opening image from {url}, possibly wrong format.")
            continue

        output_buffer = BytesIO()
        if item == "story":
            # Process as before but save to an in-memory bytes buffer
            image.thumbnail((1280, 720))
            image = image.convert("RGB")
            # AVIF my saviour
            image.save(
                output_buffer, format="avif", optimize=True, quality=60, method=6
            )
            s3_object_key = data[item]["output_path"] + ".avif"
        else:
            # Processing favicon images as before, saving to buffer
            image = image.resize((32, 32))
            image.save(output_buffer, format="ico")
            s3_object_key = data[item]["output_path"] + ".ico"

        output_buffer.seek(0)

        try:
            log_message(f"Attempting to upload {s3_object_key} to the bucket")
            s3_client.upload_fileobj(output_buffer, bucket_name, s3_object_key)
        except Exception as e:
            log_message(f"Failed to upload to bucket: {e}")
            continue
        log_message(f"Upload for {s3_object_key} was a success")

        output_buffer.close()
        website_paths.append(s3_object_key)

    return website_paths


def update_story_image_url(stories_to_update):
    """
    stories_to_update should be a list of tuples: [(image_url, story_id), ...]
    """
    if not stories_to_update:
        return

    log_message(f"Updating {len(stories_to_update)} story image URLs...")
    try:
        with db_connection.cursor() as cursor:
            update_query = (
                "UPDATE stories SET image_url = %s, has_image = 1 WHERE id = %s"
            )
            cursor.executemany(update_query, stories_to_update)
        db_connection.commit()
    except pymysql.MySQLError as e:
        log_message(f"Error updating multiple story image URLs: {e}")


def update_publisher_favicon(favicon_updates):
    """
    favicon_updates should be a list of tuples: [(image_url, publisher_id), ...]
    """
    if not favicon_updates:
        return

    log_message(f"Updating {len(favicon_updates)} publisher favicons...")
    try:
        with db_connection.cursor() as cursor:
            update_query = "UPDATE publishers SET favicon = %s WHERE publisher_id = %s"
            cursor.executemany(update_query, favicon_updates)
        db_connection.commit()
    except pymysql.MySQLError as e:
        log_message(f"Error updating multiple favicons: {e}")


def process_category(category: dict):
    """
    Processes each category to find and replace image URLs in the stories.

    This function fetches stories from the database filtered by the selected category.
    It then iterates over these stories, using a ThreadPoolExecutor to concurrently
    attempt to find a suitable image for each story. If a suitable image is found,
    it updates the story's media content URL in the database.

    Parameters:
        category (dict): The category data used to filter stories for processing.

    Note:
        This function handles a fixed number of stories (up to 500 by default) to avoid overwhelming
        the system with too many concurrent operations. Additionally, it updates the
        media content URL for each story, either with a direct image URL or paths to
        downloaded and processed images.
    """
    stories = fetch_stories_from_database(category["id"])
    stories_to_update = []
    favicons_to_update = []

    log_message(f"Starting threading with {WORKERS} workers for {category['name']}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = []
        for story in stories:
            # Submitting a task to the executor to process each story's link preview.
            future = executor.submit(
                get_link_preview, story, "default", category["name"]
            )
            futures.append((future, story))

        total_updated = 0
        for future, story in futures:
            # Gets a list containing paths to the story image and favicon image respectively
            images_paths = future.result()

            # If it's not a list, meaning that something went wrong during the link preview phase, we simply skip the result.
            if not isinstance(images_paths, list):
                continue

            for path in images_paths:
                image_url = f"{bucket_base_url}/{path}"

                if "stories" in path:
                    stories_to_update.append((image_url, story["id"]))
                else:
                    favicons_to_update.append((image_url, story["publisher_id"]))
                    favicon_database.append(f"{story['publisher_id']}.ico")

                total_updated += 1

        update_story_image_url(stories_to_update)
        update_publisher_favicon(favicons_to_update)

        if total_updated > 0:
            log_message(
                f"[{category['name']}] Downloaded {total_updated}/{len(stories)} images."
            )
        else:
            log_message(f"[{category['name']}] No image has been downloaded.")


def search_images():
    """
    Searches images for each category in the feeds path.
    """
    # DEBUG
    categories = [
        x for x in fetch_categories_from_database() if x["name"] == "br_general"
    ]

    total = 0
    for category in categories:
        total += 1
        progress_percentage = (total / 100) * len(categories)

        log_message(
            f"\n[{round(progress_percentage, 2)}%] Searching images for {category['name']}..."
        )
        process_category(category)

    log_message("[+] Finished!")


if __name__ == "__main__":
    search_images()
