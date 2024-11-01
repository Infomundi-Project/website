import os
import json
import hashlib
import pymysql
from glob import glob

from website_scripts import config

# Database connection parameters
db_params = {
    'host': '127.0.0.1',
    'user': config.MYSQL_USERNAME,
    'password': config.MYSQL_PASSWORD,
    'db': config.MYSQL_DATABASE,
    'charset': 'utf8mb4'
}

# Directory where JSON files are located
json_directory = './data/news/feeds/'  # Replace with the actual path to your JSON files

# Connect to MySQL database
db_connection = pymysql.connect(**db_params)
cursor = db_connection.cursor()

# Prepare SQL insert statement
insert_query = """
    INSERT INTO feeds (id, category_id, site, url, favicon)
    VALUES (%s, %s, %s, %s, %s)
"""

# Process each JSON file
for file in os.listdir(json_directory):
    file_path = json_directory + file
    # Extract category_id from filename (e.g., "br_general" from "br_general.json")
    filename = os.path.basename(file_path)
    category_id = os.path.splitext(filename)[0]

    print(file_path, filename, category_id)

    # Load JSON data from file
    with open(file_path, 'r', encoding='utf-8') as file:
        feeds = json.load(file)

        # Insert each feed entry into the database
        for feed in feeds:
            if not feed.get('url') or not feed.get('site'):
                continue
            try:
                cursor.execute(insert_query, (
                    hashlib.md5(feed['url'].encode()).hexdigest(),
                    category_id,
                    feed['site'],
                    feed['url'],
                    feed.get('favicon')
                ))
            except Exception as e:
                print(e, feed['site'], feed['url'], feed.get('favicon'))
                continue

# Commit the transaction and close the connection
db_connection.commit()
cursor.close()
db_connection.close()

print("Data migration completed successfully.")
