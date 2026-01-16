import pymysql

from website_scripts import config, input_sanitization, json_util

# Column size constants from Publisher model (models.py)
# name = db.Column(db.String(150), nullable=False)
# feed_url = db.Column(db.String(200))
PUBLISHER_NAME_MAX_LENGTH = 150
PUBLISHER_URL_MAX_LENGTH = 200


def validate_and_truncate_feed(feed: dict, name_key: str) -> tuple[str, str] | tuple[None, None]:
    """
    Validate and truncate feed name and URL to match database column constraints.
    Uses "Unknown" as fallback for missing or empty names.
    
    Args:
        feed: Dictionary containing feed data
        name_key: Key to use for extracting the feed name ('name' or 'site')
    
    Returns:
        Either (feed_name, feed_url) with both as valid strings, or (None, None) if URL is invalid.
    """
    raw_name = feed.get(name_key)
    if raw_name:
        stripped_name = str(raw_name).strip()
        if stripped_name:
            feed_name = stripped_name[:PUBLISHER_NAME_MAX_LENGTH]
        else:
            feed_name = "Unknown"
    else:
        feed_name = "Unknown"
    
    raw_url = feed.get("url")
    if raw_url:
        stripped_url = str(raw_url).strip()
        feed_url = stripped_url[:PUBLISHER_URL_MAX_LENGTH] if stripped_url else None
    else:
        feed_url = None
    
    # Only reject if URL is missing (name defaults to "Unknown")
    if feed_url is None:
        return None, None
    
    return feed_name, feed_url


# Database connection parameters
db_params = {
    "host": config.MYSQL_HOST,
    "user": config.MYSQL_USERNAME,
    "password": config.MYSQL_PASSWORD,
    "db": config.MYSQL_DATABASE,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

feeds = json_util.read_json("assets/data/json/feeds/feeds")

categories = []
for feed in feeds:
    countries_cca2 = feed["locales"].split("_")[1].lower()
    if "," in countries_cca2:
        for country_cca2 in countries_cca2.replace(" ", "").split(","):
            categories.append(f"{country_cca2}_general")
    else:
        categories.append(f"{countries_cca2}_general")


categories = list(set(categories))

old_feeds = json_util.read_json("assets/data/json/feeds/old-feeds")
all_categories = list(old_feeds.keys()) + categories


all_unique_categories = list(set(all_categories))


db_connection = pymysql.connect(**db_params)
with db_connection.cursor() as cursor:
    for category in all_unique_categories:
        try:
            cursor.execute(
                """
                INSERT INTO categories (name)
                VALUES (%s)
            """,
                (category,),  # Fix: tuple with comma
            )
        except pymysql.err.IntegrityError:
            continue
    db_connection.commit()


with db_connection.cursor() as cursor:
    cursor.execute("SELECT * from categories")
    categories_from_database = cursor.fetchall()


with db_connection.cursor() as cursor:
    for feed in feeds:
        categories = []
        countries_cca2 = feed["locales"].split("_")[1].lower()
        if "," in countries_cca2:
            for country_cca2 in countries_cca2.replace(" ", "").split(","):
                categories.append(f"{country_cca2}_general")
        else:
            categories.append(f"{countries_cca2}_general")
        categories_id = [
            x["id"] for x in categories_from_database if x["name"] in categories
        ]

        for category_id in categories_id:
            try:
                feed_name, feed_url = validate_and_truncate_feed(feed, "name")
                
                if feed_name is None or feed_url is None:
                    continue

                cursor.execute(
                    """
                    INSERT INTO publishers (name, feed_url, category_id)
                    VALUES (%s, %s, %s)
                """,
                    (
                        input_sanitization.sanitize_html(feed_name),
                        feed_url,
                        category_id,
                    ),
                )
            except Exception as e:
                print(f"Error inserting feed {feed.get('name')}: {e}")
                continue

    db_connection.commit()

with db_connection.cursor() as cursor:
    for feed_category in old_feeds:
        category = feed_category

        category_id = [
            x["id"] for x in categories_from_database if x["name"] == category
        ][0]

        for feed in old_feeds[feed_category]:
            try:
                feed_name, feed_url = validate_and_truncate_feed(feed, "site")
                
                if feed_name is None or feed_url is None:
                    continue

                cursor.execute(
                    """
                    INSERT INTO publishers (name, feed_url, category_id)
                    VALUES (%s, %s, %s)
                """,
                    (
                        input_sanitization.sanitize_html(feed_name),
                        feed_url,
                        category_id,
                    ),
                )
            except Exception as e:
                print(f"Error inserting old feed {feed.get('site')}: {e}")
                continue
    db_connection.commit()

db_connection.close()
print("✅ Publishers inserted successfully!")
