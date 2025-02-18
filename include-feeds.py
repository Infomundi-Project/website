import pymysql
import json
from unidecode import unidecode
from random import shuffle
from hashlib import md5
from sys import exit

from website_scripts import config


# Database connection parameters
db_params = {
    'host': '127.0.0.1',
    'user': config.MYSQL_USERNAME,
    'password': config.MYSQL_PASSWORD,
    'db': config.MYSQL_DATABASE,
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

db_connection = pymysql.connect(**db_params)

with db_connection.cursor() as cursor:
    sql_query = "SELECT id, url FROM feeds"
    cursor.execute(sql_query)
    results = cursor.fetchall()

    urls_already_in_database = [x['url'] for x in results]
    ids_already_in_database = [x['id'] for x in results]

with open('new_feeds.json') as f:
    new_feeds = json.load(f)


total = 0

with db_connection.cursor() as cursor:
    for feed in new_feeds:
        if feed['url'].lower() in urls_already_in_database:
            continue

        categories = []

        if ',' in feed['locales']:
            for locale in feed['locales'].split(','):
                categories.append(locale.split('_')[1].lower() + '_general')
        else:
            categories.append(feed['locales'].split('_')[1].lower() + '_general')
        

        for category in categories:
            # Creates the publisher id based on a MD5 summary of the feed link.
            publisher_id = md5(unidecode(feed['url'] + category).encode()).hexdigest()
            try:
                # Insert or update the category
                cursor.execute(
                    "INSERT INTO feeds (id, category_id, site, url) VALUES (%s, %s, %s, %s)",
                    (publisher_id, category, feed['name'], feed['url'],)
                )
            except Exception as err:
                print(f"[-] {err}")

    # Commit all changes to the database
    db_connection.commit()