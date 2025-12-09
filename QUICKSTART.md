# Quick Start Guide for Contributors

Get Infomundi running locally in 5 minutes!

## Prerequisites

- Docker and Docker Compose installed
- Git installed
- 4GB RAM available for Docker

## Setup Steps

### 1. Clone the Repository

```bash
git clone https://github.com/Infomundi-Project/website.git
cd website
```

### 2. Create Environment File

```bash
# Copy the example environment file
cp .env.example .env

# Generate secure keys (on macOS/Linux)
sed -i "s/your-secret-key-here.*/$(openssl rand -hex 32)/" .env
sed -i "s/your-encryption-key-here.*/$(openssl rand -hex 32)/" .env
sed -i "s/your-hmac-key-here.*/$(openssl rand -hex 32)/" .env

# On Windows (PowerShell):
# (Get-Content .env) -replace 'your-secret-key-here.*', (python -c "import secrets; print(secrets.token_hex(32))") | Set-Content .env
```

Or manually edit `.env` and replace the keys with random strings.

### 3. Set up Assets & Start Services

```bash
# Initialize and update all submodules
git submodule update --init --recursive

# Start all services in background
docker compose up -d

# View logs (optional)
docker compose logs -f infomundi-app
```

Wait around 30 seconds for services to initialize.

### 4. Seed Database

```bash
# Import reference data (categories, publishers, countries)
docker compose exec infomundi-app python -m utils.extra.insert_feeds_to_database

# Generate statistics cache
docker compose exec infomundi-app python utils/extra/get_statistics
docker compose exec infomundi-app python utils/search_news.py
```

### 5. Open the App

**Open http://localhost:5000** in your browser!

You should see the Infomundi homepage.

### 6. Create a Test Account

1. Click "Register"
2. Use a fake email like `test@example.com` (MailHog will catch it)
3. View the verification email at http://localhost:8025
4. Click the verification link

## What's Running?

| Service | Purpose | Access |
|---------|---------|--------|
| **infomundi-app** | Flask application | http://localhost:5000 |
| **infomundi-mysql** | Database | localhost:3306 |
| **infomundi-redis** | Cache | localhost:6379 |
| **mailhog** | Email testing | http://localhost:8025 |

## Daily Development Workflow

```bash
# Start services
docker compose up -d

# Make code changes (edit files with your editor)
# The container automatically reloads when you save

# View logs
docker compose logs -f infomundi-app

# Run tests
docker compose exec infomundi-app pytest tests/

# Stop services (optional - can leave running)
docker compose stop
```

## Common Commands

```bash
# Restart app after dependency changes
docker compose up -d --force-recreate --no-deps infomundi-app

# Access MySQL shell
docker compose exec infomundi-mysql mysql -u infomundi -p
# Password: dev_pass

# Access Redis CLI
docker compose exec infomundi-redis redis-cli -a dev_redis_pass

# Access Python shell in app container
docker compose exec infomundi-app python

# View all containers
docker compose ps

# Stop all services
docker compose down

# Stop and remove all data (fresh start)
docker compose down -v
```

## Troubleshooting

### Port Already in Use

If port 5000 or 3306 is already taken:

```bash
# Edit docker-compose.yml to use different ports
# Change "5000:5000" to "5001:5000" for Flask
# Change "3306:3306" to "3307:3306" for MySQL
```

### Database Connection Error

```bash
# Check if MySQL is running
docker compose ps infomundi-mysql

# View MySQL logs
docker compose logs infomundi-mysql

# Restart MySQL
docker compose restart infomundi-mysql
```

### App Won't Start

```bash
# View app logs
docker compose logs infomundi-app

# Rebuild app
docker compose up -d --force-recreate infomundi-app

# Check disk space
docker system df
```

### "Module Not Found" Error

```bash
# Rebuild with fresh pip install
docker compose down
docker compose up -d --build
```

## File Structure

```
website/
├── app.py              # Flask app entry point
├── wsgi.py             # Production WSGI entry
├── views.py            # HTML page routes
├── auth.py             # Authentication routes
├── api.py              # JSON API routes
├── website_scripts/    # Utility modules
├── templates/          # Jinja2 HTML templates
├── static/             # CSS, JS, images
├── sql/                # Database schema
├── tests/              # Test files
├── utils/              # Helper scripts
├── docker-compose.yml  # Local dev environment
├── .env.example        # Environment template
└── requirements.txt    # Python dependencies
```

## Next Steps

1. **Read** [CONTRIBUTING.md](CONTRIBUTING.md) - Development guidelines
2. **Read** [CLAUDE.md](CLAUDE.md) - Architecture overview
3. **Create** a feature branch: `git checkout -b feature/my-feature`
4. **Make** your changes
5. **Test** your changes: `docker compose exec infomundi-app pytest tests/`
6. **Submit** a pull request

## Getting Help

- **Questions**: Ask in team Slack/Discord
- **Bugs**: Open a GitHub issue
- **Security**: Report privately to maintainers

Happy coding! 🚀
