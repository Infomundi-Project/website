import feedparser
import threading
import logging
import pymysql
import requests
import yake

from concurrent.futures import ThreadPoolExecutor, as_completed
from random import shuffle
from urllib.parse import urljoin, urlparse
from datetime import datetime
from bs4 import BeautifulSoup

from website_scripts import (
    config,
    input_sanitization,
    immutable,
    hashing_util,
    qol_util,
)

# =============================================================================
# Performance & Robustness Enhancements
# =============================================================================
# - Session pooling with retries & keep-alive
# - Conditional GETs with ETag/Last-Modified (persisted per publisher)
# - Bounded thread pool
# - Entry cap per feed
# - YAKE extractor cache + short-text gate
# - Faster feed discovery + content sniffing (XML + JSON Feed)
# - Chunked multi-VALUES inserts; optional temp-table join for tags
# - De-dup within batch prior to DB

import re
import json
from typing import List, Optional, Iterable

from requests.adapters import HTTPAdapter, Retry

# ---- Tunables ---------------------------------------------------------------
RSS_TIMEOUT = (3, 8)  # (connect, read)
MAX_BYTES_TO_SNIFF = 4096
MAX_CANDIDATES = 50
MAX_WORKERS = 48
MAX_ENTRIES_PER_FEED = 50
YAKE_MIN_LEN = 120
TAG_INSERT_CHUNK = 1000
STORY_INSERT_CHUNK = 1000

_FEED_HINT_RE = re.compile(
    r"(rss|atom|feed|rdf|xml|\.rss|\.atom|\.xml)(?:[?#].*)?$",
    re.IGNORECASE,
)
_JSON_FEED_VERSION_RE = re.compile(r"https?://jsonfeed\.org/version", re.I)

# Canonical CMS endpoints to try (relative paths)
CANONICAL_ENDPOINTS: List[str] = [
    # Generic
    "feed",
    "feed/",
    "rss",
    "rss/",
    "rss.xml",
    "feed.xml",
    "index.xml",
    "atom.xml",
    "blog/rss",
    "blog/rss/",
    "blog/feed",
    "blog/feed/",
    "posts.rss",
    "posts.atom",
    "posts.xml",
    # WordPress
    "?feed=rss2",
    "?feed=atom",
    "feed/",
    "comments/feed/",
    "category/news/feed/",
    "tag/news/feed/",
    # Ghost
    "rss/",
    "rss/index.xml",
    # Jekyll/Hugo/Static
    "feed.xml",
    "index.xml",
    "rss.xml",
    "atom.xml",
    # Medium
    "feed",
    "publication/feed",
    # Blogger
    "feeds/posts/default?alt=rss",
    "feeds/posts/default",
    "feeds/posts/default?alt=atom",
    # Tumblr
    "rss",
    # Substack
    "feed",
    "feed.xml",
    # Squarespace
    "?format=rss",
    "blog?format=rss",
    # Drupal
    "rss.xml",
    "?q=taxonomy/term/1/0/feed",
    # Shopify (common blog handles)
    "blogs/news.atom",
    "blogs/news.rss",
    # Joomla
    "?format=feed&type=rss",
    "?format=feed&type=atom",
    # Wix
    "blog-feed.xml",
    "feed.xml",
]

# =============================================================================
# HTTP session pooling
# =============================================================================
_tls = threading.local()


def get_session() -> requests.Session:
    s = getattr(_tls, "session", None)
    if s is not None:
        return s
    s = requests.Session()
    retries = Retry(
        total=2,
        backoff_factor=0.25,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(pool_connections=128, pool_maxsize=128, max_retries=retries)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    ua = (
        getattr(immutable, "USER_AGENTS", None) and immutable.USER_AGENTS[0]
    ) or "Mozilla/5.0"
    s.headers.update(
        {
            "User-Agent": ua,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, application/feed+json, text/xml, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.google.com/",
            "Connection": "keep-alive",
        }
    )
    _tls.session = s
    return s


def _request(
    url: str,
    method: str = "GET",
    timeout: tuple = RSS_TIMEOUT,
    headers: Optional[dict] = None,
) -> Optional[requests.Response]:
    try:
        sess = get_session()
        resp = sess.request(
            method, url, timeout=timeout, headers=headers, allow_redirects=True
        )
        return resp
    except requests.RequestException:
        return None


# =============================================================================
# Discovery & parsing helpers (XML + JSON Feed)
# =============================================================================


def _looks_like_feed_bytes(blob: bytes) -> bool:
    head = blob[:MAX_BYTES_TO_SNIFF].lstrip()
    return (
        head.startswith(b"<?xml")
        or b"<rss" in head
        or b"<feed" in head
        or b"<rdf:RDF" in head
        or _JSON_FEED_VERSION_RE.search(head.decode("utf-8", "ignore")) is not None
    )


def _parse_json_feed(content: bytes):
    try:
        data = json.loads(content.decode("utf-8", "ignore"))
    except Exception:
        return None

    def FP(**kwargs):
        return feedparser.FeedParserDict(kwargs)

    feed_info = FP(
        title=data.get("title"),
        link=data.get("home_page_url")
        or data.get("feed_url")
        or data.get("description"),
    )

    entries = []
    for item in data.get("items", [])[:MAX_ENTRIES_PER_FEED]:
        desc = (
            item.get("content_html") or item.get("content_text") or item.get("summary")
        )
        author = None
        if isinstance(item.get("author"), dict):
            author = item["author"].get("name")
        elif item.get("authors") and isinstance(item["authors"], list):
            a0 = item["authors"][0]
            if isinstance(a0, dict):
                author = a0.get("name")
        tags = []
        for t in item.get("tags", []) or []:
            if isinstance(t, str):
                tags.append(FP(term=t))
            elif isinstance(t, dict):
                name = t.get("name") or t.get("term")
                if name:
                    tags.append(FP(term=name))
        entries.append(
            FP(
                title=item.get("title"),
                link=item.get("url") or item.get("external_url"),
                description=desc,
                summary=item.get("summary"),
                author=author,
                published=item.get("date_published"),
                updated=item.get("date_modified"),
                tags=tags,
            )
        )

    return feedparser.FeedParserDict({"feed": feed_info, "entries": entries, "bozo": 0})


def _parse_if_feed(url: str, resp: requests.Response):
    ct = (resp.headers.get("Content-Type") or "").lower()
    content = resp.content or b""

    if "application/feed+json" in ct or (
        ct.startswith("application/json") and _looks_like_feed_bytes(content)
    ):
        parsed = _parse_json_feed(content)
        if parsed and parsed.get("entries") is not None:
            return parsed

    if any(fmt in ct for fmt in ["rss", "atom", "xml"]) or _looks_like_feed_bytes(
        content
    ):
        parsed = feedparser.parse(content)
        if getattr(parsed, "bozo", 0) == 0 or parsed.entries:
            return parsed
    return None


def _extract_feed_links_from_html(base_url: str, html: str) -> List[str]:
    out: List[str] = []
    # Prefer lxml if available for speed
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # <link> hints
    for link in soup.find_all("link"):
        rels = " ".join([*(link.get("rel") or [])]).lower()
        typ = (link.get("type") or "").lower()
        href = link.get("href")
        title = (link.get("title") or "").lower()
        if not href:
            continue
        if (
            "alternate" in rels
            or "feed" in rels
            or any(t in typ for t in ["rss", "atom", "xml", "json"])
            or any(k in title for k in ["rss", "atom", "feed"])
        ):
            out.append(urljoin(base_url, href))

    # <a> fallbacks
    for a in soup.find_all("a", href=True)[:5000]:
        href = a["href"].strip()
        txt = (a.get_text(" ") or "").lower()
        if _FEED_HINT_RE.search(href) or any(k in txt for k in ["rss", "atom", "feed"]):
            out.append(urljoin(base_url, href))

    # JSON-LD hints
    for s in soup.find_all("script", attrs={"type": re.compile("json", re.I)}):
        try:
            data = json.loads(s.string or "{}")
        except Exception:
            continue
        stack = (
            [data]
            if isinstance(data, dict)
            else (list(data) if isinstance(data, list) else [])
        )
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                url = node.get("url") or node.get("@id")
                if isinstance(url, str) and _FEED_HINT_RE.search(url):
                    out.append(urljoin(base_url, url))
                if node.get("@type") in ("DataFeed", "Blog", "CollectionPage"):
                    for k in ("url", "mainEntityOfPage", "sameAs"):
                        v = node.get(k)
                        if isinstance(v, str) and _FEED_HINT_RE.search(v):
                            out.append(urljoin(base_url, v))
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)

    # De-dup
    seen, uniq = set(), []
    for u in out:
        ru = (u or "").split("#")[0]
        if ru and ru not in seen:
            seen.add(ru)
            uniq.append(ru)
    return uniq[:MAX_CANDIDATES]


def _candidate_endpoints(base_url: str) -> List[str]:
    base = base_url.rstrip("/") + "/"
    cands: List[str] = []

    for rel in CANONICAL_ENDPOINTS:
        if "*" in rel:
            continue
        cands.append(urljoin(base, rel))

    for leaf in [
        "feed",
        "feed/",
        "rss",
        "rss/",
        "rss.xml",
        "feed.xml",
        "index.xml",
        "atom.xml",
    ]:
        cands.append(urljoin(base, leaf))

    parts = urlparse(base)
    if parts.path.strip("/"):
        parent = base.rsplit("/", 2)[0] + "/"
        for leaf in ["feed", "rss", "feed.xml", "index.xml"]:
            cands.append(urljoin(parent, leaf))

    seen, uniq = set(), []
    for u in cands:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def _score_feed_url(url: str) -> int:
    score = 0
    u = url.lower()
    if any(
        x in u
        for x in ("/feed", "/rss", "rss.xml", "feed.xml", "atom.xml", "/index.xml")
    ):
        score += 5
    if any(
        x in u
        for x in (
            "wordpress",
            "ghost",
            "blogger",
            "tumblr",
            "substack",
            "squarespace",
            "drupal",
            "joomla",
            "shopify",
            "wix",
        )
    ):
        score += 2
    if u.endswith((".xml", ".rss", ".atom")):
        score += 2
    if "?feed=" in u or "format=rss" in u:
        score += 2
    return score


def find_feed_candidates(base_or_feed_url: str) -> List[str]:
    """Return prioritized list of candidate feed URLs without fetching them first."""
    # Start with the provided URL as-is (maybe it's already a feed URL)
    cands = [base_or_feed_url]

    # Discover from site root
    parsed = urlparse(base_or_feed_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    base_for_discovery = origin if parsed.path.count("/") <= 1 else f"{origin}/"

    resp = _request(base_for_discovery, "GET")
    html_candidates: List[str] = []
    if resp is not None and getattr(resp, "status_code", 0) == 200 and resp.text:
        html_candidates = _extract_feed_links_from_html(base_for_discovery, resp.text)

    endpoint_candidates = _candidate_endpoints(base_for_discovery)
    merged = list({*cands, *html_candidates, *endpoint_candidates})
    merged.sort(key=_score_feed_url, reverse=True)
    return merged[:MAX_CANDIDATES]


# =============================================================================
# Conditional GETs
# =============================================================================


def fetch_with_conditional(url: str, etag: Optional[str], last_modified: Optional[str]):
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    resp = _request(url, "GET", headers=headers)
    if resp is None:
        return None, None, None
    new_etag = resp.headers.get("ETag")
    new_lastmod = resp.headers.get("Last-Modified")
    return resp, new_etag, new_lastmod


# =============================================================================
# Database connection & logging
# =============================================================================

db_params = {
    "host": "127.0.0.1",
    "user": config.MYSQL_USERNAME,
    "password": config.MYSQL_PASSWORD,
    "db": config.MYSQL_DATABASE,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

db_connection = pymysql.connect(**db_params)

logging.basicConfig(
    filename=f"{config.LOCAL_ROOT}/logs/create_cache.log",
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
)

# YAKE extractor cache
_yake_cache = {}


def extract_yake(text: str, lang_code: str = "en", top_n: int = 5):
    ex = _yake_cache.get((lang_code, top_n))
    if not ex:
        ex = yake.KeywordExtractor(lan=lang_code, n=2, top=top_n)
        _yake_cache[(lang_code, top_n)] = ex
    return [kw for kw, _ in ex.extract_keywords(text)]


def log_message(message):
    print(f"[~] {message}")
    # logging.info(message)


# =============================================================================
# DB helpers (chunked inserts, temp-table join for tags)
# =============================================================================


def _chunk(seq: List, size: int) -> Iterable[List]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _multi_values_insert(
    cursor, table: str, cols: List[str], rows: List[tuple], chunk: int = 1000
):
    if not rows:
        return
    prefix = f"INSERT IGNORE INTO {table} (" + ",".join(cols) + ") VALUES "
    placeholders = "(" + ",".join(["%s"] * len(cols)) + ")"
    for part in _chunk(rows, chunk):
        sql = prefix + ",".join([placeholders] * len(part))
        flat = [v for row in part for v in row]
        cursor.execute(sql, flat)


def insert_stories_to_database(stories, category_name, category_id):
    """Bulk-insert stories and tags with fewer round-trips. Returns #exceptions."""
    exceptions = 0

    # De-duplicate stories within the batch by url_hash (keep first occurrence)
    uniq_map = {}
    for s in stories:
        uniq_map.setdefault(s["story_url_hash"], s)
    stories = list(uniq_map.values())

    try:
        with db_connection.cursor() as cursor:
            # 1) Bulk insert stories (chunked multi-VALUES)
            story_rows = [
                (
                    s["story_title"],
                    s["story_lang"],
                    s["story_author"],
                    s["story_description"],
                    s["story_url"],
                    s["story_url_hash"],
                    s["story_pubdate"],
                    category_id,
                    s["publisher_id"],
                )
                for s in stories
            ]
            _multi_values_insert(
                cursor,
                "stories",
                [
                    "title",
                    "lang",
                    "author",
                    "description",
                    "url",
                    "url_hash",
                    "pub_date",
                    "category_id",
                    "publisher_id",
                ],
                story_rows,
                chunk=STORY_INSERT_CHUNK,
            )

            # 2) Map url_hash -> id (single query)
            url_hashes = tuple(s["story_url_hash"] for s in stories)
            if not url_hashes:
                db_connection.commit()
                return 0
            if len(url_hashes) == 1:
                url_hashes = (url_hashes[0], url_hashes[0])
            cursor.execute(
                "SELECT id, url_hash FROM stories WHERE url_hash IN %s",
                (url_hashes,),
            )
            id_map = {row["url_hash"]: row["id"] for row in cursor.fetchall()}

            # 3) Prepare (url_hash, tag) pairs (de-dup)
            tag_pairs = set()
            for s in stories:
                for tag in s.get("story_tags", []) or []:
                    t = (s["story_url_hash"], (tag or "").strip())
                    if t[1]:
                        tag_pairs.add(t)

            # 4) Fast path: temp table join (falls back to executemany)
            used_temp = False
            if tag_pairs:
                try:
                    cursor.execute(
                        "CREATE TEMPORARY TABLE tmp_tags (url_hash BINARY(16), tag VARCHAR(255)) ENGINE=MEMORY"
                    )
                    tmp_rows = list(tag_pairs)
                    _multi_values_insert(
                        cursor,
                        "tmp_tags",
                        ["url_hash", "tag"],
                        tmp_rows,
                        chunk=TAG_INSERT_CHUNK,
                    )
                    cursor.execute(
                        """
                        INSERT IGNORE INTO tags (story_id, tag)
                        SELECT s.id, t.tag
                        FROM stories s
                        JOIN tmp_tags t ON t.url_hash = s.url_hash
                        """
                    )
                    used_temp = True
                except Exception:
                    used_temp = False

                if not used_temp:
                    tag_rows = []
                    for h, tag in tag_pairs:
                        sid = id_map.get(h)
                        if sid:
                            tag_rows.append((sid, tag))
                    _multi_values_insert(
                        cursor,
                        "tags",
                        ["story_id", "tag"],
                        tag_rows,
                        chunk=TAG_INSERT_CHUNK,
                    )

            db_connection.commit()
    except Exception as e:
        db_connection.rollback()
        log_message(f"Error bulk inserting stories/tags: {e}")
        exceptions += 1

    return exceptions


# =============================================================================
# Publisher HTTP cache (ETag / Last-Modified)
# =============================================================================


def update_publisher_http_cache(
    publisher_id: int, etag: Optional[str], last_modified: Optional[str]
):
    if not (etag or last_modified):
        return
    try:
        with db_connection.cursor() as cursor:
            # Columns must exist: publishers.etag VARCHAR(255), publishers.last_modified VARCHAR(255)
            cursor.execute(
                "UPDATE publishers SET etag = COALESCE(%s, etag), last_modified = COALESCE(%s, last_modified) WHERE id = %s",
                (etag, last_modified, publisher_id),
            )
        db_connection.commit()
    except Exception as e:
        # Silently ignore if columns don't exist; log for awareness
        log_message(
            f"[warn] Could not update ETag/Last-Modified for publisher {publisher_id}: {e}"
        )


# =============================================================================
# Fetch & transform
# =============================================================================


def fetch_feed(publisher: dict, news_filter: str, result_list: list):
    """Fetch feed with discovery + conditional GET; append parsed items to result_list."""
    publisher_url = publisher.get("feed_url") or publisher.get("site_url")
    if not input_sanitization.is_valid_url(publisher_url):
        log_message(f"Invalid url: {publisher_url}")
        return {}

    if publisher_url.endswith("/"):
        publisher_url = publisher_url[:-1]

    # Discover candidates, then try conditional GET + parse in priority order
    etag = publisher.get("etag")
    last_mod = publisher.get("last_modified")

    feed = None
    resolved_url = None
    not_modified = False

    try:
        candidates = find_feed_candidates(publisher_url)
        for cand in candidates:
            resp, new_etag, new_lastmod = fetch_with_conditional(cand, etag, last_mod)
            if resp is None:
                continue
            if resp.status_code == 304:
                # No updates for this publisher; keep cache fresh and stop
                update_publisher_http_cache(publisher["id"], new_etag, new_lastmod)
                not_modified = True
                break
            if resp.status_code != 200:
                continue
            parsed = _parse_if_feed(cand, resp)
            if parsed:
                feed = parsed
                resolved_url = cand
                # Save fresh validators
                update_publisher_http_cache(publisher["id"], new_etag, new_lastmod)
                break
    except Exception as e:
        log_message(f"Exception while resolving feed for {publisher_url}: {e}")
        feed, resolved_url = None, None

    if not feed:
        if not_modified:
            log_message(f"Not modified: {publisher.get('name') or publisher_url}")
        else:
            log_message(f"Could not find feed for {publisher_url}, skipping...")
        return {}

    try:
        data = {
            "title": (getattr(feed.feed, "title", None) or "Unknown Publisher").strip()
            if getattr(feed, "feed", None)
            else "Unknown Publisher",
            "link": (
                getattr(feed.feed, "link", None) or resolved_url or publisher_url or ""
            ).strip(),
            "items": [],
        }

        for story in feed.entries[:MAX_ENTRIES_PER_FEED]:
            story_title = input_sanitization.sanitize_html(
                input_sanitization.decode_html_entities(story.get("title"))
            )
            story_description = input_sanitization.sanitize_html(
                input_sanitization.decode_html_entities(
                    story.get("description") or story.get("summary")
                )
            )

            story_author = input_sanitization.sanitize_html(
                input_sanitization.decode_html_entities(story.get("author"))
            )
            if story_author == "None":
                story_author = None

            if not story_title:
                continue

            story_title = input_sanitization.gentle_cut_text(250, story_title)
            story_description = input_sanitization.gentle_cut_text(
                500, story_description
            )

            # Categories/tags normalization
            raw_tags = story.get("tags", []) or []
            story_categories = []
            for t in raw_tags:
                term = None
                if isinstance(t, dict):
                    term = t.get("term") or t.get("label") or t.get("name")
                if not term and hasattr(t, "term"):
                    term = getattr(t, "term")
                if term:
                    story_categories.append(term)

            story_url = story.get("link")
            if not input_sanitization.is_valid_url(story_url) or len(story_url) > 512:
                continue

            pubdate = (
                story.get("published_parsed")
                or story.get("published")
                or story.get("updated")
            )
            story_pubdate = format_date(pubdate).get(
                "datetime", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            # Language: trust publisher default if present
            story_lang = publisher.get("lang") or qol_util.detect_language(
                f"{story_title} {story_description}"
            )

            # YAKE: skip tiny blurbs
            combined = f"{story_title} {story_description}".strip()
            story_tags = (
                extract_yake(combined, lang_code=story_lang)
                if len(combined) >= YAKE_MIN_LEN
                else []
            )

            new_story = {
                "story_title": story_title,
                "story_categories": story_categories,
                "story_tags": story_tags,
                "story_lang": story_lang,
                "story_author": story_author,
                "story_description": story_description,
                "story_pubdate": story_pubdate,
                "story_url_hash": hashing_util.string_to_md5_binary(story_url),
                "story_url": story_url,
                "publisher_id": publisher["id"],
            }

            data["items"].append(new_story)

    except Exception as err:
        log_message(f"Exception getting {publisher_url} ({news_filter}) // {err}")
        data = {}

    log_message(
        f"Successfully processed feed for {publisher.get('name') or data.get('title') or publisher_url}!"
    )
    result_list.append(data)


# =============================================================================
# Date handling
# =============================================================================


def format_date(date) -> dict:
    """Converts struct_time, ISO/RFC strings, or datetime into MySQL DATETIME string."""
    from time import struct_time

    if isinstance(date, str):
        try:
            from email.utils import parsedate_to_datetime

            try:
                dt = parsedate_to_datetime(date)
            except Exception:
                dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
            return {"datetime": dt.strftime("%Y-%m-%d %H:%M:%S")}
        except Exception:
            return {"error": "Invalid date format"}

    if isinstance(date, tuple):
        try:
            date = datetime(*date[:6])
        except Exception:
            return {"error": "Invalid date format"}

    if isinstance(date, datetime):
        return {"datetime": date.strftime("%Y-%m-%d %H:%M:%S")}

    if isinstance(date, struct_time):
        try:
            date = datetime(*date[:6])
            return {"datetime": date.strftime("%Y-%m-%d %H:%M:%S")}
        except Exception:
            return {"error": "Invalid date format"}

    return {"error": "Invalid date format"}


# =============================================================================
# DB fetchers
# =============================================================================


def fetch_categories_from_database():
    log_message("Fetching categories from the database")
    try:
        with db_connection.cursor() as cursor:
            cursor.execute("SELECT * FROM categories")
            categories = cursor.fetchall()
    except Exception as e:
        log_message(f"Error fetching categories: {e}")
        return []

    category_list = [(row["id"], row["name"]) for row in categories]
    shuffle(category_list)

    log_message(f"Got {len(category_list)} categories from the database")
    return category_list


def fetch_publishers_from_database(category_id: int):
    log_message(f"Fetching publishers for category ID: {category_id}")
    try:
        with db_connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM publishers WHERE category_id = %s",
                (category_id,),
            )
            publishers = cursor.fetchall()
    except Exception as e:
        log_message(f"Error fetching publishers: {e}")
        return []

    log_message(f"Got {len(publishers)} publishers from the database")
    return publishers


# =============================================================================
# Main
# =============================================================================


def main():
    total_done = 0
    categories = fetch_categories_from_database()

    for category_id, category_name in categories:
        percentage = (total_done / max(len(categories), 1)) * 100
        log_message(f"[{round(percentage, 2)}%] Handling {category_name}...")

        result_list = []
        publishers = fetch_publishers_from_database(category_id)

        # Bounded thread pool
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = [
                ex.submit(fetch_feed, publisher, category_name, result_list)
                for publisher in publishers
            ]
            for _ in as_completed(futures):
                pass

        # Merge all articles
        merged_articles = []
        for rss_data in result_list:
            if not rss_data:
                continue
            merged_articles.extend(rss_data["items"])

        if not merged_articles:
            log_message(f"[-] Empty cache: {category_name}")
            total_done += 1
            continue

        shuffle(merged_articles)

        exceptions_count = insert_stories_to_database(
            merged_articles, category_name, category_id
        )
        total_done += 1

        log_message(
            f"[{len(merged_articles) - exceptions_count} articles] Saved for {category_name}."
        )

    log_message("Finished!")


if __name__ == "__main__":
    main()
