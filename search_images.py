import concurrent.futures
import pymysql
import os

from requests.exceptions import ProxyError, ConnectionError, Timeout
from requests import get as get_request
from random import shuffle, choice
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image

from website_scripts import json_util, config, scripts, immutable

# Database connection parameters
db_params = {
    'host': 'localhost',
    'user': config.MYSQL_USERNAME,
    'password': config.MYSQL_PASSWORD,
    'db': 'infomundi',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

db_connection = pymysql.connect(**db_params)

# Global list to keep track of bad proxies
bad_proxies = []


def get_link_preview(data, source:str='default', selected_filter:str='None'):
    """
    Attempts to retrieve a link preview image URL for a given URL. Handles proxy rotation
    and retries upon failure. Can return either a preview image URL or, under certain conditions,
    a response object directly.

    Parameters:
        data (str or models.Story): If a models.Story, expects 'link' attribute with the URL. Otherwise, directly uses the string as the URL.
        source (str): Determines the mode of operation. If not 'default', the raw response object is returned for further processing.
        selected_filter (str): Not directly used in this function but passed to subsequent functions for directory management.

    Returns:
        str or requests.Response: Returns the image preview URL as a string under normal operation. If source is not 'default',
                                  returns the response object for further processing.
    """

    # Determine URL based on data type
    if isinstance(data, str):
        url = data
    else:
        url = data.link
    
    try:
        # Randomly select a user agent to simulate browser requests
        headers = {'User-Agent': choice(immutable.USER_AGENTS)}

        # Load proxy list from file and limit to first 200 entries for efficiency
        with open(f'{config.WEBSITE_ROOT}/http-proxies.txt') as f:
            proxies = [x.rstrip() for x in f.readlines()][:200]

        while True:
            # Filter out bad proxies identified in previous attempts
            proxies = [x for x in proxies if x not in bad_proxies]
                
            if not proxies:
                # Return default image if no proxies are left
                return "static/img/infomundi-white-darkbg-square.webp"
                
            chosen_proxy = choice(proxies)
            
            try:
                response = requests.get(url, timeout=8, headers=headers, proxies={'http': f'http://{chosen_proxy}'})
                if response.status_code >= 400:
                    # HTTP error handling
                    print(f'[!] Received HTTP error {response.status_code} from {url}')
                    return 'static/img/infomundi-white-darkbg-square.webp'
            except requests.exceptions.ProxyError:
                # Handle proxy errors by marking proxy as bad and retrying
                bad_proxies.append(chosen_proxy)
                continue
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                # Connection and timeout errors handling
                return 'static/img/infomundi-white-darkbg-square.webp'
            except Exception as err:
                # General error handling
                print(f'[!] Unexpected error: {err}')
                return 'static/img/infomundi-white-darkbg-square.webp'
            
            break  # Break the loop if the request was successful

        if source != 'default':
            # Return response object directly for non-default sources
            return response

        # Otherwise, proceed to extract and return the image URL
        return extract_image_from_response(response, url, data, selected_filter)
    except Exception as e:
        # Log unexpected errors encountered during execution
        print(f'[!] Error in get_link_preview: {e}')
        return 'static/img/infomundi-white-darkbg-square.webp'


def extract_image_from_response(response, url:str, story:dict, selected_filter:str):
    """
    Extracts and handles an image URL from a web response, with specific attention to news story imagery.
    
    It looks for an og:image meta tag for a primary image and a favicon as a secondary option.
    If no primary image is found, a default is used. If the image is the default or a favicon is available,
    the function attempts to store these in a structured directory based on a filter criteria.
    
    Parameters:
        response (requests.Response): The web response object containing the HTML content.
        url (str): The URL from which the response was fetched, used for resolving relative image URLs.
        story (dict): A dict, containing details about the story.
        selected_filter (str): A filter criteria indicating the subdirectory within which the image should be stored.
    
    Returns:
        The result of attempting to download and convert the found or default image, and favicon if applicable.
    """
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')

    # Attempt to find the Open Graph image meta tag for the primary image.
    image = soup.find('meta', {'property': 'og:image'})
    # If found, strip leading/trailing whitespace from the URL, otherwise use a default image.
    image = image.get('content').strip() if image else "static/img/infomundi-white-darkbg-square.webp"
    
    # Attempt to find a link tag for the site's favicon.
    icon_link = soup.find('link', rel=lambda rel: rel and 'icon' in rel.lower())

    if image.endswith('infomundi-white-darkbg-square.webp'):
        return image
    
    # Ensure the directory for storing images for this filter exists.
    if not os.path.exists(f'{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}'):
        os.mkdir(f'{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}')
    
    # Ensure the directory for storing favicons for this filter exists.
    if not os.path.exists(f'{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}/favicons'):
        os.mkdir(f'{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}/favicons')

    # Resolve the favicon URL, defaulting to '/favicon.ico' if no specific link tag was found.
    if icon_link and icon_link.get('href'):
        favicon = urljoin(url, icon_link['href'])
    else:
        favicon = urljoin(url, '/favicon.ico')

    # Check if the publisher's favicon has already been stored by listing existing favicons and removing the file extension.
    favicon_database = [x.replace('.ico', '') for x in os.listdir(f'{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}/favicons')]
        
    # Determine the structure of the return value based on the presence of a publisher ID and whether it's in the favicon database.
    publisher_id = story['publisher_id']
    if not publisher_id or publisher_id in favicon_database:
        images = {
        'news': {
            'url': image,
            'output_path': f"{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}/{story['story_id']}"
            }
        }
    else:
        images = {
            'news': {
                'url': image,
                'output_path': f"{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}/{story['story_id']}"
            },
            'favicon': {
                'url': favicon,
                'output_path': f"{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}/favicons/{story['publisher_id']}"
            }
        }

    return download_and_convert_image(images)


def download_and_convert_image(data: dict) -> str:
    """
    Downloads and processes images specified in the input dictionary.
    
    This function iterates over each item in the data dictionary, downloads the image from the URL,
    and then processes the image depending on whether it's a news image or a favicon. News images
    are resized and converted to the WebP format for efficiency, while favicons are resized to
    a standard 32x32 pixel size and saved as ICO files.
    
    Parameters:
        data (dict): A dictionary where each key is a type of image ('news' or 'favicon') and
                     the value is another dictionary with 'url' and 'output_path' keys.
    
    Returns:
        str: A str containing the path where the processed image has been saved, relative to the
              website root directory.
    """
    website_paths = []
    for item in data:
        url = data[item]['url']
        # Downloading the image using a previously defined function or directly if not using proxies.
        # Consider using try-except here to manage download failures gracefully.
        response = get_request(url, timeout=8)  # Adjust timeout as necessary

        if response.status_code != 200:
            # If the image cannot be downloaded, log or handle this situation appropriately.
            raise Exception(f"Failed to download the image from {url}: Status code {response.status_code}")

        # Open the image using PIL
        try:
            image = Image.open(BytesIO(response.content))
        except Exception as e:
            # Handling exceptions if the image is corrupted or in an unexpected format.
            # It might be useful to log this error for troubleshooting.
            print(f"Error opening image from {url}: {e}")
            continue  # Skip this iteration and proceed with the next item

        if item == 'news':
            # Resizing the news image to a maximum of 1280x720 pixels and converting to RGB for WebP format.
            image.thumbnail((1280, 720))
            image = image.convert("RGB")  # Ensure compatibility with WebP format
            
            image_path = data[item]['output_path'] + ".webp"
            image.save(image_path, format="webp", optimize=True, quality=50, method=6)
        else:
            # Resizing favicon images to 32x32 pixels.
            image = image.resize((32, 32), Image.ANTIALIAS)
            
            favicon_path = data[item]['output_path'] + ".ico"
            image.save(favicon_path)
    
    return image_path.replace(config.WEBSITE_ROOT, '')


def search_images():
    """
    Searches images for each category in the feeds path.
    """
    categories = [file.replace(".json", "") for file in os.listdir(f"{config.FEEDS_PATH}")]
    shuffle(categories)

    top_countries = ['us_general', 'br_general', 'in_general', 'ru_general', 'ca_general', 'au_general', 'ar_general']

    # Removes top countries from the categories variable, in order to prevent going into the same country twice
    for country in top_countries:
        categories.remove(country)

    # Extends the top countries list so the script begins getting images for the biggest countries.
    top_countries.extend(categories)
    
    top_countries = ['mx_general'] # DEBUG

    total = 0
    for selected_filter in top_countries:
        total += 1
        progress_percentage = (total * 100) // len(categories)
        
        print(f"\n[{progress_percentage}% done] Searching images for {selected_filter}...")
        process_category(selected_filter)

    print('[+] Finished!')


def process_category(selected_filter: str):
    """
    Processes each category to find and replace image URLs in the stories.

    This function fetches stories from the database filtered by the selected category.
    It then iterates over these stories, using a ThreadPoolExecutor to concurrently
    attempt to find a suitable image for each story. If a suitable image is found, 
    it updates the story's media content URL in the database.

    Parameters:
        selected_filter (str): The category ID used to filter stories for processing.

    Note:
        This function handles a fixed number of stories (up to 500) to avoid overwhelming 
        the system with too many concurrent operations. Additionally, it updates the 
        media content URL for each story, either with a direct image URL or paths to 
        downloaded and processed images, including handling favicons.
    """

    with db_connection.cursor() as cursor:
        cursor.execute("""
            SELECT story_id, media_content_url, publisher_id, link FROM stories
            WHERE category_id = %s AND media_content_url NOT LIKE 'static/img/stories/%%'
            ORDER BY created_at DESC 
            LIMIT 500
            """, (selected_filter,))
        stories = cursor.fetchall()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            count = 0
            for story in stories:
                # Limiting to 500 stories to manage resource usage and ensure responsiveness.
                if count == 500:
                    break
                
                # Skipping stories that already have a manually assigned or previously processed image.
                if 'static/img/stories' in story['media_content_url']:
                    continue
                
                # Submitting a task to the executor to process each story's link preview.
                future = executor.submit(get_link_preview, story, 'default', selected_filter)
                futures.append((future, story))
                count += 1

            total_updated = 0
            for future, story in futures:
                image_url = future.result()
                
                if image_url.endswith('infomundi-white-darkbg-square.webp'):
                    continue
                    
                cursor.execute("""
                    UPDATE stories SET media_content_url = %s WHERE story_id = %s
                    """, (image_url, story_id))
                total_updated += 1

            if total_updated > 0:
                print(f'[+] Gathered {total_updated} images for {selected_filter}')
                db_connection.commit()
            else:
                print(f'[-] No image for {selected_filter} has been gathered.')

# Main execution
if __name__ == "__main__":
    search_images()
    db_connection.close()