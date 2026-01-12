# Architecture Decisions

This document explains the non-obvious design decisions in this codebase. If you're a new developer wondering "why is it done this way?", this is the place to look.

## Table of Contents

1. [Email Encryption & Searchable Encryption Pattern](#email-encryption--searchable-encryption-pattern)
2. [Story URL Deduplication](#story-url-deduplication)
3. [Session Version Invalidation (Forced Logout)](#session-version-invalidation-forced-logout)
4. [Storage Mode Auto-Switching](#storage-mode-auto-switching)
5. [Public IDs vs Internal IDs](#public-ids-vs-internal-ids)
6. [Background Job Architecture](#background-job-architecture)
7. [CAPTCHA Systems](#captcha-systems)

---

## Email Encryption & Searchable Encryption Pattern

### The Problem

We need to store user emails securely (encrypted at rest), but we also need to look up users by email address during login and registration.

### The Solution

We use a **searchable encryption pattern** with two fields:

```
email_encrypted  → AES-GCM encrypted email (for retrieval/display)
email_fingerprint → HMAC-SHA256 of email (for lookups)
```

### How It Works

**Registration/Email Change:**
```python
# In models.py User.set_email() or auth_util.py
email_encrypted = security_util.encrypt(email)           # AES-GCM
email_fingerprint = hashing_util.generate_hmac_signature(email, as_bytes=True)  # HMAC-SHA256
```

**Lookup (login, duplicate check):**
```python
# In auth_util.py search_user_email_in_database()
user = User.query.filter_by(
    email_fingerprint=hashing_util.generate_hmac_signature(email, as_bytes=True)
).first()
```

**Retrieval (display to user):**
```python
plaintext_email = security_util.decrypt(user.email_encrypted)
```

### Why This Pattern?

- **Security**: Emails are encrypted. A database breach doesn't expose plaintext emails.
- **Searchable**: HMAC fingerprints allow O(1) lookups without decrypting every row.
- **Deterministic**: Same email always produces same fingerprint (unlike random IVs in encryption).

### Key Files

- `website_scripts/security_util.py` - `encrypt()`, `decrypt()` functions
- `website_scripts/hashing_util.py` - `generate_hmac_signature()` function
- `website_scripts/auth_util.py` - `search_user_email_in_database()` usage example
- `website_scripts/models.py` - `User.set_email()` method

### Common Mistakes to Avoid

- **Never** query by plaintext email: `User.query.filter_by(email=email)` won't work
- **Never** store plaintext email in the database
- **Always** use `generate_hmac_signature(email, as_bytes=True)` for lookups (note `as_bytes=True`)

---

## Story URL Deduplication

### The Problem

RSS feeds often return the same story multiple times. We need to prevent duplicates efficiently.

### The Solution

Each story has a `url_hash` field: a binary MD5 hash of the story URL.

```python
# In models.py
url_hash = db.Column(BINARY(16), nullable=False, unique=True)
```

### How It Works

**When inserting stories** (in `utils/search_news.py`):
```python
url_hash = hashing_util.string_to_md5_binary(story_url)
# INSERT IGNORE or check for existing hash
```

**Public-facing story IDs:**
```python
# In models.py Story.get_public_id()
def get_public_id(self) -> str:
    return hashing_util.binary_to_md5_hex(self.url_hash)
# Returns: "5d41402abc4b2a76b9719d911017c592"
```

**Looking up stories by public ID:**
```python
url_hash_binary = hashing_util.md5_hex_to_binary(public_id)
story = Story.query.filter_by(url_hash=url_hash_binary).first()
```

### Why MD5? Why Binary?

- **MD5**: Fast, 16 bytes, sufficient for deduplication (not used for security)
- **Binary storage**: 16 bytes vs 32 bytes for hex string = 50% storage savings
- **Index efficiency**: Binary comparison is faster than string comparison

### Key Files

- `website_scripts/models.py` - `Story` model, `get_public_id()` method
- `website_scripts/hashing_util.py` - `string_to_md5_binary()`, `md5_hex_to_binary()`, `binary_to_md5_hex()`
- `utils/search_news.py` - Story insertion logic

### Common Mistakes to Avoid

- **Never** use `Story.id` in URLs or APIs (exposes internal IDs, enumerable)
- **Always** use `story.get_public_id()` for external references
- **Always** convert hex → binary when querying: `md5_hex_to_binary(public_id)`

---

## Session Version Invalidation (Forced Logout)

### The Problem

When a user changes their password or we detect suspicious activity, we need to invalidate all their active sessions across all devices.

### The Solution

Each user has a `session_version` integer. On login, this version is stored in the session. On each request, we compare them.

```python
# In models.py
session_version = db.Column(db.Integer, default=0)
```

### How It Works

**On login** (in `auth_util.py`):
```python
session["session_version"] = user.session_version
```

**On every request** (in `app.py` lines 295-308):
```python
@app.before_request
def check_session_version():
    if current_user.is_authenticated:
        user = db.session.get(User, current_user.id)
        if session.get("session_version") != user.session_version:
            logout_user()  # Force logout
```

**To force logout all sessions:**
```python
user.session_version += 1
db.session.commit()
# All existing sessions now have stale version → logged out on next request
```

### When to Increment Session Version

- Password change
- Password reset
- Security-sensitive account changes
- Admin forcing user logout
- Suspicious activity detected

### Key Files

- `app.py` - `check_session_version()` before_request handler
- `website_scripts/auth_util.py` - `perform_login_actions()` stores session version
- `website_scripts/models.py` - `User.session_version` field

### Notes

- The check is cached for 5 minutes to reduce database load
- User sees a flash message: "We hope to see you again soon, {username}"

---

## Storage Mode Auto-Switching

### The Problem

In development, we don't want to require Cloudflare R2 credentials. In production, we use R2 for media storage.

### The Solution

At module load time, we check for R2 credentials and set a flag:

```python
# In models.py lines 20-28
USE_LOCAL_STORAGE = False
try:
    if not config.R2_ENDPOINT or not config.R2_ACCESS_KEY or not config.R2_SECRET:
        USE_LOCAL_STORAGE = True
except AttributeError:
    USE_LOCAL_STORAGE = True
```

### How It Works

**URL generation** (in `models.py`):
```python
def get_storage_url(path: str) -> str:
    if USE_LOCAL_STORAGE:
        return f"/static/local_uploads/{path}"
    else:
        return f"https://bucket.infomundi.net/{path}"
```

**Usage in models:**
```python
# Story.get_image_url()
path = f"stories/{self.category.name}/{self.get_public_id()}.avif"
return get_storage_url(path)

# User.get_picture()
return get_storage_url(f"users/{self.get_public_id()}.webp")
```

### File Path Conventions

| Content Type | Path Pattern | Format |
|--------------|--------------|--------|
| Story images | `stories/{category_name}/{md5_hash}.avif` | AVIF |
| User avatars | `users/{uuid}.webp` | WebP |
| User banners | `banners/{uuid}.webp` | WebP |
| User wallpapers | `wallpapers/{uuid}.webp` | WebP |

### Local Development Setup

1. Create directory: `static/local_uploads/`
2. Don't set R2 environment variables
3. Images will be served from `/static/local_uploads/`

### Key Files

- `website_scripts/models.py` - `USE_LOCAL_STORAGE` flag, `get_storage_url()` function
- `utils/search_news_images.py` - Image download/processing (also checks storage mode)

### Notes

- The storage mode is determined once at startup
- Restart the app after changing R2 credentials
- Images are converted to AVIF format before upload (stories) or WebP (users)

---

## Public IDs vs Internal IDs

### The Problem

Auto-increment integer IDs are enumerable, leak information about system size, and can be targeted.

### The Solution

We use different ID schemes for different purposes:

| Entity | Internal ID | Public ID | Public ID Format |
|--------|-------------|-----------|------------------|
| User | `id` (int) | `public_id` (binary UUID) | UUID string: `550e8400-e29b-41d4-a716-446655440000` |
| Story | `id` (int) | `url_hash` (binary MD5) | MD5 hex: `5d41402abc4b2a76b9719d911017c592` |

### Usage Patterns

**Users:**
```python
# Store (binary, 16 bytes)
public_id = db.Column(BINARY(16), nullable=False, unique=True)

# Generate
user.public_id = security_util.generate_uuid_bytes()

# Convert to string for URLs/API
public_id_string = user.get_public_id()  # → "550e8400-e29b-..."

# Convert back for queries
public_id_binary = security_util.uuid_string_to_bytes(public_id_string)
user = User.query.filter_by(public_id=public_id_binary).first()
```

**Stories:**
```python
# Get public ID
story_id = story.get_public_id()  # → "5d41402abc4b2a76b..."

# Query by public ID
url_hash = hashing_util.md5_hex_to_binary(story_id)
story = Story.query.filter_by(url_hash=url_hash).first()
```

### Key Files

- `website_scripts/security_util.py` - UUID generation and conversion
- `website_scripts/hashing_util.py` - MD5 conversion functions
- `website_scripts/models.py` - `get_public_id()` methods on User and Story

---

## Background Job Architecture

### Overview

Background jobs fetch news, download images, and update statistics. They run as standalone Python scripts.

### Job Scripts

| Script | Purpose | Run Frequency |
|--------|---------|---------------|
| `utils/search_news.py` | Fetch RSS feeds, extract keywords, store stories | Every 15-30 min |
| `utils/search_news_images.py` | Download story images, convert to AVIF | After search_news |
| `utils/extra/get_statistics.py` | Update cached site statistics | Every hour |
| `utils/extra/fetch_favicons.py` | Download publisher favicons | Daily or on-demand |

### Running Jobs

```bash
# In development (Docker)
docker compose exec infomundi-app python -m utils.search_news
docker compose exec infomundi-app python -m utils.search_news_images

# In production (cron example)
*/30 * * * * cd /app && python -m utils.search_news
*/30 * * * * cd /app && python -m utils.search_news_images
0 * * * * cd /app && python -m utils.extra.get_statistics
```

### Concurrency Settings

Both `search_news.py` and `search_news_images.py` use ThreadPoolExecutor:

```python
# search_news.py
MAX_WORKERS = 20  # Concurrent feed fetchers

# search_news_images.py
WORKERS = 20  # Concurrent image downloaders
```

### Debug Mode

Set `SEARCH_NEWS_DEBUG=1` to limit news fetching to `br_general` category only (faster for development).

### Key Considerations

- Jobs connect directly to MySQL (not through Flask app)
- Jobs handle their own database connections and pooling
- Proxy rotation is used for image downloads (see `search_news_images.py`)
- Failed downloads are logged but don't stop the batch

---

## CAPTCHA Systems

### Overview

The codebase has three CAPTCHA systems. Currently, **Cloudflare Turnstile** is the primary system.

### Available Systems

1. **Cloudflare Turnstile** (Primary)
   - Configured via `TURNSTILE_SECRET_KEY` and `TURNSTILE_SITE_KEY`
   - Used with `@decorators.verify_turnstile` decorator

2. **Custom CAP Service** (Optional, in docker-compose)
   - Separate container for self-hosted CAPTCHA
   - Configure via `CAP_SECRET_KEY` and `CAP_URL`
   - Currently not documented or actively used

3. **Infomundi CAPTCHA** (Legacy)
   - Custom implementation, still in code but deprecated
   - May be removed in future cleanup

### Usage in Routes

```python
from website_scripts.decorators import verify_turnstile

@auth.route("/login", methods=["POST"])
@verify_turnstile
def login():
    # CAPTCHA already verified by decorator
    ...
```

### Configuration

```env
# .env
TURNSTILE_SECRET_KEY=your_secret_key
TURNSTILE_SITE_KEY=your_site_key
```

### Frontend Integration

Templates include the Turnstile widget. The token is submitted with forms and verified server-side by the decorator.

---

## Questions?

If you encounter a pattern that isn't documented here and seems non-obvious, please add it to this document for future developers.
