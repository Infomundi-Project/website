import pymysql
from datetime import datetime, timedelta

from website_scripts import config

db_params = {
    "host": "127.0.0.1",
    "user": config.MYSQL_USERNAME,
    "password": config.MYSQL_PASSWORD,
    "database": config.MYSQL_DATABASE,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}


def get_statistics() -> dict:
    """Handles the statistics for Infomundi. Returns a dict with related information."""
    current_timestamp = datetime.now()
    formatted_time = current_timestamp.strftime("%Y/%m/%d %H:%M")  # Local Time

    with pymysql.connect(**db_params) as connection:
        with connection.cursor() as cursor:

            # Fetching current statistics record
            cursor.execute("SELECT * FROM site_statistics ORDER BY id DESC LIMIT 1")
            statistics = cursor.fetchone()

            saved_timestamp = statistics["created_at"] if statistics else None
            if saved_timestamp:
                # Check if cache is less than 1 hour old
                if current_timestamp - saved_timestamp < timedelta(hours=24):
                    return statistics  # Return if data is fresh

            # Calculating statistics
            cursor.execute("SELECT COUNT(*) FROM categories")
            total_countries_supported = cursor.fetchone()["COUNT(*)"]

            cursor.execute("SELECT COUNT(*) FROM publishers")
            total_feeds = cursor.fetchone()["COUNT(*)"]

            cursor.execute("SELECT COUNT(*) FROM stories")
            total_news = cursor.fetchone()["COUNT(*)"]

            cursor.execute("SELECT SUM(views) FROM story_stats")
            total_clicks = cursor.fetchone()["SUM(views)"] or 0

            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()["COUNT(*)"]

            cursor.execute("SELECT COUNT(*) FROM comments")
            total_comments = cursor.fetchone()["COUNT(*)"]

            # Calculate last updated message
            if saved_timestamp:
                time_difference = current_timestamp - saved_timestamp
                total_seconds = time_difference.total_seconds()
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)

                if time_difference < timedelta(hours=1):
                    last_updated_message = f"{minutes} minutes ago"
                else:
                    last_updated_message = f"{hours} hours ago"
            else:
                last_updated_message = "Now"

            # Insert or update statistics in the database
            if statistics:
                cursor.execute(
                    """
                    UPDATE site_statistics SET total_countries_supported=%s, total_news=%s, total_feeds=%s, 
                    total_users=%s, total_comments=%s, last_updated_message=%s, 
                    total_clicks=%s WHERE id=%s
                    """,
                    (
                        total_countries_supported,
                        total_news,
                        total_feeds,
                        total_users,
                        total_comments,
                        last_updated_message,
                        total_clicks,
                        statistics["id"],
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO site_statistics (total_countries_supported, 
                    total_news, total_feeds, total_users, total_comments, last_updated_message, 
                    total_clicks) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        total_countries_supported,
                        total_news,
                        total_feeds,
                        total_users,
                        total_comments,
                        last_updated_message,
                        total_clicks,
                    ),
                )
            connection.commit()

    # Return dictionary with updated statistics data
    data = {
        "current_time": formatted_time,
        "total_countries_supported": total_countries_supported,
        "total_news": f"{total_news:,}",
        "total_feeds": total_feeds,
        "total_users": total_users,
        "total_comments": total_comments,
        "last_updated_message": last_updated_message,
        "total_clicks": total_clicks,
    }

    return data


if __name__ == "__main__":
    print(get_statistics())
