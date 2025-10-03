<div align="center">

![Infomundi Logo](https://raw.githubusercontent.com/behindsecurity/behindsecurity/refs/heads/main/images/infomundi-nobg.webp)

[![Codacy Badge](https://app.codacy.com/project/badge/Grade/3549171b5ed14423b31b3138afdf80ee)](https://app.codacy.com?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
![Python](https://img.shields.io/badge/Python-3.12.7-blue?style=social&logo=python&logoColor=black)
![Flask](https://img.shields.io/badge/3.1.0-black?style=social&logo=flask&logoColor=black&label=Flask)
![MySQL](https://img.shields.io/badge/MySQL-9.0.1-blue?style=social&logo=mysql&logoColor=black)
![Bootstrap 5](https://img.shields.io/badge/5.3.x-blue?style=social&logo=bootstrap&logoColor=black&label=Bootstrap)

</div>

# Infomundi — News platform and community

[![Português (Brasil)](https://img.shields.io/badge/README-pt--BR-blue)](README-pt.md)

Monolithic **Flask** app with server-side rendering, a **REST API**, and **WebSockets** for real-time features. Back end in Python (Flask 3.x + SQLAlchemy/MySQL), front end with **Jinja2** + **Bootstrap 5** and vanilla JavaScript; **Redis** for caching and **Cloudflare R2** for image storage.

> This README summarizes the architecture and workflow of the Infomundi project and documents how to develop and deploy it.

---

## Table of Contents
- [Overview](#overview)
- [Stack and key components](#stack-and-key-components)
- [Folder structure](#folder-structure)
- [Product features](#product-features)
- [Getting started (local dev)](#getting-started-local-dev)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment variables](#environment-variables)
  - [Running the application](#running-the-application)
- [Docker Compose (recommended)](#docker-compose-recommended)
- [Jobs and helper scripts](#jobs-and-helper-scripts)
- [API (overview)](#api-overview)
- [Real time (Socket.IO)](#real-time-socketio)
- [Security](#security)
- [Caching and performance](#caching-and-performance)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Roadmap and improvements](#roadmap-and-improvements)

---

## Overview

**Infomundi** is a news-discovery platform with social features (comments, reactions, friendships, and messages). The app follows **MVC** using **Flask Blueprints** to separate **views** (HTML pages), **auth** (authentication/accounts), and **api** (JSON endpoints). The front end is server-rendered (good SEO and fast first paint) and is enhanced by AJAX/WebSocket for dynamic content (notifications, comments, and chat).

## Stack and key components

- **Back end**
  - Python 3.12, Flask 3.x, Flask-Login, Flask-Limiter, Flask-SocketIO
  - SQLAlchemy (MySQL)
  - Flask-Assets for bundling/minifying CSS/JS
  - Redis (Flask-Caching) for cache
- **Front end**
  - Jinja2 (templates), Bootstrap 5 (responsive UI), vanilla JS (modules in `static/js`)
- **Infra**
  - Cloudflare R2 (S3-compatible) for image uploads (avatar, banner, etc.)
  - SMTP for transactional email (account verification, password reset, contact)
  - (Optional) Google OAuth
- **Security**
  - **TOTP 2FA**, **Argon2id** for passwords, and **AES-GCM** + HMAC for user emails
  - **Cloudflare Turnstile** and **custom image CAPTCHA** for anti-spam
- **Real time**
  - WebSockets via Flask-SocketIO (messages, typing indicators, read receipts)

## Folder structure

```

.
├── README-pt.md
├── README.md
├── api.py
├── app.py
├── assets
│   ├── data
│   │   └── json
│   │       ├── area_ranking.json
│   │       ├── capitals_time.json
│   │       ├── common_currency.json
│   │       ├── countries.json
│   │       ├── countries_data
│   │       │   ├── ad.json
│   │       │   ├── ae.json
│   │       │   ├── af.json
│   │       │   ├── ag.json
│   │       │   ├── <SNIP>
│   │       │   ├── yt.json
│   │       │   ├── za.json
│   │       │   ├── zm.json
│   │       │   └── zw.json
│   │       ├── country_names_codes.json
│   │       ├── crypto.json
│   │       ├── currencies.json
│   │       ├── feeds
│   │       │   ├── feeds.json
│   │       │   └── old-feeds.json
│   │       ├── gdp.json
│   │       ├── gdp_per_capita.json
│   │       ├── hdi_data.json
│   │       ├── langcodes.json
│   │       ├── presidents.json
│   │       ├── religions.json
│   │       └── stocks.json
│   ├── http-proxies.txt
│   └── sql
│       ├── cities.sql
│       ├── countries.sql
│       ├── regions.sql
│       ├── states.sql
│       └── subregions.sql
├── auth.py
├── data
├── requirements.txt
├── ruff.toml
├── sql
│   └── infomundi.sql
├── static
│   ├── ads.txt
│   ├── countries.xml
│   ├── css
│   │   ├── chat.css
│   │   ├── commentSystem.css
│   │   ├── libs
│   │   │   ├── bootstrap.min.css
│   │   │   ├── bootstrap.min.css.bak
│   │   │   ├── cookieconsent.css
│   │   │   ├── cropper.min.css
│   │   │   ├── font-awesome-4.7.0.min.css
│   │   │   ├── jquery-ui-1.13.1.css
│   │   │   └── quill.css
│   │   ├── main.css
│   │   ├── maximusSummary.css
│   │   ├── navbar.css
│   │   ├── news.css
│   │   ├── ticker.css
│   │   └── userProfile.css
│   ├── favicon.ico
│   ├── fontawesome
│   │   └── css
│   │       ├── all.css
│   │       ├── all.min.css
│   │       ├── brands.css
│   │       ├── brands.min.css
│   │       ├── fontawesome.css
│   │       ├── fontawesome.min.css
│   │       ├── regular.css
│   │       ├── regular.min.css
│   │       ├── solid.css
│   │       ├── solid.min.css
│   │       ├── svg-with-js.css
│   │       ├── svg-with-js.min.css
│   │       ├── v4-font-face.css
│   │       ├── v4-font-face.min.css
│   │       ├── v4-shims.css
│   │       ├── v4-shims.min.css
│   │       ├── v5-font-face.css
│   │       └── v5-font-face.min.css
│   ├── fonts
│   │   ├── Alexandria-Regular.ttf
│   │   ├── Inconsolata-Medium.ttf
│   │   ├── NotoSerifGeorgian-ExtraBold.ttf
│   │   ├── NotoSerifGeorgian-SemiBold.ttf
│   │   ├── RobotoMono-Medium.ttf
│   │   ├── SourceCodePro-Black.ttf
│   │   ├── Spectral-SemiBold.ttf
│   │   ├── SpectralSC-SemiBold.ttf
│   │   └── captcha
│   │       ├── chill.ttf
│   │       ├── fears.ttf
│   │       ├── mom.ttf
│   │       └── script.ttf
│   ├── gen
│   │   ├── base_packed.css
│   │   ├── base_packed.js
│   │   ├── base_packed_authenticated.js
│   │   ├── home_packed.js
│   │   ├── news_packed.js
│   │   └── profile_packed.js
│   ├── gui.alves_0xA0136487_public.asc
│   ├── img
│   │   ├── avatar.webp
│   │   ├── brands
│   │   │   └── google-logo.webp
│   │   ├── dbarros.webp
│   │   ├── favicon
│   │   │   ├── android-chrome-192x192.png
│   │   │   ├── android-chrome-384x384.png
│   │   │   ├── apple-touch-icon.png
│   │   │   ├── browserconfig.xml
│   │   │   ├── favicon-16x16.png
│   │   │   ├── favicon-32x32.png
│   │   │   ├── favicon.ico
│   │   │   ├── mstile-150x150.png
│   │   │   ├── safari-pinned-tab.svg
│   │   │   └── site.webmanifest
│   │   ├── flags
│   │   │   └── 4x3
│   │   │       ├── ad.svg
│   │   │       ├── ae.svg
│   │   │       ├── af.svg
│   │   │       ├── ag.svg
│   │   │       ├── ai.svg
│   │   │       ├── <SNIP>
│   │   │       ├── za.svg
│   │   │       ├── zm.svg
│   │   │       └── zw.svg
│   │   ├── galves.webp
│   │   ├── illustrations
│   │   │   ├── captcha.webp
│   │   │   ├── change_password-bg.webp
│   │   │   ├── change_password.webp
│   │   │   ├── editing-bg.webp
│   │   │   ├── editing.webp
│   │   │   ├── forgot_password.webp
│   │   │   ├── login.webp
│   │   │   ├── maintenance.webp
│   │   │   ├── maximus.webp
│   │   │   ├── owl.webp
│   │   │   ├── parchment.webp
│   │   │   ├── pillar-bottom2.webp
│   │   │   ├── pillar-middle2.webp
│   │   │   ├── pillar-top2.webp
│   │   │   ├── register.webp
│   │   │   ├── ruins.webp
│   │   │   ├── scroll.webp
│   │   │   └── struggling.webp
│   │   ├── infomundi-white-darkbg-square.webp
│   │   ├── logos
│   │   │   ├── logo-500-bg-dark.webp
│   │   │   ├── logo-500-bg-light.webp
│   │   │   ├── logo-500-dark.webp
│   │   │   ├── logo-500-default.png
│   │   │   ├── logo-500-default.webp
│   │   │   ├── logo-500-light.webp
│   │   │   ├── logo-icon-dark.svg
│   │   │   ├── logo-icon-dark.webp
│   │   │   ├── logo-icon-light.svg
│   │   │   ├── logo-icon-light.webp
│   │   │   ├── logo-light.svg
│   │   │   ├── logo-wide-dark-resized.webp
│   │   │   └── logo-wide-light-resized.webp
│   │   └── maximus.webp
│   ├── js
│   │   ├── autoSubmitCaptcha.js
│   │   ├── autocomplete.js
│   │   ├── autocompleteNoRedirect.js
│   │   ├── automaticTranslation.js
│   │   ├── captcha.js
│   │   ├── captchaWaitSubmit.js
│   │   ├── chart.js
│   │   ├── chat.js
│   │   ├── codeTokenChanger.js
│   │   ├── commentSystem.js
│   │   ├── cookieConsent.js
│   │   ├── defaultFormValidation.js
│   │   ├── fetchHomeTicker.js
│   │   ├── hiddenNavbarScroll.js
│   │   ├── home
│   │   │   ├── fetchHomeDashboard.js
│   │   │   └── worldFeed.js
│   │   ├── libs
│   │   │   ├── amcharts
│   │   │   │   ├── animated.js
│   │   │   │   ├── continentsLow.js
│   │   │   │   ├── index.js
│   │   │   │   ├── map.js
│   │   │   │   ├── micro.js
│   │   │   │   └── worldLow.js
│   │   │   ├── bootstrap.bundle.min.js
│   │   │   ├── bootstrap.bundle.min.js.bak
│   │   │   ├── cap_wasm.min.js
│   │   │   ├── cap_wasm_bg.wasm
│   │   │   ├── chart.umd.min.js
│   │   │   ├── cookieconsent-3.0.1.js
│   │   │   ├── cropper.min.js
│   │   │   ├── jquery-3.7.1.min.js
│   │   │   ├── jquery-ui-1.13.1.min.js
│   │   │   ├── lazysizes.min.js
│   │   │   ├── popper-2.11.8.min.js
│   │   │   ├── quill.js
│   │   │   └── socket.io.min.js
│   │   ├── linkSafety.js
│   │   ├── maximusSummary.js
│   │   ├── notificationSystem.js
│   │   ├── passwordUtility.js
│   │   ├── profile
│   │   │   ├── edit
│   │   │   │   └── imageCrop.js
│   │   │   ├── friendshipButtons.js
│   │   │   ├── lastSeen.js
│   │   │   ├── reportUser.js
│   │   │   └── userStats.js
│   │   ├── registerFormValidation.js
│   │   ├── renderFriendsModal.js
│   │   ├── renderStories.js
│   │   ├── scrollProgressBar.js
│   │   ├── scrollTopButton.js
│   │   ├── themeButton.js
│   │   ├── tickerSpeedUp.js
│   │   ├── triggerLiveToast.js
│   │   ├── triggerTooltip.js
│   │   ├── updateStatus.js
│   │   └── utils
│   │       └── keys.js
│   ├── pubkey.asc
│   ├── robots.txt
│   ├── security.txt
│   ├── sitemap.xml
│   ├── sounds
│   │   └── pop.ogg
│   └── webfonts
│       ├── fa-brands-400.ttf
│       ├── fa-brands-400.woff2
│       ├── fa-regular-400.ttf
│       ├── fa-regular-400.woff2
│       ├── fa-solid-900.ttf
│       ├── fa-solid-900.woff2
│       ├── fa-v4compatibility.ttf
│       └── fa-v4compatibility.woff2
├── templates
│   ├── about.html
│   ├── base.html
│   ├── captcha.html
│   ├── comments.html
│   ├── contact.html
│   ├── edit_avatar.html
│   ├── edit_profile.html
│   ├── edit_settings.html
│   ├── error.html
│   ├── forgot_password.html
│   ├── homepage.html
│   ├── login.html
│   ├── maintenance.html
│   ├── news.html
│   ├── policies.html
│   ├── register.html
│   ├── sensitive.html
│   ├── team.html
│   ├── twofactor.html
│   └── user_profile.html
├── tests
│   └── sanitization_test.py
├── utils
│   ├── __init__.py
│   ├── collect_world_data.py
│   ├── create_cache.py
│   ├── csv_publishers_to_database.py
│   ├── enhanced_create_cache.py
│   ├── fetch_favicons.py
│   ├── get_statistics.py
│   ├── insert_feeds_to_database.py
│   ├── reader.py
│   ├── search_images.py
│   └── update-rss.py
├── views.py
├── website_scripts
│   ├── __init__.py
│   ├── auth_util.py
│   ├── captcha_util.py
│   ├── cloudflare_util.py
│   ├── comments_util.py
│   ├── config.py
│   ├── country_util.py
│   ├── custom_exceptions.py
│   ├── decorators.py
│   ├── extensions.py
│   ├── friends_util.py
│   ├── hashing_util.py
│   ├── image_util.py
│   ├── immutable.py
│   ├── input_sanitization.py
│   ├── json_util.py
│   ├── llm_util.py
│   ├── models.py
│   ├── notifications.py
│   ├── qol_util.py
│   ├── scripts.py
│   ├── security_util.py
│   └── totp_util.py
└── wsgi.py

```

## Product features

- Sign up, login, logout, and email verification; optional **2FA (TOTP)**
- News pages by country/category; stories with **reactions** (like/dislike)
- **Threaded comments** with aggregate counts and HTML sanitization
- **Friendships**, **blocks**, and **real-time private messages** (Socket.IO)
- **In-app notifications** for events (new comment, friend request, etc.)
- Profiles with avatar/banner; **standardized image upload** served via R2

## Getting started (local dev)

### Prerequisites
- **Python 3.12**
- **MySQL** (with user/database created)
- **Redis** optional (for caching; you can use SimpleCache in dev)
- (Optional) Local SMTP tool (MailHog, etc.)

### Installation
```bash
git clone https://github.com/Infomundi-Project/website.git
cd website
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
````

### Environment variables

Create a `.env` file (or export in your shell) with at least:

```
# Flask / session / security
SESSION_COOKIE_NAME=infomundi-session
SECRET_KEY=changeme

# Integrations
OPENAI_API_KEY=                         # optional (summaries)
CAPTCHA_SECRET_KEY=                     # Cloudflare Turnstile

TURNSTILE_SITE_KEY=
TURNSTILE_SECRET_KEY=

# Database
MYSQL_DATABASE=infomundi
MYSQL_HOST=127.0.0.1
MYSQL_USERNAME=infomundi
MYSQL_PASSWORD=changeme

# Cache
REDIS_HOST=127.0.0.1
REDIS_PASSWORD=

# Storage (Cloudflare R2 / S3-compatible)
R2_ENDPOINT=
R2_ACCESS_KEY=
R2_SECRET=
R2_TOKEN=

# Email (SMTP)
SMTP_SERVER=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=

# OAuth (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Other
WEBHOOK_URL=                            # For error alerts (optional)
WEBSITE_ROOT=/abs/path/to/project
LOCAL_ROOT=/abs/path/local
```

> Tip: use `python-dotenv` in dev to load `.env` automatically.


### Running the application

Development server:

```bash
export FLASK_APP=app.py
export FLASK_ENV=development
flask run
# or
python app.py
```

Open `http://localhost:5000`. Create a test account (if SMTP email isn’t configured,
make temporary adjustments in verification flows for local testing).



## Docker Compose (recommended)

Running Infomundi with Docker Compose is the **primary** way to develop and deploy the app. The stack consists of three core services:

- **infomundi-app** — the Flask application (Gunicorn + eventlet)
- **infomundi-mysql** — MySQL database
- **infomundi-redis** — Redis for caching and Socket.IO message queue

> **Secrets**: never hardcode secrets in `docker-compose.yml`. Use a `.env` file (or Docker secrets) and reference variables like `${MYSQL_PASSWORD}`.

### 1) Files and directories

```

.
├─ website/                     # the Flask project (mounted into the app container)
│  ├─ app.py
│  ├─ wsgi.py
│  ├─ requirements.txt
│  ├─ static/
│  ├─ templates/
│  ├─ website\_scripts/
│  └─ sql/infomundi.sql         # optional: can be auto-imported on first run
├─ docker-compose.yml
└─ .env                         # holds secrets used by compose (NOT committed)

````

### 2) Minimal compose

Below is a pared-down compose excerpt that shows only what is needed to run **infomundi-app** with MySQL and Redis. Replace values via your `.env`.

```yaml
services:
  infomundi-mysql:
    image: mysql:8
    container_name: infomundi-mysql
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE:-infomundi}
      MYSQL_USER: ${MYSQL_USERNAME:-infomundi}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - infomundi_mysql_data:/var/lib/mysql
      # Optional: auto-load schema and seed on first boot
      - ./website/sql:/docker-entrypoint-initdb.d:ro
      # Optional: custom MySQL config
      # - ./conf/my.cnf:/etc/mysql/my.cnf:ro
    ports:
      - "127.0.0.1:3306:3306"
    networks:
      - infomundi-intranet
    restart: unless-stopped

  infomundi-redis:
    image: redis:7-alpine
    container_name: infomundi-redis
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}"]
    volumes:
      - infomundi_redis_data:/data
    networks:
      - infomundi-intranet
    restart: unless-stopped

  infomundi-app:
    image: python:3.12-alpine
    container_name: infomundi-app
    working_dir: /app
    volumes:
      - ./website:/app:ro
      - ./website/static:/app/static
      - ./website/data:/app/data
      - infomundi-app-pip-cache:/root/.cache/pip
      # Optional (dev): map __pycache__ to avoid container bloat
      # - ./website/__pycache__:/app/__pycache__
      # - ./website/website_scripts/__pycache__:/app/website_scripts/__pycache__
    environment:
      # Core app paths
      WEBSITE_ROOT: "/app"
      LOCAL_ROOT: "/app"
      SESSION_COOKIE_NAME: "infomundi_session"
      BASE_DOMAIN: ${BASE_DOMAIN}

      # Database
      MYSQL_HOST: "infomundi-mysql"
      MYSQL_USERNAME: ${MYSQL_USERNAME}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}

      # Redis (cache + Socket.IO message queue)
      REDIS_HOST: "infomundi-redis"
      REDIS_PASSWORD: ${REDIS_PASSWORD}

      # OPTIONAL integrations (only set if you actually use them)
      SECRET_KEY: ${SECRET_KEY}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      SMTP_SERVER: ${SMTP_SERVER}
      SMTP_PORT: ${SMTP_PORT:-587}
      SMTP_USERNAME: ${SMTP_USERNAME}
      SMTP_PASSWORD: ${SMTP_PASSWORD}
      R2_ENDPOINT: ${R2_ENDPOINT}
      R2_ACCESS_KEY: ${R2_ACCESS_KEY}
      R2_SECRET: ${R2_SECRET}
      R2_TOKEN: ${R2_TOKEN}
      TURNSTILE_SITE_KEY: ${TURNSTILE_SITE_KEY}
      TURNSTILE_SECRET_KEY: ${TURNSTILE_SECRET_KEY}
      HMAC_KEY: ${HMAC_KEY}
      WEBHOOK_URL: ${WEBHOOK_URL}
    expose:
      - "8000"
    # For local testing without a reverse proxy, also publish the port:
    # ports:
    #   - "127.0.0.1:8000:8000"
    command: >
      sh -lc "apk add --no-cache libmagic &&
              python -m pip install --upgrade pip &&
              pip install -r requirements.txt &&
              gunicorn --worker-class eventlet --workers ${GUNICORN_WORKERS:-2}
                       --bind 0.0.0.0:8000 wsgi:app"
    depends_on:
      - infomundi-mysql
      - infomundi-redis
      # If you run a separate CAPTCHA microservice, add it here as well and configure CAP_* envs.
      # - cap
    networks:
      - infomundi-network      # public edge/reverse proxy network (e.g., nginx)
      - infomundi-intranet     # private network for DB/Redis
    restart: unless-stopped

volumes:
  infomundi-app-pip-cache:
  infomundi_mysql_data:
  infomundi_redis_data:

networks:
  infomundi-network:
    name: infomundi-network
  infomundi-intranet:
    name: infomundi-intranet
````

**Notes on the app container**

* Uses the official `python:3.12-alpine` image.
* Installs Python dependencies on boot (cached via the `infomundi-app-pip-cache` volume).
* Serves via **Gunicorn** + **eventlet** on port **8000**.
* Attaches to two networks:

  * `infomundi-intranet`: private communication with MySQL and Redis.
  * `infomundi-network`: fronted by your reverse proxy (e.g., nginx) in production.

### 3) The `.env` file (compose-level)

Create a `.env` file *next to* `docker-compose.yml`. This file is read automatically by Docker Compose.

```dotenv
# Database (required)
MYSQL_ROOT_PASSWORD=change-me
MYSQL_DATABASE=infomundi
MYSQL_USERNAME=infomundi
MYSQL_PASSWORD=change-me

# Redis (required)
REDIS_PASSWORD=change-me

# App basics
BASE_DOMAIN=infomundi.local
SECRET_KEY=generate-a-random-hex
ENCRYPTION_KEY=generate-a-random-hex
HMAC_KEY=generate-a-random-hex

# Optional integrations (fill only if used)
OPENAI_API_KEY=
SMTP_SERVER=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
R2_ENDPOINT=
R2_ACCESS_KEY=
R2_SECRET=
R2_TOKEN=
TURNSTILE_SITE_KEY=
TURNSTILE_SECRET_KEY=
WEBHOOK_URL=

# Gunicorn tuning
GUNICORN_WORKERS=2
```

> Tip: For production, consider **Docker secrets** or a secret manager instead of `.env`.

### 4) Start-up

**First run (local):**

```bash
# Start database and cache first
docker compose up -d infomundi-mysql infomundi-redis

# (Optional) If not mounting sql/ as init, import schema manually:
# docker compose exec -T infomundi-mysql sh -lc 'exec mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' < website/sql/infomundi.sql

# Start the app
docker compose up -d infomundi-app

# Tail logs
docker compose logs -f infomundi-app
```

**Seeding reference data** (categories, publishers, countries, etc.):

```bash
docker compose exec infomundi-app python insert_feeds_to_database.py
# Optional:
docker compose exec infomundi-app python get_statistics.py
docker compose exec infomundi-app python create_cache.py
```

Open:

* **Direct (dev)**: [http://localhost:8000](http://localhost:8000)  *(only if you mapped the port in `ports:`)*
* **Behind reverse proxy (prod)**: use your proxy host on `infomundi-network` (see Deployment section).

### 5) Common operations

```bash
# Recreate app after changing requirements.txt
docker compose up -d --force-recreate --no-deps infomundi-app

# Shell into the app container
docker compose exec infomundi-app sh

# Apply DB migrations / maintenance scripts
docker compose exec infomundi-app python some_script.py

# Stop all
docker compose down
```

### 6) Tuning & production tips (infomundi-app)

* **Workers**: `GUNICORN_WORKERS` defaults to 2 here; tune based on CPU/RAM. With **Socket.IO**, keep to **eventlet** workers and use a **Redis** message queue for horizontal scaling.
* **Static assets**: `Flask-Assets` bundles are generated at runtime. For heavy traffic, prebuild assets in a CI step or bake a dedicated image.
* **Health checks**: add a simple `/healthz` route and configure a Compose/Orchestrator healthcheck for the app container.
* **Reverse proxy**: terminate TLS at nginx (or your edge), pass traffic to `infomundi-app:8000` on `infomundi-network`.
* **Persistence**: MySQL and Redis volumes (`infomundi_mysql_data`, `infomundi_redis_data`) are persisted by Compose. Back them up before upgrades.

### 7) Development variant

The repository also includes a development-oriented service (e.g., `dev-infomundi`) that mirrors `infomundi-app` but targets a separate dev DB/Redis and may publish port 8000 directly. Use it for bleeding-edge testing without touching production data.


## Jobs and helper scripts

* `insert_feeds_to_database.py`: loads RSS sources (categories/publishers).
* `collect_world_data.py`: updates JSONs with indicators (stocks, currencies, crypto).
* `get_statistics.py` / `create_cache.py`: initialize/update caches used by pages.
* Schedule via **cron** (or Celery beat) in production to keep data fresh.

## API (overview)

Main **JSON** routes, consumed via AJAX on the front end:

* `GET /api/get_stories` — list stories (filters by country/category, pagination).
* `POST /api/comments` — create comment (threaded); `GET /api/comments/get/<page_id>`.
* Reactions: `POST /api/story/<action>`, `POST /api/comments/<id>/<action>`.
* Social: `POST /api/friends` (requests), `POST /api/user/<id>/block` (block).
* Profile/images: `POST /api/user/image/<category>` (avatar/banner/wallpaper).
* Notifications: `GET /api/notifications`, `POST /api/notifications/<id>/read`.

**Authorization and protection**: `@api_login_required` decorators + **rate limiting**.

## Real time (Socket.IO)

**WebSocket** events for private messages and presence:

* `send_message` → persists to MySQL and emits `receive_message` to the recipient.
* **Typing** and **read** indicators.
* In production, use **Gunicorn** with **eventlet** workers; to scale horizontally,
  configure a *message queue* (e.g., Redis) in `socketio.init_app(...)`.

## Security

* **Passwords** with **Argon2id**; **2FA (TOTP)** with encrypted secret.
* **User emails** encrypted (**AES-GCM**) and **HMAC** fingerprint for lookups.
* **HTML sanitization** in comments (Bleach) and size limits.
* **CAPTCHA**: Cloudflare Turnstile (server-side verify) + custom image CAPTCHA.

## Caching and performance

* **Flask-Caching (Redis)** on hot paths (home/news) with *memoize* (1h/6h).
* **Flask-Assets** generates `gen/*.js` and `gen/*.css` bundles to reduce requests.
* **/static/** with aggressive **Cache-Control** (30 days) and option to serve via CDN/Nginx.

## Deployment

* Recommended **container** (code in `/app`), using **Gunicorn** with **eventlet**:

  ```bash
  gunicorn -w 1 --worker-class eventlet -b 0.0.0.0:5000 app:app
  ```
* **Nginx/Proxy** in front for TLS and static assets (or use CDN/Cloudflare).
* **HTTPS** required (cookies `Secure`; cookie domain via `BASE_DOMAIN`).
* **Cloudflare R2** for uploads — ensure keys/bucket and public domain are set.
* **SMTP** with STARTTLS: configure SPF/DKIM for the production sender.
* **Jobs**: schedule `collect_world_data.py`, RSS fetching, and statistics.

## Troubleshooting

* **MySQL**: prefer `MYSQL_HOST=127.0.0.1` (TCP). Review environment variables.
* **Front-end dependencies**: install `jsmin/cssmin` filters so Flask-Assets can rebuild bundles.
* **External services**: if not using OpenAI/Google OAuth in dev, disable routes or provide dummy keys.

## Roadmap and improvements

* Split `api.py` (1700+ lines) by domain (e.g., `comments_api`, `friends_api`, etc.).
* Reorganize `scripts.py` into focused modules (finance, parsing, etc.).
* Improve crawling and cache refresh (avoid stale data).
* Scale Socket.IO with a message queue and add chat history pagination.
* Fix model nits (duplicate fields) and consolidate friendship/notifications utilities.
* Implement a future **reputation system** and stub pages (e.g., Donations, Admin).
