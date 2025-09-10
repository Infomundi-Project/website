import pymysql

from website_scripts import config, input_sanitization, json_util


# Database connection parameters
db_params = {
    "host": "127.0.0.1",
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
                (category),
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

    db_connection.commit()

with db_connection.cursor() as cursor:
    for feed in old_feeds:
        category = feed

        category_id = [
            x["id"] for x in categories_from_database if x["name"] == category
        ][0]

        for feed in old_feeds[feed]:
            try:
                cursor.execute(
                    """
                    INSERT INTO publishers (name, feed_url, category_id) 
                    VALUES (%s, %s, %s)
                """,
                    (
                        input_sanitization.sanitize_html(feed["site"]),
                        feed["url"].strip(),
                        category_id,
                    ),
                )
            except Exception as e:
                print(e)
                continue
    db_connection.commit()
