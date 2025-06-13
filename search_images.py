#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
import boto3

from requests.exceptions import ProxyError, ConnectionError, Timeout
from random import shuffle, choice
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from io import BytesIO
from urllib.parse import urljoin

import aiohttp
import aiomysql
from aiobotocore.session import get_session
import pyvips

from website_scripts import config, immutable, input_sanitization, hashing_util

# Configuration
WORKERS = int(os.getenv("WORKERS", 50))
DB_BATCH_SIZE = int(os.getenv("DB_BATCH_SIZE", 500))
HTTP_CONCURRENCY = int(os.getenv("HTTP_CONCURRENCY", 100))
S3_CONCURRENCY = int(os.getenv("S3_CONCURRENCY", 50))
DEFAULT_IMAGE = None

PROXY_FILE = os.path.join(config.LOCAL_ROOT, "assets", "http-proxies.txt")
LOG_FILE = os.path.join(config.LOCAL_ROOT, "logs", "search_images_async.log")

S3_BUCKET = "infomundi"
S3_BASE_URL = "https://bucket.infomundi.net"

DB_CONFIG = {
    "host": "127.0.0.1",
    "user": config.MYSQL_USERNAME,
    "password": config.MYSQL_PASSWORD,
    "db": config.MYSQL_DATABASE,
    "charset": "utf8mb4",
    "cursorclass": aiomysql.DictCursor,
    "autocommit": False,
}

# Logging
logger = logging.getLogger("image_gatherer_async")
logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5
)
handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
logger.addHandler(handler)

# Load and shuffle proxies
with open(PROXY_FILE) as pf:
    _proxies = [line.strip() for line in pf if line.strip()]
random.shuffle(_proxies)
proxies = _proxies[:]
bad_proxies = set()
proxy_lock = asyncio.Lock()

# Semaphores for limiting concurrency
http_sem = asyncio.Semaphore(HTTP_CONCURRENCY)
s3_sem = asyncio.Semaphore(S3_CONCURRENCY)


async def get_proxy():
    async with proxy_lock:
        valid = [p for p in proxies if p not in bad_proxies]
        return random.choice(valid) if valid else None


async def mark_bad(proxy):
    async with proxy_lock:
        bad_proxies.add(proxy)


async def init_db_pool(loop):
    return await aiomysql.create_pool(loop=loop, **DB_CONFIG)


async def init_s3_client():
    session = get_session()
    return await session.create_client(
        "s3",
        endpoint_url=config.R2_ENDPOINT,
        aws_access_key_id=config.R2_ACCESS_KEY,
        aws_secret_access_key=config.R2_SECRET,
        region_name="auto",
    ).__aenter__()

def fetch_stories_with_publishers(category_id: int, limit: int = 20):
    log_message("Fetching stories with nested publisher dict...")
    try:
        with db_connection.cursor() as cursor:
            sql = """
            SELECT
                s.*,
                p.favicon_url AS publisher_favicon_url,
                p.id          AS publisher_id,
                p.name        AS publisher_name,
                p.feed_url    AS publisher_feed_url,
                p.site_url    AS publisher_site_url
            FROM stories AS s
            JOIN publishers AS p
              ON s.publisher_id = p.id
            WHERE s.category_id = %s
              AND NOT s.has_image
            ORDER BY s.created_at DESC
            LIMIT %s
            """
            cursor.execute(sql, (category_id, limit))
            rows = cursor.fetchall()
    except pymysql.MySQLError as e:
        log_message(f"Error fetching stories: {e}")
        return []

async def fetch_categories(pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM categories")
            cats = await cur.fetchall()
    random.shuffle(cats)
    return cats


async def fetch_stories(pool, category_id):
    sql = (
        "SELECT s.*, p.favicon_url AS publisher_favicon_url,"
        " p.id AS publisher_id, p.name AS publisher_name,"
        " p.feed_url, p.site_url"
        " FROM stories s JOIN publishers p ON s.publisher_id=p.id"
        " WHERE s.category_id=%s AND NOT s.has_image"
        " ORDER BY s.created_at DESC LIMIT %s"
    )
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (category_id, DB_BATCH_SIZE))
            rows = await cur.fetchall()
    stories = []
    for row in rows:
        pub = {
            k.replace("publisher_", ""): row[k]
            for k in row
            if k.startswith("publisher_")
        }
        data = {k: row[k] for k in row if not k.startswith("publisher_")}
        data["publisher"] = pub
        stories.append(data)
    return stories


async def update_story_images(pool, ids):
    if not ids:
        return
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.executemany(
                "UPDATE stories SET has_image=1 WHERE id=%s", [(i,) for i in ids]
            )
        await conn.commit()


async def update_favicons(pool, items):
    if not items:
        return
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.executemany(
                "UPDATE publishers SET favicon_url=%s WHERE id=%s", items
            )
        await conn.commit()


async def fetch_url(session, url):
    proxy = await get_proxy()
    proxy_url = f"http://{proxy}" if proxy else None
    try:
        async with http_sem, session.get(url, timeout=5, proxy=proxy_url) as resp:
            if resp.status in (200, 301, 302):
                return await resp.read(), resp
            logger.warning(f"Bad HTTP status {resp.status} for {url}")
    except aiohttp.ClientProxyConnectionError:
        await mark_bad(proxy)
    except Exception as e:
        logger.warning(f"Error fetching {url}: {e}")
    return None, None


def parse_meta(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    og = soup.find("meta", property="og:image")
    story_url = og["content"].strip() if og and og.get("content") else DEFAULT_IMAGE
    icon = soup.find("link", rel=lambda x: x and "icon" in x)
    fav_url = icon["href"] if icon and icon.get("href") else "/favicon.ico"
    if not input_sanitization.is_valid_url(fav_url):
        fav_url = urljoin(base_url, fav_url)
    return story_url, fav_url


async def convert_and_upload(kind, content, meta, s3_client, pool):
    # Convert in threadpool if needed
    loop = asyncio.get_event_loop()

    def _convert():
        img = pyvips.Image.new_from_buffer(content, "")
        if kind == "story":
            img = img.thumbnail_image(1280)
            buf = img.write_to_buffer(".avif[quality=60]")
            key = f"{meta['output']}.avif"
        else:
            img = img.thumbnail_image(32)
            buf = img.write_to_buffer(".ico")
            key = f"{meta['output']}.ico"
        return key, buf

    key, buf = await loop.run_in_executor(None, _convert)
    # Upload
    async with s3_sem:
        try:
            await s3_client.put_object(Bucket=S3_BUCKET, Key=key, Body=buf)
            return key
        except Exception as e:
            logger.error(f"S3 upload failed for {key}: {e}")
    return None


async def process_story(story, session, s3_client, pool, story_ids, favicon_items):
    html_bytes, resp = await fetch_url(session, story["url"])
    if not html_bytes:
        return
    img_url, fav_url = parse_meta(html_bytes, story["url"])
    tasks = []
    if img_url:
        tasks.append(
            convert_and_upload(
                "story",
                (await fetch_url(session, img_url))[0],
                {
                    "output": f"stories/{story['publisher']['name']}/{hashing_util.binary_to_md5_hex(story['url_hash'])}"
                },
                s3_client,
                pool,
            )
        )
        story_ids.append(story["id"])
    if not story["publisher"]["favicon_url"] and fav_url:
        tasks.append(
            convert_and_upload(
                "favicon",
                (await fetch_url(session, fav_url))[0],
                {
                    "output": f"favicons/{story['publisher']['name']}/{story['publisher']['id']}"
                },
                s3_client,
                pool,
            )
        )
        favicon_items.append((f"{S3_BASE_URL}/%s", story["publisher"]["id"]))
    await asyncio.gather(*tasks)


async def process_category(cat, session, s3_client, pool):
    stories = await fetch_stories(pool, cat["id"])
    if not stories:
        return
    story_ids, favicon_items = [], []
    workers = [
        process_story(story, session, s3_client, pool, story_ids, favicon_items)
        for story in stories
    ]
    await asyncio.gather(*workers)
    await update_story_images(pool, story_ids)
    await update_favicons(pool, favicon_items)
    logger.info(f"Processed category {cat['name']} with {len(story_ids)} images.")


async def main():
    loop = asyncio.get_event_loop()
    pool = await init_db_pool(loop)
    s3_client = await init_s3_client()
    async with aiohttp.ClientSession() as session:
        cats = await fetch_categories(pool)
        for cat in cats:
            await process_category(cat, session, s3_client, pool)
    await pool.wait_closed()
    await s3_client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown via KeyboardInterrupt")
        sys.exit(0)
