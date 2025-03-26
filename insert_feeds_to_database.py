import pymysql
from unidecode import unidecode
from sys import exit

from website_scripts import config, input_sanitization, immutable, hashing_util, json_util


# Database connection parameters
db_params = {
    'host': '127.0.0.1',
    'user': config.MYSQL_USERNAME,
    'password': config.MYSQL_PASSWORD,
    'db': config.MYSQL_DATABASE,
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

feeds = json_util.read_json('old/feeds')

categories = []
for feed in feeds:
    countries_cca2 = feed['locales'].split('_')[1].lower()
    if ',' in countries_cca2:
        for country_cca2 in countries_cca2.replace(' ', '').split(','):
            categories.append(f'{country_cca2}_general')
    else:
        categories.append(f'{countries_cca2}_general')


categories = list(set(categories))



old_feeds = json_util.read_json('old/old-feeds')
all_categories = list(old_feeds.keys()) + categories


all_unique_categories = list(set(all_categories))


db_connection = pymysql.connect(**db_params)
with db_connection.cursor() as cursor:
    for category in all_unique_categories:
        try:
            cursor.execute("""
                INSERT INTO categories (name) 
                VALUES (%s)
            """, (category))
        except pymysql.err.IntegrityError:
            continue
    db_connection.commit()


with db_connection.cursor() as cursor:
    cursor.execute("SELECT * from categories")
    categories_from_database = cursor.fetchall()


with db_connection.cursor() as cursor:
    for feed in feeds:
        categories = []
        countries_cca2 = feed['locales'].split('_')[1].lower()
        if ',' in countries_cca2:
            for country_cca2 in countries_cca2.replace(' ', '').split(','):
                categories.append(f'{country_cca2}_general')
        else:
            categories.append(f'{countries_cca2}_general')
        url_hash = hashing_util.string_to_md5_binary(feed['url'])
        category_id = [x['id'] for x in categories_from_database if x['name'] in categories][0]

        try:
            cursor.execute("""
                INSERT INTO feeds (site_name, url, url_hash,  category_id) 
                VALUES (%s, %s, %s, %s)
            """, (feed['name'].strip(), feed['url'], url_hash, category_id))
        except Exception:
            continue

    db_connection.commit()

with db_connection.cursor() as cursor:
    for feed in old_feeds:
        category = feed

        category_id = [x['id'] for x in categories_from_database if x['name'] == category][0]

        for feed in old_feeds[feed]:
            url_hash = hashing_util.string_to_md5_binary(feed['url'])
            try:
                cursor.execute("""
                    INSERT INTO publishers (name, url, url_hash, category_id) 
                    VALUES (%s, %s, %s, %s)
                """, (unidecode(feed['site'].strip()), feed['url'], url_hash, category_id))
            except Exception as e:
                print(e)
                continue
    db_connection.commit()