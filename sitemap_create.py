import os
import pymysql
from sys import exit
from xml.etree.ElementTree import Element, ElementTree, SubElement
from defusedxml.ElementTree import parse as safe_parse
from datetime import datetime

from website_scripts import config, models, extensions
from app import app

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


def fetch_categories() -> list:
    try:
        with db_connection.cursor() as cursor:
            # Construct the SQL query to fetch category IDs
            sql_query = "SELECT category_id FROM categories"
            cursor.execute(sql_query)
            categories = cursor.fetchall()

            category_database = [row['category_id'] for row in categories]
            shuffle(category_database)
    except pymysql.MySQLError as e:
        return []
    
    print(f'Got a total of {len(category_database)} categories from the database')
    return category_database


def fetch_stories(selected_filter: str):
    print(f'Fetching stories for {selected_filter}')
    try:
        with db_connection.cursor() as cursor:
            # Construct the SQL query with a LIMIT clause
            sql_query = """
                SELECT story_id FROM stories 
                WHERE category_id = %s AND NOT has_media_content 
                ORDER BY created_at DESC
            """
            # Execute the query
            cursor.execute(sql_query, (selected_filter))
            
            # Fetch all the results
            stories = cursor.fetchall()
    except pymysql.MySQLError as e:
        print(f"Error fetching stories: {e}")
        stories = []
    
    print(f'Got a total of {len(stories)} for {selected_filter}')
    return stories


def add_url(loc, lastmod, changefreq, priority):
    url = Element('url')
    SubElement(url, 'loc').text = loc
    SubElement(url, 'lastmod').text = lastmod
    SubElement(url, 'changefreq').text = changefreq
    SubElement(url, 'priority').text = str(priority)
    return url


def save_sitemap(root, sitemap_file: str):
    tree = ElementTree(root)
    tree.write(SITEMAP_FILE, encoding='utf-8', xml_declaration=True)


def main():
    countries_sitemap = Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')

    for category in categories:
        country_code = category.split('_')[0]

        loc = f'https://infomundi.net/news?country={country_code}'
        lastmod = datetime.today().strftime('%Y-%m-%d')
        changefreq = 'hourly' # always, hourly, daily, weekly, monthly, yearly, never
        priority = '0.7' # 0.0 to 1.0

        new_url = add_url(loc, lastmod, changefreq, priority)
        root.append(new_url)
        print(f"[+] Successfully added the URL: {loc} to sitemap.")

    save_sitemap(countries_sitemap, f'{config.LOCAL_ROOT}/static/countries.xml')

    stories_sitemap = Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')

    for story in categories:
        country_code = category.split('_')[0]

        loc = f'https://infomundi.net/news?country={country_code}'
        lastmod = datetime.today().strftime('%Y-%m-%d')
        changefreq = 'daily'
        priority = '0.7'

        new_url = add_url(loc, lastmod, changefreq, priority)
        root.append(new_url)
        print(f"[+] Successfully added the URL: {loc} to sitemap.")

    save_sitemap(root)


if __name__ == "__main__":
    print(fetch_stories('br_general'))
    exit()
    main()
