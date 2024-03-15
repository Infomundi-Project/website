import json
import os
import pymysql

from website_scripts import config

# Database connection parameters
db_params = {
    'host': 'localhost',
    'user': config.MYSQL_USERNAME,
    'password': config.MYSQL_PASSWORD,
    'db': 'infomundi',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# Path to the directory containing JSON files
json_dir_path = config.CACHE_PATH


def process_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)


def insert_category_and_tags(cursor, category_id, tags):
    # Ensure the category exists
    cursor.execute("INSERT INTO categories (category_id) VALUES (%s) ON DUPLICATE KEY UPDATE category_id = category_id", (category_id,))
    for tag in tags:
        # Insert tag, avoiding duplicates
        cursor.execute("INSERT INTO tags (tag) VALUES (%s) ON DUPLICATE KEY UPDATE tag = tag", (tag,))
        cursor.execute("SELECT tag_id FROM tags WHERE tag = %s", (tag,))
        tag_id = cursor.fetchone()['tag_id']
        # Link tag with category
        cursor.execute("INSERT INTO category_tags (category_id, tag_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE category_id = category_id, tag_id = tag_id", (category_id, tag_id))


def insert_story_data(cursor, story, category_id):
    # Insert publisher, avoiding duplicates
    try:
        cursor.execute("INSERT INTO publishers (publisher_id, name, link) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE name = VALUES(name), link = VALUES(link)", 
                       (story["publisher_id"], story["publisher"], story["publisher_link"]))
        
        cursor.execute("INSERT INTO stories (story_id, title, description, link, pub_date, category_id, publisher_id, media_content_url) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                       (story["id"], story["title"], story["description"], story["link"], story["pubDate"], category_id, story["publisher_id"], story.get("media_content", {}).get("url")))
    except Exception as e:
        print(f'Exception: {e}')


def migrate_data(json_data, category_id):
    try:
        with connection.cursor() as cursor:
            # Insert category and tags
            tags = json_data.get("best_tags", [])
            insert_category_and_tags(cursor, category_id, tags)
            
            # Iterate over stories in the JSON data
            for story in json_data["stories"]:
                insert_story_data(cursor, story, category_id)
                
        connection.commit()
    except pymysql.MySQLError as err:
        print(f"Error: {err}")


connection = pymysql.connect(**db_params)

# Iterate over each JSON file in the specified directory
for filename in os.listdir(json_dir_path):
    if filename.endswith('.json'):
        file_path = os.path.join(json_dir_path, filename)
        category_id = filename.split('.')[0]  # Extract category_id from filename
        json_data = process_json_file(file_path)
        migrate_data(json_data, category_id)

print("Migration completed.")
connection.close()
