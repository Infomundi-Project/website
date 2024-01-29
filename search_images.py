import concurrent.futures
import os

from requests.exceptions import ProxyError, ConnectionError, Timeout
from requests import get as get_request
from random import shuffle, choice
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image

from website_scripts import json_util, config, scripts, immutable

# Global list to keep track of bad proxies
bad_proxies = []


def get_link_preview(data: str, source:str='default', selected_filter:str='None') -> str:
    """
    Takes an URL as input and returns a link to an image preview.
    Handles proxy selection and retries on failure.
    """
    if not isinstance(data, dict):
        url = data
    else:
        url = data['link']
    
    try:
        headers = {'User-Agent': choice(immutable.USER_AGENTS)}

        with open(f'{config.WEBSITE_ROOT}/http-proxies.txt') as f:
            proxies = [x.rstrip() for x in f.readlines()][:200]

        while True:
            proxies = [x for x in proxies if x not in bad_proxies]
                
            if not proxies:
                return "static/img/infomundi-white-darkbg-square.webp"
                
            chosen_proxy = choice(proxies)
            
            try:
                response = get_request(url, timeout=8, headers=headers, proxies={'http': f'http://{chosen_proxy}'})
                if response.status_code >= 400:
                    print(f'[!] Received HTTP error {response.status_code} from {url}')
                    return "static/img/infomundi-white-darkbg-square.webp"
            except ProxyError:
                bad_proxies.append(chosen_proxy)
                print(f'[!] Proxy error with {chosen_proxy}, trying another...')
                continue
            except (ConnectionError, Timeout):
                print(f'[!] Connection or timeout error with {url}')
                return "static/img/infomundi-white-darkbg-square.webp"
            except Exception as err:
                print(f'[!] Unexpected error: {err}')
                return "static/img/infomundi-white-darkbg-square.webp"
            
            print(f'[+] Connected to {chosen_proxy}')
            break

        if source != 'default':
            return response

        return extract_image_from_response(response, data, selected_filter)
    except Exception as e:
        print(f'[!] Error in get_link_preview: {e}')
        return 'static/img/infomundi-white-darkbg-square.webp'


def extract_image_from_response(response, story:dict, selected_filter:str):
    """
    Extracts image URL from the response object.
    """
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')

    image = soup.find('meta', {'property': 'og:image'})
    image = image.get('content').strip() if image else "static/img/infomundi-white-darkbg-square.webp"

    if not image.endswith('infomundi-white-darkbg-square.webp'):
        if not os.path.exists(f'{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}'):
            os.mkdir(f'{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}')

        output_path = f"{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}/{story['id']}"
        return download_and_convert_image(image, output_path)

    return image


def download_and_convert_image(url, output_path):
    # Download the image
    response = get_link_preview(url, source='convert')
    if response.status_code != 200:
        raise Exception(f"Failed to download the image: Status code {response.status_code}")

    # Open the image using PIL
    image = Image.open(BytesIO(response.content))

    # Convert the image to WebP
    image = image.convert("RGB")
    webp_image_path = output_path + ".webp"
    image.save(webp_image_path, format="webp", optimize=True, quality=35)

    print(f'[+] Downloading {webp_image_path}')

    path_splitted = webp_image_path.split('/')

    website_path = f'static/img/stories/{path_splitted[-2]}/{path_splitted[-1]}'
    return website_path


def search_images():
    """
    Searches images for each category in the feeds path.
    """
    categories = [file.replace(".json", "") for file in os.listdir(f"{config.FEEDS_PATH}")]
    shuffle(categories)
    
    for selected_filter in categories:
        print(f"\n[~] Searching images for {selected_filter}...")
        process_category(selected_filter)

    cleanup_images()    
    print('[+] Finished!')


def cleanup_images():
    """
    Lists all the images within the folder and removes images for news that are no longer being used
    """
    categories = [directory for directory in os.listdir(f"{config.WEBSITE_ROOT}/static/img/stories")]

    total_deleted = 0
    for category in categories:
        files = [x.replace('.webp', '') for x in os.listdir(f'{config.WEBSITE_ROOT}/static/img/stories/{category}')]
        
        cache = json_util.read_json(f"{config.CACHE_PATH}/{category}")
        stories = [x['id'] for x in cache['stories']]

        to_remove = [x for x in files if x not in stories]

        for file in to_remove:
            os.remove(f'{config.WEBSITE_ROOT}/static/img/stories/{category}/{file}.webp')
            total_deleted += 1

    print(f'[~] We deleted {total_deleted} images that were not being used.')


def process_category(selected_filter):
    """
    Processes each category to find and replace image URLs.
    """
    try:
        cache = json_util.read_json(f'{config.CACHE_PATH}/{selected_filter}')
    except FileNotFoundError: 
        print(f"[!] No cache file found for {selected_filter}")
        return

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for story in cache['stories']:
            if 'static/img/stories' in story['media_content']['url'] and False:
                continue
            future = executor.submit(get_link_preview, story, 'default', selected_filter)
            futures.append((future, story))

        total = 0
        for future, story in futures:
            image_url = future.result()
            if image_url.endswith('infomundi-white-darkbg-square.webp'):
                continue
            
            story['media_content']['url'] = image_url
            total += 1

        print(f'[+] Gathered {total} images for {selected_filter}')
        json_util.write_json(cache, f'{config.CACHE_PATH}/{selected_filter}')


# Main execution
if __name__ == "__main__":
    search_images()
