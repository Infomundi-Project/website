#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backfill_feed_urls.py — Find and store real RSS/Atom feed URLs for publishers missing feed_url.

- Uses your rss_finder_i18n.py discovery+validation logic (no generated feeds).
- Respects your default user-agent and timeouts inside the finder.
- Safe to run multiple times; only updates rows with NULL/empty feed_url.

Usage:
  pip install pymysql requests beautifulsoup4
  python backfill_feed_urls.py --workers 8 --dry-run   # preview only
  python backfill_feed_urls.py --workers 8             # write updates
"""

import argparse
import sys
import threading
from typing import Optional, Tuple, List

import pymysql

# Import your finder module (must be importable on PYTHONPATH or same folder)
import rss_finder_i18n as finder

# ---- DB helpers -------------------------------------------------------------


def get_db_connection():
    # Uses your exact pattern; requires a config module with credentials.
    from website_scripts import config  # noqa: F401 (must exist in your project)

    db_params = {
        "host": config.MYSQL_HOST,
        "user": config.MYSQL_USERNAME,
        "password": config.MYSQL_PASSWORD,
        "db": config.MYSQL_DATABASE,
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
    }
    return pymysql.connect(**db_params)


def fetch_publishers_missing_feed(conn, limit: Optional[int] = None) -> List[dict]:
    sql = """
        SELECT id, name, site_url
        FROM publishers
        WHERE (feed_url IS NULL OR feed_url = '')
          AND site_url IS NOT NULL AND site_url <> ''
        ORDER BY id ASC
        LIMIT 10
    """
    if limit is not None:
        sql += " LIMIT %s"
        args = (limit,)
    else:
        args = ()
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def update_feed_url(conn, pub_id: int, feed_url: str):
    sql = "UPDATE publishers SET feed_url=%s WHERE id=%s"
    with conn.cursor() as cur:
        cur.execute(sql, (feed_url, pub_id))


# ---- Feed discovery using your finder --------------------------------------

DEFAULT_UA = finder.DEFAULT_UA  # reuse your UA string


def normalize_root(url: str) -> Optional[str]:
    try:
        return finder._norm_url(url)  # your helper; raises on bad URL
    except Exception:
        return None


def discover_valid_feed(root_url: str) -> Optional[str]:
    """
    Return the first valid feed URL for root_url, or None.
    Only accepts *existing* feeds discovered by your logic.
    """
    s = finder._session(DEFAULT_UA)  # fresh requests.Session with UA
    root = normalize_root(root_url)
    if not root:
        return None

    candidates = finder.discover_feeds(root, s)
    # Try each candidate; accept only those that validate and whose entries live on same domain
    for cand in candidates:
        ok, _ftype = finder.validate_feed(cand, s, root)
        if ok:
            return cand
    return None


# ---- Worker logic (optional concurrency) -----------------------------------


def process_one(
    pub_row: dict, verbose: bool = False
) -> Tuple[int, Optional[str], Optional[str]]:
    """
    Returns (publisher_id, site_url, found_feed_url or None)
    """
    pub_id = pub_row["id"]
    site = pub_row.get("site_url") or ""
    feed = None
    if site:
        try:
            feed = discover_valid_feed(site)
        except Exception as e:
            if verbose:
                print(f"[warn] id={pub_id} site={site} error={e}", file=sys.stderr)
    if verbose:
        print(f"[check] id={pub_id} site={site} -> feed={feed}", file=sys.stderr)
    return pub_id, site, feed


# ---- Main -------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(
        description="Backfill publishers.feed_url using rss_finder_i18n discovery."
    )
    ap.add_argument(
        "--limit", type=int, default=None, help="Max number of publishers to process"
    )
    ap.add_argument(
        "--workers", type=int, default=8, help="Concurrency for network checks"
    )
    ap.add_argument("--dry-run", action="store_true", help="Do not write DB updates")
    ap.add_argument("--verbose", action="store_true", help="Verbose logging to stderr")
    args = ap.parse_args()

    conn = get_db_connection()
    pubs = fetch_publishers_missing_feed(conn, args.limit)
    total = len(pubs)
    if args.verbose:
        print(f"[start] candidates={total}", file=sys.stderr)

    # Concurrency: thread pool, but we’ll keep DB writes on the main thread.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: List[Tuple[int, Optional[str], Optional[str]]] = []

    # Protect stdout/stderr formatting in verbose mode
    print_lock = threading.Lock()

    def _task(row):
        res = process_one(row, verbose=args.verbose)
        # serialize logs if needed
        if args.verbose:
            with print_lock:
                pass
        return res

    if args.workers and args.workers > 1:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(_task, r) for r in pubs]
            for f in as_completed(futs):
                results.append(f.result())
    else:
        for r in pubs:
            results.append(_task(r))

    # Apply updates
    updated = 0
    for pub_id, _site, feed in results:
        if not feed:
            continue
        if args.dry_run:
            print(
                f"[dry-run] UPDATE publishers SET feed_url='{feed}' WHERE id={pub_id};"
            )
        else:
            update_feed_url(conn, pub_id, feed)
            updated += 1

    if not args.dry_run:
        conn.commit()
    conn.close()

    # Summary
    print(
        f"Processed: {total} | Found feeds: {sum(1 for _, _, f in results if f)} | Updated: {updated}{' (dry-run)' if args.dry_run else ''}"
    )


if __name__ == "__main__":
    main()
