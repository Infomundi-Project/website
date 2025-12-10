# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Infomundi is a Flask-based news aggregation and social platform that collects stories from RSS feeds, processes them with AI, and provides a social layer for users to interact with news content. The application uses MySQL for persistence, Redis for caching, and supports both local and cloud storage (Cloudflare R2) for media.

## Architecture

### Application Structure

The application follows a modular Flask blueprint architecture:

- **app.py**: Main Flask application initialization, configures database, cache, SocketIO, and error handlers
- **views.py**: Main user-facing routes (homepage, news pages, user profiles)
- **auth.py**: Authentication routes (login, register, password recovery, 2FA)
- **api.py**: RESTful API endpoints for AJAX calls and data access
- **wsgi.py**: WSGI entry point for Gunicorn

### Core Modules (website_scripts/)

The `website_scripts/` directory contains the business logic:

- **models.py**: SQLAlchemy ORM models (User, Story, Publisher, Category, Tag, Comment, etc.)
- **config.py**: Environment-based configuration loader
- **extensions.py**: Shared Flask extensions (db, cache, login_manager, limiter, socketio)
- **decorators.py**: Custom decorators (admin_required, login_required, rate limiting, captcha verification)
- **security_util.py**: Encryption/decryption (AES-GCM), email fingerprinting, session management
- **hashing_util.py**: MD5, SHA256, binary conversions for public IDs
- **input_sanitization.py**: Input validation and HTML sanitization
- **auth_util.py**: User registration, login, password recovery flows
- **scripts.py**: Business logic for page rendering and data processing

### News Processing (utils/)

The `utils/` directory contains background job scripts:

- **search_news.py**: Fetches RSS feeds, extracts metadata using YAKE keyword extraction, stores stories in database
- **search_news_images.py**: Downloads and processes story images, converts to AVIF format
- **extra/insert_feeds_to_database.py**: Seeds database with publisher/category reference data
- **extra/get_statistics.py**: Generates cached statistics for the platform
- **extra/fetch_favicons.py**: Downloads publisher favicons

These scripts are meant to run via `python -m utils.search_news` or as cron jobs.

### Database Schema

Key tables:
- **users**: Encrypted emails (AES-GCM), Argon2id password hashing, TOTP/email 2FA, profile customization
- **stories**: News articles with url_hash (binary MD5) for deduplication, has_image flag, pub_date
- **publishers**: RSS feed sources with category associations
- **categories**: Story categorization (e.g., br_general, us_technology)
- **tags**: YAKE-extracted keywords linked to stories
- **comments**: Threaded comment system with parent/child relationships
- **story_reactions** / **comment_reactions**: User likes/dislikes
- **friendships**: Social connections between users
- **notifications**: User activity notifications

### Storage Modes

The application supports two storage modes (detected in models.py):

1. **Local Development**: Media served from `/static/local_uploads/` when R2 credentials are missing
2. **Production**: Media served from Cloudflare R2 bucket at `https://bucket.infomundi.net/`

Story images follow pattern: `stories/{category_name}/{md5_hash}.avif`

### Security Features

- Emails stored encrypted (AES-GCM) with HMAC-based fingerprints for lookup
- Passwords hashed with Argon2id
- CSRF protection via Flask-WTF
- Rate limiting via Flask-Limiter
- Cloudflare Turnstile CAPTCHA integration
- Custom CAPTCHA fallback option
- Session version invalidation for forced logouts
- Input sanitization with bleach for HTML content

### Real-time Features

- Flask-SocketIO with eventlet workers for WebSocket support
- Real-time chat system (Maximus Chat)
- Online presence indicators
- Live notifications

## Development Commands

### Initial Setup

```bash
# Initialize submodules (contains SQL seed data in assets/)
git submodule update --init --recursive

# Create and configure environment
cp .env.example .env
# Edit .env with secure random keys (see QUICKSTART.md)

# Start all services
docker compose up -d

# Wait ~30 seconds for MySQL initialization

# Seed database with publishers/categories
docker compose exec infomundi-app python -m utils.extra.insert_feeds_to_database

# Fetch news stories (respects NEWS_SEARCH_DEBUG=1 for limited categories)
docker compose exec infomundi-app python -m utils.search_news

# Download story images
docker compose exec infomundi-app python -m utils.search_news_images

# Generate statistics cache
docker compose exec infomundi-app python -m utils.extra.get_statistics
```

### Daily Development

```bash
# Start services (if stopped)
docker compose up -d

# View app logs (auto-reloads on file changes)
docker compose logs -f infomundi-app

# Run tests
docker compose exec infomundi-app pytest tests/

# Access Python shell with app context
docker compose exec infomundi-app python

# Access MySQL
docker compose exec infomundi-mysql mysql -u infomundi -p
# Password: dev_pass (or your MYSQL_PASSWORD from .env)

# Access Redis
docker compose exec infomundi-redis redis-cli -a dev_redis_pass

# Restart app after dependency changes
docker compose up -d --force-recreate --no-deps infomundi-app

# Stop services (preserves data)
docker compose stop

# Full cleanup (removes volumes)
docker compose down -v
```

### Running Background Jobs

```bash
# Fetch latest news (run periodically in production)
docker compose exec infomundi-app python -m utils.search_news

# Download news images
docker compose exec infomundi-app python -m utils.search_news_images

# Update statistics cache
docker compose exec infomundi-app python -m utils.extra.get_statistics

# Fetch publisher favicons
docker compose exec infomundi-app python -m utils.extra.fetch_favicons
```

### Testing

```bash
# Run all tests
docker compose exec infomundi-app pytest tests/

# Run specific test file
docker compose exec infomundi-app pytest tests/sanitization_test.py

# Run with verbose output
docker compose exec infomundi-app pytest -v tests/
```

## Code Conventions

### Import Organization

Files follow this import pattern:
1. Standard library imports
2. Third-party imports (Flask, SQLAlchemy, etc.)
3. Local website_scripts imports
4. Local blueprint imports (views, auth, api)

### Database Queries

- Use `joinedload()` for relationships that are always needed (reduces N+1 queries)
- Use `lazy="dynamic"` for collections that may be filtered
- Story public IDs use `get_public_id()` which returns hex MD5 from binary url_hash
- User public IDs stored as binary UUIDv4 in `public_id` field

### Security Patterns

- Always validate input with `input_sanitization` module before database operations
- Use `@decorators.verify_turnstile` on forms to prevent spam
- Use `@extensions.limiter.limit()` on sensitive endpoints
- Check `current_user.is_authenticated` before accessing user-specific data
- Encrypt sensitive data with `security_util.encrypt_data()` / `decrypt_data()`

### Configuration

All config loaded from environment variables via `website_scripts/config.py`. Never hardcode credentials or URLs.

Key environment variables:
- `BASE_URL`: Site URL without trailing slash (e.g., http://localhost or https://infomundi.net)
- `SEARCH_NEWS_DEBUG`: Set to 1 to limit news fetching to br_general category
- `SECRET_KEY`, `ENCRYPTION_KEY`, `HMAC_KEY`: Required cryptographic keys
- `MYSQL_*`, `REDIS_*`: Database credentials
- `R2_*`: Cloudflare R2 storage (optional for local dev)
- `OPENAI_API_KEY`: For AI summarization features (optional)

## Deployment Notes

- Production uses Gunicorn with eventlet workers (required for SocketIO)
- `docker-compose.yml` is for local development only
- Database schema is in `sql/infomundi.sql`
- Geographic reference data loaded from assets/ submodule (regions, countries, states, cities)
- The app checks for R2 credentials; if missing, automatically uses local storage mode

## Common Patterns

### Creating a New Route

1. Add route to appropriate blueprint (views, auth, or api)
2. Apply decorators in order: rate limit → auth → captcha
3. Validate all inputs with `input_sanitization` module
4. Use `extensions.db.session` for database operations
5. Return `render_template()` for HTML or `jsonify()` for API

### Adding a Database Model

1. Define model in `website_scripts/models.py`
2. Add relationships with appropriate `lazy` loading strategy
3. Implement `to_dict()` method for API serialization
4. Update `sql/infomundi.sql` with table schema

### Processing User Input

1. Strip whitespace with `.strip()`
2. Validate length/format with `input_sanitization.is_valid_*()`
3. Sanitize HTML content with `input_sanitization.sanitize_html()`
4. Hash sensitive identifiers with `hashing_util` functions

### Working with Stories

- Stories identified by MD5 hash of URL (`url_hash` field) to prevent duplicates
- Public story IDs use `story.get_public_id()` which returns hex string
- Images accessed via `story.get_image_url()` which handles local vs. cloud storage
- Categories follow pattern `{country_code}_{topic}` (e.g., br_general, us_technology)
