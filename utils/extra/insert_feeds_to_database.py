import pymysql

from website_scripts import config, input_sanitization, json_util


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
                # Fix: Validate and truncate feed name and URL
                feed_name = (feed.get("name") or "Unknown")[:150]  # Max 150 chars
                feed_url = (feed.get("url") or "").strip()[:200] if feed.get("url") else None  # Max 200 chars
                
                if not feed_name or not feed_url:
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
                # Fix: Validate and truncate feed name and URL
                feed_name = (feed.get("site") or "Unknown")[:150]  # Max 150 chars
                feed_url = (feed.get("url") or "").strip()[:200] if feed.get("url") else None  # Max 200 chars
                
                if not feed_name or not feed_url:
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
