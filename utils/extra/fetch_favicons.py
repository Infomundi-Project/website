#!/usr/bin/env python3
"""
Fetch and store ONLY favicons for publishers.

- Scans categories and their publishers.
- By default, processes only publishers missing a favicon_url.
- With --force, processes ALL publishers and overwrites uploads & DB values.
- Resolves <link rel="icon"...> (and variants) with absolute URLs (fallback -> /favicon.ico).
- Downloads, converts to 32x32 ICO when raster, uploads to R2 (S3 compatible).
- Updates publishers.favicon_url with the uploaded object URL.

Usage:
  python fetch_favicons.py [--force]
"""

import argparse
import concurrent.futures
import logging
import random
from io import BytesIO
from urllib.parse import urljoin

import boto3
import pymysql
import requests
from bs4 import BeautifulSoup
from PIL import Image

from website_scripts import config, immutable, input_sanitization

# ======================
# Config
# ======================
WORKERS = 8
REQUEST_TIMEOUT = 8

LOG_FILE = f"{config.LOCAL_ROOT}/logs/favicons.log"

# R2 / S3
s3_client = boto3.client(
    "s3",
    endpoint_url=config.R2_ENDPOINT,
    aws_access_key_id=config.R2_ACCESS_KEY,
    aws_secret_access_key=config.R2_SECRET,
    region_name="auto",
)
BUCKET_NAME = "infomundi"
BUCKET_BASE_URL = "https://bucket.infomundi.net"

# DB
db_params = {
    "host": config.MYSQL_HOST,
    "user": config.MYSQL_USERNAME,
    "password": config.MYSQL_PASSWORD,
    "db": config.MYSQL_DATABASE,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}
db_connection = pymysql.connect(**db_params)

# ======================
# Logging
# ======================
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
)


def log(msg: str):
    print(f"[~] {msg}")
    # logging.info(msg)  # enable if you want file logging


# ======================
# DB helpers
# ======================
def fetch_categories_from_database():
    log("Fetching categories from the database")
    try:
        with db_connection.cursor() as cursor:
            cursor.execute("SELECT * FROM categories")
            categories = cursor.fetchall()
            random.shuffle(categories)
            log(f"Got a total of {len(categories)} categories")
            return categories
    except pymysql.MySQLError as e:
        log(f"Error fetching categories: {e}")
        return []


def fetch_publishers(category_id: int, force: bool):
    """
    Returns publishers to process.

    If force=False: only those missing favicon_url (NULL or empty).
    If force=True : all publishers in the category (overwrite mode).
    """
    if force:
        log(f"[force] Fetching ALL publishers for category ID: {category_id}")
        query = """
            SELECT id, name, site_url, feed_url, favicon_url
            FROM publishers
            WHERE category_id = %s
        """
        params = (category_id,)
    else:
        log(f"Fetching publishers without favicons for category ID: {category_id}")
        query = """
            SELECT id, name, site_url, feed_url, favicon_url
            FROM publishers
            WHERE category_id = %s
              AND (favicon_url IS NULL OR favicon_url = '')
        """
        params = (category_id,)

    try:
        with db_connection.cursor() as cursor:
            cursor.execute(query, params)
            publishers = cursor.fetchall()
            log(f"Got {len(publishers)} publishers to process")
            return publishers
    except Exception as e:
        log(f"Error fetching publishers: {e}")
        return []


def update_publisher_favicons(favicon_updates):
    """
    favicon_updates: list of (favicon_url_or_None, publisher_id)

    Note: passing None for favicon_url will set the column to NULL in MySQL.
    """
    if not favicon_updates:
        return
    log(f"Updating {len(favicon_updates)} publisher favicons...")
    try:
        with db_connection.cursor() as cursor:
            cursor.executemany(
                "UPDATE publishers SET favicon_url = %s WHERE id = %s",
                favicon_updates,
            )
        db_connection.commit()
    except pymysql.MySQLError as e:
        log(f"Error updating favicons: {e}")


# ======================
# Networking (no proxies)
# ======================
def http_get(url: str):
    """
    Simple HTTP GET without proxies. Returns requests.Response or None.
    """
    if not input_sanitization.is_valid_url(url):
        log(f"Invalid URL: {url}")
        return None

    headers = {"User-Agent": random.choice(immutable.USER_AGENTS)}
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code in (200, 301, 302):
            return resp
        log(f"[Bad HTTP {resp.status_code}] {url}")
        return None
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        log(f"[Timeout/ConnError] {e} from {url}")
        return None
    except Exception as e:
        log(f"[Unexpected] {e} from {url}")
        return None


# ======================
# Favicon scraping / selection
# ======================
def choose_best_icon(links):
    """
    Given a list of <link> tags whose rel includes 'icon',
    choose the most suitable candidate.

    Preference: sizes=32x32, 48x48, 16x16, 'any', else first.
    """
    if not links:
        return None

    def score(tag):
        sizes = (tag.get("sizes") or "").lower()
        if "32x32" in sizes:
            return 100
        if "48x48" in sizes:
            return 90
        if "16x16" in sizes:
            return 80
        if "any" in sizes:
            return 70
        return 0

    links_sorted = sorted(links, key=score, reverse=True)
    return links_sorted[0]


def extract_favicon_url(html: str, base_url: str) -> str:
    """
    Parse HTML and find a favicon URL. Fallback to /favicon.ico.
    """
    soup = BeautifulSoup(html, "html.parser")

    icon_links = []
    for link in soup.find_all("link"):
        rel = link.get("rel")
        if not rel:
            continue
        rel_str = " ".join(rel).lower() if isinstance(rel, list) else str(rel).lower()
        if "icon" in rel_str:
            icon_links.append(link)

    chosen = choose_best_icon(icon_links)
    if chosen and chosen.get("href"):
        href = chosen.get("href").strip()
        if input_sanitization.is_valid_url(href):
            return href
        return urljoin(base_url, href)

    return urljoin(base_url, "/favicon.ico")


# ======================
# Image processing / upload
# ======================
def upload_bytes(obj_key: str, data: BytesIO) -> bool:
    try:
        log(f"Uploading {obj_key} to bucket...")
        s3_client.upload_fileobj(data, BUCKET_NAME, obj_key)
        log("Upload success")
        return True
    except Exception as e:
        log(f"Upload failed for {obj_key}: {e}")
        return False


def download_and_store_favicon(favicon_url: str, s3_object_key: str) -> str | None:
    """
    Download favicon, try to convert to 32x32 ICO (raster images),
    and upload to R2. Returns public URL string or None on failure.
    """
    resp = http_get(favicon_url)
    if not resp:
        return None

    try:
        img = Image.open(BytesIO(resp.content))
        img = img.convert("RGBA")
        img = img.resize((32, 32))
        out = BytesIO()
        img.save(out, format="ICO")
        out.seek(0)
        ok = upload_bytes(s3_object_key, out)
        out.close()
        return f"{BUCKET_BASE_URL}/{s3_object_key}" if ok else None
    except Exception:
        # If you want SVG-as-is support, uncomment below.
        # if "image/svg" in resp.headers.get("Content-Type", "") or favicon_url.lower().endswith(".svg"):
        #     out = BytesIO(resp.content)
        #     svg_key = s3_object_key.rsplit(".", 1)[0] + ".svg"
        #     out.seek(0)
        #     ok = upload_bytes(svg_key, out)
        #     out.close()
        #     return f"{BUCKET_BASE_URL}/{svg_key}" if ok else None
        log(f"[!] Skipping non-raster favicon (likely SVG): {favicon_url}")
        return None


# ======================
# Per-publisher worker
# ======================
def process_publisher(publisher: dict, category_name: str) -> tuple[int, str | None]:
    """
    Returns (publisher_id, uploaded_public_url_or_None).

    Strategy:
      1) Scrape site/feed to find favicon (preferred).
      2) If (1) fails and publisher has existing favicon_url that is NOT in our bucket,
         try that URL as a source and re-upload into our bucket.
      3) If still nothing, return (id, None) so the caller can set DB to NULL.
    """
    base = publisher.get("site_url") or publisher.get("feed_url")
    if not base or not input_sanitization.is_valid_url(base):
        log(f"Publisher {publisher['id']} has no valid site/feed URL")
        return (publisher["id"], None)

    # Try scraping
    page_resp = http_get(base)
    if page_resp:
        page_resp.encoding = "utf-8"
        favicon_url = extract_favicon_url(page_resp.text, base)
    else:
        favicon_url = urljoin(base, "/favicon.ico")

    s3_key = f"favicons/{category_name}/{publisher['id']}.ico"
    public = download_and_store_favicon(favicon_url, s3_key)

    # Fallback: try existing external URL (useful in --force mode if present)
    existing = publisher.get("favicon_url") or ""
    if not public and existing and not existing.startswith(BUCKET_BASE_URL):
        log(f"Trying existing external favicon as source: {existing}")
        public = download_and_store_favicon(existing, s3_key)

    # Return (id, public or None). None -> caller will set DB NULL.
    return (publisher["id"], public if public else None)


# ======================
# Category loop
# ======================
def process_category(category: dict, force: bool):
    publishers = fetch_publishers(category["id"], force=force)
    if not publishers:
        log(f"[{category['name']}] Nothing to do.")
        return

    updates = []
    log(f"Threading with {WORKERS} workers for {category['name']} (force={force})")
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = [
            ex.submit(process_publisher, p, category["name"]) for p in publishers
        ]
        for fut in concurrent.futures.as_completed(futures):
            try:
                pid, public_url_or_none = fut.result()
                # Always append an update; None maps to SQL NULL
                updates.append((public_url_or_none, pid))
            except Exception as e:
                # If the worker itself fails, still clear favicon_url
                log(f"[Worker error] {e}")
                continue

    update_publisher_favicons(updates)
    # Count successes for logging
    wrote = sum(1 for url, _ in updates if url)
    log(
        f"[{category['name']}] Updated {wrote}/{len(publishers)} favicons "
        f"(set NULL for {len(publishers) - wrote})"
    )


def fetch_favicons(force: bool):
    categories = fetch_categories_from_database()
    total = len(categories)
    for idx, category in enumerate(categories, start=1):
        pct = round((idx / total) * 100.0, 2) if total else 100.0
        log(f"\n[{pct}%] Processing favicons for {category['name']} (force={force})...")
        process_category(category, force=force)
    log("[+] Finished favicon run!")


# ======================
# Entrypoint
# ======================
def main():
    parser = argparse.ArgumentParser(description="Fetch/overwrite publisher favicons.")
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Process ALL publishers and overwrite existing favicons in DB/bucket.",
    )
    args = parser.parse_args()
    fetch_favicons(force=args.force)


if __name__ == "__main__":
    main()
