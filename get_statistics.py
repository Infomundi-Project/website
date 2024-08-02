from datetime import datetime, timedelta

from website_scripts import json_util, config, scripts, models, extensions
from app import app

def get_statistics() -> dict:
    """Handles the statistics for Infomundi. Returns a dict with related information."""
    current_timestamp = datetime.now()
    formatted_time = current_timestamp.strftime('%Y/%m/%d %H:%M')  # Local Time

    statistics = json_util.read_json(config.STATISTICS_PATH)
    saved_timestamp = datetime.fromisoformat(statistics['timestamp'])
    
    time_difference = current_timestamp - saved_timestamp
    if time_difference < timedelta(hours=1):
        # Return cache if it's less than 1 hour old
        statistics['current_time'] = formatted_time
        return statistics

    with app.app_context():
        total_countries_supported = models.Category.query.count()

        total_feeds = models.Publisher.query.count()
        total_news = models.Story.query.count()

        # Get last updated
        time_difference = current_timestamp - saved_timestamp
        
        total_seconds = time_difference.total_seconds()

        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)

        if time_difference < timedelta(hours=1):
            last_updated_message = f"{minutes} minutes ago"
        else:
            last_updated_message = f"{hours} hours ago"

        total_clicks = int(models.Story.query.with_entities(extensions.db.func.sum(models.Story.clicks)).scalar())

        total_users = models.User.query.count()

        total_comments = 32 # DEBUG!

        timestamp_string = current_timestamp.isoformat()
        data = {
            'current_time': formatted_time,
            'timestamp': timestamp_string,  # this will be used to check if the statistics are ready for an update
            'total_countries_supported': total_countries_supported,
            'total_news': f"{total_news:,}",
            'total_feeds': total_feeds,
            'total_users': total_users,
            'total_comments': total_comments,
            'last_updated_message': last_updated_message,
            'total_clicks': total_clicks
        }

        json_util.write_json(data, config.STATISTICS_PATH)

    return data

if __name__ == '__main__':
    get_statistics()
