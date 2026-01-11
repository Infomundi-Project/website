import csv
import re
from urllib.parse import urlparse, urlunparse
from pathlib import PurePosixPath
from difflib import SequenceMatcher
import pymysql

from website_scripts import config

# Database connection parameters
db_params = {
    "host": config.MYSQL_HOST,
    "user": config.MYSQL_USERNAME,
    "password": config.MYSQL_PASSWORD,
    "db": config.MYSQL_DATABASE,
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

db_connection = pymysql.connect(**db_params)

# ---------------- helpers ----------------


def normalize_url(url: str) -> str | None:
    if not url:
        return None
    u = url.strip()
    if not u:
        return None
    if "://" not in u:
        u = "http://" + u
    p = urlparse(u)
    if not p.netloc:
        return None
    scheme = (p.scheme or "http").lower()
    netloc = p.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]
    path = p.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunparse((scheme, netloc, path, "", "", ""))


def slug_from_source(src: str) -> str | None:
    if not src:
        return None
    name = PurePosixPath(urlparse(src).path).name.lower()
    return name[:-4] if name.endswith(".htm") else (name or None)


def split_slug(slug: str | None):
    """Returns (base_slug, state_candidate) where state_candidate is last 2 letters if present.
    '...na' -> national => state_candidate=None."""
    if not slug:
        return (None, None)
    if slug.endswith("na"):
        return (slug[:-2], None)  # national
    m = re.search(r"([a-z]{2})$", slug)
    if m:
        return (slug[:-2], m.group(1).upper())  # subnational (2-letter code)
    return (slug, None)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def category_key(iso2: str | None, state_code: str | None) -> str:
    """<iso2>_<state-or-na>_general, lowercase, trimmed to VARCHAR(15)."""
    cc = (iso2 or "XX").lower()
    seg = (state_code or "NA").lower()
    key = f"{cc}_{seg}_general"
    return key[:15]  # keep within current categories.name (VARCHAR(15))


# ------------- preload countries & states once -------------


def load_country_dict(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, iso2, iso3, tld FROM countries")
        rows = cur.fetchall()
    # map ccTLD last label -> iso2 (handles '.br', '.uk', lists)
    tld2iso = {}
    for r in rows:
        tlds = (r.get("tld") or "").lower()
        parts = re.split(r"[\s,;]+", tlds)
        for t in parts:
            t = t.strip(". ")
            if len(t) == 2:
                tld2iso[t] = r["iso2"] or r["iso2"]
    # just in case the tld list lacks 'uk'
    tld2iso.setdefault("uk", "GB")
    return {
        "rows": rows,
        "tld2iso": tld2iso,
        "name_keys": [
            (r["id"], r["iso2"] or "", r["iso3"] or "", norm(r["name"])) for r in rows
        ],
    }


def load_state_codes(conn):
    """Build { 'BR': {'AC','AL',...}, 'US': {...}, ... } from states(country_code, iso2)."""
    with conn.cursor() as cur:
        cur.execute("SELECT country_code, iso2 FROM states")
        rows = cur.fetchall()
    by_country = {}
    for r in rows:
        cc = (r["country_code"] or "").upper()
        sc = (r["iso2"] or "").upper()
        if not cc or not sc:
            continue
        by_country.setdefault(cc, set()).add(sc)
    return by_country


def resolve_iso2(country_dict, host: str, source_page: str) -> str | None:
    # tld first
    last = host.split(".")[-1].lower() if host else ""
    if len(last) == 2 and last in country_dict["tld2iso"]:
        return country_dict["tld2iso"][last]

    # slug fallback with fuzzy match against DB names/iso codes
    slug = slug_from_source(source_page)
    base, _state = split_slug(slug)
    b = norm(base or "")
    if not b:
        return None

    best_iso2, best = None, 0.0
    for _id, iso2, iso3, cname in country_dict["name_keys"]:
        score = 0.0
        if b == iso2.lower() or b.startswith(iso2.lower()):
            score = 0.96
        if iso3 and (b == iso3.lower() or b.startswith(iso3.lower())):
            score = max(score, 0.92)
        score = max(score, SequenceMatcher(None, b, cname).ratio())
        if score > best:
            best, best_iso2 = score, iso2
    return best_iso2 if best >= 0.52 else None


def resolve_state_code(
    states_by_country, iso2: str | None, source_page: str
) -> str | None:
    """Extract 2-letter state candidate from slug and validate against DB for that country."""
    if not iso2:
        return None
    slug = slug_from_source(source_page) or ""
    _base, cand = split_slug(slug)
    if not cand:
        return None
    valid = states_by_country.get(iso2.upper(), set())
    return cand if cand in valid else None


# ------------- main pipeline: recategorize + insert -------------


def recategorize_and_import_from_csv(conn, csv_path="/root/e.csv", batch_size=5000):
    """
    1) Stage all CSV rows (site_url, iso2, state_code, category_name, name).
    2) CREATE missing categories (state-aware).
    3) UPDATE existing publishers -> set category_id by (site_url -> category_name).
    4) INSERT any new publishers with the correct category_id.
    """
    country_dict = load_country_dict(conn)
    states_by_country = load_state_codes(conn)

    # Deduplicate within CSV to cut work
    staged = {}
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("anchor_text") or "").strip()
            if not name:
                continue
            site_url = normalize_url(row.get("external_url") or "")
            if not site_url:
                continue
            if site_url in staged:
                continue

            source_page = (row.get("source_page") or "")[:255]
            host = urlparse(site_url).hostname or ""
            iso2 = resolve_iso2(country_dict, host, source_page) or "XX"
            state_code = resolve_state_code(states_by_country, iso2, source_page)
            cat_name = category_key(iso2, state_code)

            staged[site_url] = (
                name[:150],
                site_url,
                source_page,
                iso2[:2],
                (state_code or ""),
                cat_name,
            )

    if not staged:
        print("No valid rows found in CSV.")
        return

    with conn.cursor() as cur:
        # 1) Temp staging table
        cur.execute("""
            CREATE TEMPORARY TABLE publishers_stage (
                name VARCHAR(150) NOT NULL,
                site_url VARCHAR(500) NOT NULL,
                source_page_url VARCHAR(255),
                iso2 CHAR(2) NULL,
                state_code VARCHAR(10) NULL,
                category_name VARCHAR(15) NOT NULL,
                UNIQUE KEY uniq_stage_site (site_url)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # 2) Bulk insert into staging
        data = list(staged.values())
        for i in range(0, len(data), batch_size):
            chunk = data[i : i + batch_size]
            cur.executemany(
                """INSERT IGNORE INTO publishers_stage
                   (name, site_url, source_page_url, iso2, state_code, category_name)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                chunk,
            )

        # 3) Ensure all needed categories exist
        cur.execute("""
            INSERT IGNORE INTO categories (name)
            SELECT DISTINCT category_name
            FROM publishers_stage;
        """)

        # 4) UPDATE existing publishers to the correct category_id
        #    Join publishers <- stage <- categories by site_url & category_name
        cur.execute("""
            UPDATE publishers p
            JOIN publishers_stage s ON s.site_url = p.site_url
            JOIN categories c ON c.name = s.category_name
            SET p.category_id = c.id
            WHERE p.category_id <> c.id OR p.category_id IS NULL;
        """)
        updated = cur.rowcount

        # 5) INSERT any new publishers that aren't in DB yet (idempotent)
        cur.execute("""
            INSERT INTO publishers (created_at, name, feed_url, site_url, favicon_url, category_id)
            SELECT CURRENT_TIMESTAMP, s.name, NULL, s.site_url, NULL, c.id
            FROM publishers_stage s
            JOIN categories c ON c.name = s.category_name
            LEFT JOIN publishers p ON p.site_url = s.site_url
            WHERE p.id IS NULL;
        """)
        inserted = cur.rowcount

    conn.commit()
    print(
        f"Done. Updated categories for {updated} existing publishers. Inserted {inserted} new publishers."
    )


# Usage:
recategorize_and_import_from_csv(db_connection, "/root/assets/publishers.csv")
