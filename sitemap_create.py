import os
from xml.etree import ElementTree as ET

from website_scripts import config, models, extensions
from app import app

with app.app_context():
    session = extensions.db.session
    categories = [x.category_id for x in session.query(models.Category).all()]

SITEMAP_FILE = 'countries.xml'
NAMESPACE = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}


def load_sitemap():
    if os.path.exists(SITEMAP_FILE):
        tree = ET.parse(SITEMAP_FILE)
        root = tree.getroot()
    else:
        root = ET.Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    return root


def add_url(loc, lastmod, changefreq, priority):
    url = ET.Element('url')
    ET.SubElement(url, 'loc').text = loc
    ET.SubElement(url, 'lastmod').text = lastmod
    ET.SubElement(url, 'changefreq').text = changefreq
    ET.SubElement(url, 'priority').text = str(priority)
    return url


def save_sitemap(root):
    tree = ET.ElementTree(root)
    tree.write(SITEMAP_FILE, encoding='utf-8', xml_declaration=True)


def main():
    root = load_sitemap()

    for category in categories:
        country_code = category.split('_')[0]

        loc = f'https://infomundi.net/news?country={country_code}'
        lastmod = '2024-05-30' # YYYY-MM-DD
        changefreq = 'daily' # always, hourly, daily, weekly, monthly, yearly, never
        priority = '0.7' # 0.0 to 1.0

        new_url = add_url(loc, lastmod, changefreq, priority)
        root.append(new_url)
        print(f"[+] Successfully added the URL: {loc} to sitemap.")

    save_sitemap(root)


if __name__ == "__main__":
    main()
