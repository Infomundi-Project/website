# Infomundi

<div align="center">

![Infomundi Logo](https://raw.githubusercontent.com/behindsecurity/behindsecurity/refs/heads/main/images/infomundi-nobg.webp)

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1-green.svg)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)

[Features](#features) • [Quick Start](#quick-start) • [Documentation](#documentation) • [Contributing](#contributing)

</div>

---

## Overview

Infomundi is a Flask-based news aggregation and social platform that collects stories from RSS feeds worldwide, processes them with AI-powered summarization, and provides a social layer for users to engage with global news. The platform organizes content by geographic regions and categories, making it easy to discover news from any part of the world.

### Key Features

- **📰 Global News Aggregation**: Automatically fetches and processes news from RSS feeds across multiple countries and categories
- **🤖 AI-Powered Summaries**: OpenAI integration for intelligent story summarization
- **🌍 Geographic Organization**: Browse news by region, country, and category
- **👥 Social Features**: User profiles, friendships, comments, reactions, and notifications
- **💬 Real-Time Chat**: WebSocket-powered chat system for live discussions
- **🔐 Security-First**: AES-GCM email encryption, Argon2id password hashing, CSRF protection, rate limiting
- **🔑 2FA Support**: Both TOTP (authenticator apps) and email-based two-factor authentication
- **📊 Analytics**: Site statistics, story views, trending content
- **🎨 Customizable Profiles**: Avatars, banners, wallpapers, and profile descriptions
- **🔍 Keyword Extraction**: YAKE algorithm for automatic story tagging
- **☁️ Cloud Storage**: Cloudflare R2 integration with local development fallback
- **🚀 Performance**: Redis caching, optimized database queries, AVIF image format

## Tech Stack

### Backend
- **Framework**: Flask 3.1 with Blueprints architecture
- **Database**: MySQL 8.0 with SQLAlchemy ORM
- **Cache**: Redis 7
- **Real-time**: Flask-SocketIO with eventlet workers
- **AI**: OpenAI API for summarization
- **Security**: Flask-WTF (CSRF), Flask-Limiter (rate limiting), Cloudflare Turnstile

### Frontend
- **Templates**: Jinja2
- **Styles**: Bootstrap 5, custom CSS
- **Assets**: Flask-Assets with minification
- **Icons**: Font Awesome
- **Maps**: Interactive region visualization

### Infrastructure
- **Deployment**: Docker Compose, Gunicorn
- **Storage**: Cloudflare R2 (S3-compatible)
- **Email**: SMTP with MailHog for local development
- **Monitoring**: Webhook alerts for errors

## Quick Start

Get Infomundi running locally in 5 minutes!

### Prerequisites
- Docker and Docker Compose
- Git
- 4GB RAM available for Docker

### Installation

```bash
# Clone the repository
git clone https://github.com/Infomundi-Project/website.git
cd website

# Initialize submodules (contains geographic data)
git submodule update --init --recursive

# Create environment file
cp .env.example .env

# Generate secure keys (Linux/macOS)
sed -i "s/your-secret-key-here.*/$(openssl rand -hex 32)/" .env
sed -i "s/your-encryption-key-here.*/$(openssl rand -hex 32)/" .env
sed -i "s/your-hmac-key-here.*/$(openssl rand -hex 32)/" .env

# Start all services
docker compose up -d

# Wait ~30 seconds for MySQL to initialize

# Seed database with publishers and categories
docker compose exec infomundi-app python -m utils.extra.insert_feeds_to_database

# Fetch news stories
docker compose exec infomundi-app python -m utils.search_news

# Download story images
docker compose exec infomundi-app python -m utils.search_news_images

# Generate statistics
docker compose exec infomundi-app python -m utils.extra.get_statistics
```

### Access the Application

- **Website**: http://localhost:5000
- **Email Testing**: http://localhost:8025 (MailHog)

For detailed setup instructions, see [QUICKSTART.md](QUICKSTART.md).

## Project Structure

```
website/
├── app.py                      # Flask application initialization
├── views.py                    # Main routes (homepage, news, profiles)
├── auth.py                     # Authentication routes
├── api.py                      # RESTful API endpoints
├── wsgi.py                     # WSGI entry point
│
├── website_scripts/            # Core business logic
│   ├── models.py              # SQLAlchemy models
│   ├── config.py              # Environment configuration
│   ├── extensions.py          # Flask extensions
│   ├── security_util.py       # Encryption & security
│   ├── auth_util.py           # Authentication flows
│   ├── input_sanitization.py  # Input validation
│   └── ...                    # Other utilities
│
├── utils/                      # Background job scripts
│   ├── search_news.py         # RSS feed fetcher
│   ├── search_news_images.py  # Image downloader
│   └── extra/                 # Data seeding & maintenance
│
├── templates/                  # Jinja2 HTML templates
├── static/                     # CSS, JS, fonts, images
├── sql/                        # Database schema
├── assets/                     # Git submodule with seed data
└── tests/                      # Test suite
```

## Development

### Common Commands

```bash
# View application logs
docker compose logs -f infomundi-app

# Run tests
docker compose exec infomundi-app pytest tests/

# Access Python shell
docker compose exec infomundi-app python

# Access MySQL
docker compose exec infomundi-mysql mysql -u infomundi -p

# Access Redis CLI
docker compose exec infomundi-redis redis-cli -a dev_redis_pass

# Restart app after code changes
docker compose up -d --force-recreate --no-deps infomundi-app

# Stop all services
docker compose stop

# Clean restart (removes all data)
docker compose down -v
```

### Running Background Jobs

In production, these should run periodically (e.g., via cron):

```bash
# Fetch latest news
docker compose exec infomundi-app python -m utils.search_news

# Download images for new stories
docker compose exec infomundi-app python -m utils.search_news_images

# Update site statistics
docker compose exec infomundi-app python -m utils.extra.get_statistics

# Fetch publisher favicons
docker compose exec infomundi-app python -m utils.extra.fetch_favicons
```

### Environment Variables

Key configuration in `.env`:

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Flask session encryption | Yes |
| `ENCRYPTION_KEY` | AES-GCM encryption key | Yes |
| `HMAC_KEY` | Email fingerprint HMAC key | Yes |
| `BASE_URL` | Site URL (no trailing slash) | Yes |
| `MYSQL_*` | Database credentials | Yes |
| `REDIS_PASSWORD` | Redis password | Yes |
| `OPENAI_API_KEY` | OpenAI API key for summaries | No |
| `R2_*` | Cloudflare R2 storage credentials | No |
| `TURNSTILE_*` | Cloudflare Turnstile CAPTCHA keys | No |
| `GOOGLE_CLIENT_*` | Google OAuth credentials | No |

See [.env.example](.env.example) for all options.

## Database Schema

The application uses a relational schema with the following key tables:

- **users**: User accounts with encrypted emails and Argon2id password hashing
- **stories**: News articles with AI summaries and keyword tags
- **publishers**: RSS feed sources organized by category
- **categories**: Story classification by country and topic
- **comments**: Threaded discussion system
- **friendships**: Social connections between users
- **notifications**: User activity alerts
- **story_reactions** / **comment_reactions**: Like/dislike tracking

Geographic reference data (regions, countries, states, cities) is loaded from the `assets/` submodule.

## Security Features

Infomundi implements defense-in-depth security:

- **Email Privacy**: Emails encrypted with AES-GCM, searchable via HMAC fingerprints
- **Password Security**: Argon2id hashing with high cost parameters
- **CSRF Protection**: Flask-WTF tokens on all forms
- **Rate Limiting**: Flask-Limiter on authentication and API endpoints
- **Input Validation**: Comprehensive sanitization with bleach
- **Session Management**: Secure cookies with version invalidation
- **2FA Options**: TOTP (RFC 6238) and email-based verification
- **CAPTCHA**: Cloudflare Turnstile with custom fallback

## Testing

```bash
# Run all tests
docker compose exec infomundi-app pytest tests/

# Run specific test file
docker compose exec infomundi-app pytest tests/sanitization_test.py

# Run with verbose output
docker compose exec infomundi-app pytest -v tests/

# Run with coverage
docker compose exec infomundi-app pytest --cov=website_scripts tests/
```

## Contributing

We welcome contributions! Here's how to get started:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**: Follow the existing code style
4. **Test thoroughly**: Ensure tests pass
5. **Commit your changes**: Use clear commit messages
6. **Push to your fork**: `git push origin feature/amazing-feature`
7. **Open a Pull Request**: Describe your changes

### Development Guidelines

- Follow PEP 8 for Python code style
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Validate all user input with `input_sanitization` module
- Use Flask-Limiter on new endpoints
- Add tests for new features
- Update documentation as needed

For AI assistance during development, see [CLAUDE.md](CLAUDE.md) for architectural guidance.

## Deployment

The included `docker-compose.yml` is for **local development only**. For production deployment:

1. **Set secure environment variables** (strong random keys)
2. **Configure Cloudflare R2** for media storage
3. **Set up SMTP** for email delivery
4. **Enable HTTPS** (required for secure cookies)
5. **Set up cron jobs** for background tasks
6. **Configure monitoring** via webhook alerts
7. **Use a reverse proxy** (nginx/Cloudflare) for rate limiting and DDoS protection

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Flask**: Micro web framework
- **OpenAI**: AI-powered summarization
- **Cloudflare**: CDN, storage, and CAPTCHA services
- **YAKE**: Keyword extraction algorithm
- All the open-source contributors who made this possible

## Links

- **Documentation**: [QUICKSTART.md](QUICKSTART.md) | [CLAUDE.md](CLAUDE.md)
- **Repository**: [github.com/Infomundi-Project/website](https://github.com/Infomundi-Project/website)
- **Issues**: [Report a bug or request a feature](https://github.com/Infomundi-Project/website/issues)

---

<div align="center">

**Made with ❤️ by the Infomundi team**

</div>
