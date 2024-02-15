import os

from website_scripts import json_util, config


def cleanup_images():
    """
    Lists all the images within the folder and removes images for news that are no longer being used
    """
    categories = [directory for directory in os.listdir(f"{config.WEBSITE_ROOT}/static/img/stories")]

    print('[~] Starting image cleanup process...')
    
    total_deleted = 0
    for category in categories:
        files = [x.replace('.webp', '') for x in os.listdir(f'{config.WEBSITE_ROOT}/static/img/stories/{category}')]
        
        cache = json_util.read_json(f"{config.CACHE_PATH}/{category}")
        stories = [x['id'] for x in cache['stories']]

        to_remove = [x for x in files if x not in stories and x != 'favicons']

        for file in to_remove:
            os.remove(f'{config.WEBSITE_ROOT}/static/img/stories/{category}/{file}.webp')
            total_deleted += 1

    print(f'[-] We deleted {total_deleted} images that were not being used.')

if __name__ == '__main__':
    cleanup_images()