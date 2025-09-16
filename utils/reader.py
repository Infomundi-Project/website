import csv

import pymysql
import logging
from website_scripts import (
    config,
    input_sanitization,
)
from sys import exit


with open("/root/e.csv", mode="r") as file:
    # external_url, anchor_text and source_page
    csvFile = csv.DictReader(file)
    index = 0
    count = 0
    for entry in csvFile:
        index += 1
        if len(entry["external_url"]) > 200:
            count += 1
    print(count)
    exit()

# Database connection parameters
db_params = {
    "host": "127.0.0.1",
    "user": config.MYSQL_USERNAME,
    "password": config.MYSQL_PASSWORD,
    "db": config.MYSQL_DATABASE,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

db_connection = pymysql.connect(**db_params)


# Setup logging
logging.basicConfig(
    filename=f"{config.LOCAL_ROOT}/logs/create_cache.log",
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
)


def log_message(message):
    print(f"[~] {message}")
    # logging.info(message)


def fetch_publishers():
    """

    Example:
        {'id': 1282, 'created_at': datetime.datetime(2025, 4, 7, 13, 15, 49), 'name': 'つくおき', 'feed_url': 'https://cookien.com/feed/', 'favicon_url': None, 'category_id': 198, 'site_url': None}
    """
    log_message("Fetching publishers from database")

    with db_connection.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM publishers",
        )
        publishers = cursor.fetchall()

    log_message(f"Got {len(publishers)} publishers from the database")
    return publishers


print(fetch_publishers())


def fetch_categories():
    log_message("Fetching categories from database")
    with db_connection.cursor() as cursor:
        cursor.execute("SELECT * from categories")
        categories = cursor.fetchall()

    return categories


def insert_publishers(categories):
    for category_id in categories:
        try:
            cursor.execute(
                """
                INSERT INTO publishers (name, feed_url, category_id) 
                VALUES (%s, %s, %s)
            """,
                (
                    input_sanitization.sanitize_html(feed["name"]),
                    feed["url"].strip(),
                    category_id,
                ),
            )
        except Exception as e:
            print(f"Error {e}")
            continue
