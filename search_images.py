import concurrent.futures
import os

from requests.exceptions import ProxyError, ConnectionError, Timeout
from requests import get as get_request
from random import shuffle, choice
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image

from website_scripts import json_util, config, scripts, immutable

# Global list to keep track of bad proxies
bad_proxies = []


def get_link_preview(data, source:str='default', selected_filter:str='None') -> str:
    """
    Takes an URL as input and returns a link to an image preview.
    Handles proxy selection and retries on failure.
    """
    if isinstance(data, dict):
        url = data['link']
    else:
        url = data
    
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
                #print(f'[!] Proxy error with {chosen_proxy}, trying another...')
                continue
            except (ConnectionError, Timeout):
                #print(f'[!] Connection or timeout error with {url}')
                return "static/img/infomundi-white-darkbg-square.webp"
            except Exception as err:
                #print(f'[!] Unexpected error: {err}')
                return "static/img/infomundi-white-darkbg-square.webp"
            
            #print(f'[+] Connected to {chosen_proxy}')
            break

        if source != 'default':
            return response

        return extract_image_from_response(response, url, data, selected_filter)
    except Exception as e:
        print(f'[!] Error in get_link_preview: {e}')
        return 'static/img/infomundi-white-darkbg-square.webp'


def extract_image_from_response(response, url:str, story:dict, selected_filter:str):
    """
    Extracts image URL from the response object.
    """
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')

    image = soup.find('meta', {'property': 'og:image'})
    image = image.get('content').strip() if image else "static/img/infomundi-white-darkbg-square.webp"

    icon_link = soup.find('link', rel=lambda rel: rel and 'icon' in rel.lower())

    if not image.endswith('infomundi-white-darkbg-square.webp'):
        if not os.path.exists(f'{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}'):
            os.mkdir(f'{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}')

        if not os.path.exists(f'{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}/favicons'):
            os.mkdir(f'{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}/favicons')

        if icon_link and icon_link.get('href'):
            favicon = urljoin(url, icon_link['href'])
        else:
            favicon = urljoin(url, '/favicon.ico')

        favicon_database = [x.replace('.ico', '') for x in os.listdir(f'{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}/favicons')]
        
        publisher_id = story.get('publisher_id', '')
        if not publisher_id or publisher_id in favicon_database:
            images = {
            'news': {
                'url': image,
                'output_path': f"{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}/{story['id']}"
                }
            }
        else:
            images = {
                'news': {
                    'url': image,
                    'output_path': f"{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}/{story['id']}"
                },
                'favicon': {
                    'url': favicon,
                    'output_path': f"{config.WEBSITE_ROOT}/static/img/stories/{selected_filter}/favicons/{story['publisher_id']}"
                }
            }

        return download_and_convert_image(images)

    return image


def download_and_convert_image(data: dict):
    website_paths = []
    for item in data:
        url = data[item]['url']
        response = get_link_preview(url, source='convert')

        if isinstance(response, str):
            return response
        
        if response.status_code != 200:
            raise Exception(f"Failed to download the image: Status code {response.status_code}")

        # Open the image using PIL
        try:
            image = Image.open(BytesIO(response.content))
        except Exception:
            continue

        if item == 'news':
            image.thumbnail((500, 500))
            image = image.convert("RGB")
            
            image_path = data[item]['output_path'] + ".webp"
            image.save(image_path, format="webp", optimize=True, quality=35)
        else:
            image.resize((32, 32))
            image_path = data[item]['output_path'] + ".ico"
            image.save(image_path)

        website_paths.append(image_path.replace(config.WEBSITE_ROOT, ''))
    
    return website_paths


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
    
    total = 0
    for selected_filter in top_countries:
        total += 1
        progress_percentage = (total * 100) // len(categories)
        
        print(f"\n[{progress_percentage}% done] Searching images for {selected_filter}...")
        process_category(selected_filter)

    print('[+] Finished!')


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
        count = 0
        for story in cache['stories']:
            if 'recently_added' in cache:
                if count >= cache['recently_added']:
                    break
            else:
                if count >= 500:
                    break
            
            if 'static/img/stories' in story['media_content']['url']:
                continue
            
            future = executor.submit(get_link_preview, story, 'default', selected_filter)
            futures.append((future, story))
            count += 1

        total = 0
        for future, story in futures:
            image_url = future.result()
            if isinstance(image_url, str):
                if image_url.endswith('infomundi-white-darkbg-square.webp'):
                    continue
                
                story['media_content']['url'] = image_url
                total += 1
            else:
                # We are now collecting favicon data! First item will always be news image, and second will always be favicon image.
                total += 1
                for index, url in enumerate(image_url):
                    story['media_content']['url' if index == 0 else 'favicon'] = url

        print(f'[+] Gathered {total} images for {selected_filter}')
        json_util.write_json(cache, f'{config.CACHE_PATH}/{selected_filter}')


# Main execution
if __name__ == "__main__":
    search_images()
