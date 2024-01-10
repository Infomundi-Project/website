import concurrent.futures

from requests.exceptions import ProxyError, ConnectionError, Timeout
from requests import get as get_request
from random import shuffle, choice
from bs4 import BeautifulSoup
from os import listdir

from website_scripts import json_util, config, scripts, immutable

# Global list to keep track of bad proxies
bad_proxies = []


def get_link_preview(url: str) -> str:
    """
    Takes an URL as input and returns a link to an image preview.
    Handles proxy selection and retries on failure.
    """
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

        return extract_image_from_response(response)
    except Exception as e:
        print(f'[!] Error in get_link_preview: {e}')
        return 'static/img/infomundi-white-darkbg-square.webp'


def extract_image_from_response(response):
    """
    Extracts image URL from the response object.
    """
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')

    image = soup.find('meta', {'property': 'og:image'})
    image = image.get('content').strip() if image else "static/img/infomundi-white-darkbg-square.webp"

    return image


def search_images():
    """
    Searches images for each category in the feeds path.
    """
    categories = [file.replace(".json", "") for file in listdir(f"{config.FEEDS_PATH}")]
    shuffle(categories)
    
    for selected_filter in categories:
        print(f"\n[~] Searching images for {selected_filter}...")
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
        for story in cache['stories']:
            if 'infomundi' in story['media_content']['url']:
                future = executor.submit(get_link_preview, story['link'])
                futures.append((future, story))

        total = 0
        for future, story in futures:
            image_url = future.result()
            if 'infomundi' not in image_url:
                story['media_content']['url'] = image_url
                total += 1

        print(f'[+] Gathered {total} images for {selected_filter}')
        json_util.write_json(cache, f'{config.CACHE_PATH}/{selected_filter}')


# Main execution
if __name__ == "__main__":
    search_images()
