markdown
<div align="center">

![Logo do Infomundi](https://raw.githubusercontent.com/behindsecurity/behindsecurity/refs/heads/main/images/infomundi-nobg.webp)

[![Codacy Badge](https://app.codacy.com/project/badge/Grade/3549171b5ed14423b31b3138afdf80ee)](https://app.codacy.com?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
![Python](https://img.shields.io/badge/Python-3.12.7-blue?style=social&logo=python&logoColor=black)
![Flask](https://img.shields.io/badge/3.1.0-black?style=social&logo=flask&logoColor=black&label=Flask)
![MySQL](https://img.shields.io/badge/MySQL-9.0.1-blue?style=social&logo=mysql&logoColor=black)
![Bootstrap 5](https://img.shields.io/badge/5.3.x-blue?style=social&logo=bootstrap&logoColor=black&label=Bootstrap)

</div>

# Infomundi — Plataforma de notícias e comunidade

Aplicação **Flask** monolítica com renderização no servidor, uma **REST API** e **WebSockets** para recursos em tempo real. Back-end em Python (Flask 3.x + SQLAlchemy/MySQL), front-end com **Jinja2** + **Bootstrap 5** e JavaScript vanilla; **Redis** para cache e **Cloudflare R2** para armazenamento de imagens.

> Este README resume a arquitetura e o fluxo de trabalho do projeto Infomundi e documenta como desenvolver e implantar.

---

## Tabela de Conteúdos
- [Visão geral](#visão-geral)
- [Stack e componentes principais](#stack-e-componentes-principais)
- [Estrutura de pastas](#estrutura-de-pastas)
- [Funcionalidades do produto](#funcionalidades-do-produto)
- [Primeiros passos (dev local)](#primeiros-passos-dev-local)
  - [Pré-requisitos](#pré-requisitos)
  - [Instalação](#instalação)
  - [Variáveis de ambiente](#variáveis-de-ambiente)
  - [Executando a aplicação](#executando-a-aplicação)
- [Tarefas e scripts auxiliares](#tarefas-e-scripts-auxiliares)
- [API (visão geral)](#api-visão-geral)
- [Tempo real (Socket.IO)](#tempo-real-socketio)
- [Segurança](#segurança)
- [Cache e performance](#cache-e-performance)
- [Implantação](#implantação)
- [Solução de problemas](#solução-de-problemas)
- [Roadmap e melhorias](#roadmap-e-melhorias)

---

## Visão geral

**Infomundi** é uma plataforma de descoberta de notícias com recursos sociais (comentários, reações, amizades e mensagens). O app segue **MVC** usando **Flask Blueprints** para separar **views** (páginas HTML), **auth** (autenticação/contas) e **api** (endpoints JSON). O front-end é renderizado no servidor (bom SEO e primeiro paint rápido) e é aprimorado por AJAX/WebSocket para conteúdo dinâmico (notificações, comentários e chat).

## Stack e componentes principais

- **Back-end**
  - Python 3.12, Flask 3.x, Flask-Login, Flask-Limiter, Flask-SocketIO
  - SQLAlchemy (MySQL)
  - Flask-Assets para empacotar/minificar CSS/JS
  - Redis (Flask-Caching) para cache
- **Front-end**
  - Jinja2 (templates), Bootstrap 5 (UI responsiva), JS vanilla (módulos em `static/js`)
- **Infra**
  - Cloudflare R2 (compatível com S3) para upload de imagens (avatar, banner etc.)
  - SMTP para e-mails transacionais (verificação de conta, redefinição de senha, contato)
  - (Opcional) Google OAuth
- **Segurança**
  - **2FA TOTP**, **Argon2id** para senhas e **AES-GCM** + HMAC para e-mails de usuários
  - **Cloudflare Turnstile** e **CAPTCHA de imagem customizado** para antispam
- **Tempo real**
  - WebSockets via Flask-SocketIO (mensagens, indicadores de digitação, recibos de leitura)

## Estrutura de pastas

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

## Funcionalidades do produto

- Cadastro, login, logout e verificação por e-mail; **2FA (TOTP)** opcional
- Páginas de notícias por país/categoria; histórias com **reações** (curtir/não curtir)
- **Comentários encadeados** com contagens agregadas e sanitização de HTML
- **Amizades**, **bloqueios** e **mensagens privadas em tempo real** (Socket.IO)
- **Notificações in-app** para eventos (novo comentário, solicitação de amizade etc.)
- Perfis com avatar/banner; **upload de imagem padronizado** servido via R2

## Primeiros passos (dev local)

### Pré-requisitos
- **Python 3.12**
- **MySQL** (com usuário/banco criados)
- **Redis** opcional (para cache; em dev, pode usar SimpleCache)
- (Opcional) Ferramenta de SMTP local (MailHog etc.)

### Instalação
```bash
git clone https://github.com/Infomundi-Project/website.git
cd website
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Variáveis de ambiente

Crie um arquivo `.env` (ou exporte no seu shell) com pelo menos:

```
# Flask / sessão / segurança
SESSION_COOKIE_NAME=infomundi-session
SECRET_KEY=changeme

# Integrações
OPENAI_API_KEY=                         # opcional (sumários)
CAPTCHA_SECRET_KEY=                     # Cloudflare Turnstile
CAP_SITE_KEY=

# Banco de dados
MYSQL_DATABASE=infomundi
MYSQL_HOST=127.0.0.1
MYSQL_USERNAME=infomundi
MYSQL_PASSWORD=changeme

# Cache
REDIS_HOST=127.0.0.1
REDIS_PASSWORD=

# Storage (Cloudflare R2 / compatível S3)
R2_ENDPOINT=
R2_ACCESS_KEY=
R2_SECRET=
R2_TOKEN=

# E-mail (SMTP)
SMTP_SERVER=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=

# OAuth (opcional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Outros
WEBHOOK_URL=                            # Para alertas de erro (opcional)
WEBSITE_ROOT=/abs/path/to/project
LOCAL_ROOT=/abs/path/local
```

> Dica: use `python-dotenv` em dev para carregar o `.env` automaticamente.

### Executando a aplicação

Servidor de desenvolvimento:

```bash
export FLASK_APP=app.py
export FLASK_ENV=development
flask run
# ou
python app.py
```

Abra `http://localhost:5000`. Crie uma conta de teste (se o e-mail SMTP não estiver configurado,
faça ajustes temporários nos fluxos de verificação para testes locais).

## Docker Compose (recomendado)

Executar o Infomundi com Docker Compose é a maneira **principal** de desenvolver e implantar o app. A stack consiste em três serviços centrais:

- **infomundi-app** — aplicação Flask (Gunicorn + eventlet)
- **infomundi-mysql** — banco MySQL
- **infomundi-redis** — Redis para cache e fila de mensagens do Socket.IO

> **Segredos**: nunca faça hardcode de segredos no `docker-compose.yml`. Use um `.env` (ou Docker secrets) e referencie variáveis como `${MYSQL_PASSWORD}`.

### 1) Arquivos e diretórios

```
.
├─ website/                     # projeto Flask (montado dentro do container app)
│  ├─ app.py
│  ├─ wsgi.py
│  ├─ requirements.txt
│  ├─ static/
│  ├─ templates/
│  ├─ website_scripts/
│  └─ sql/infomundi.sql         # opcional: pode ser importado automaticamente na primeira execução
├─ docker-compose.yml
└─ .env                         # guarda segredos usados pelo compose (NÃO versionar)
```

### 2) Compose mínimo

Abaixo, um trecho reduzido de compose que mostra apenas o necessário para rodar **infomundi-app** com MySQL e Redis. Substitua valores via seu `.env`.

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
      # Opcional: carregar schema/seed automaticamente no primeiro boot
      - ./website/sql:/docker-entrypoint-initdb.d:ro
      # Opcional: config MySQL customizada
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
      # Opcional (dev): mapear __pycache__ para evitar crescimento do container
      # - ./website/__pycache__:/app/__pycache__
      # - ./website/website_scripts/__pycache__:/app/website_scripts/__pycache__
    environment:
      # Caminhos básicos do app
      WEBSITE_ROOT: "/app"
      LOCAL_ROOT: "/app"
      SESSION_COOKIE_NAME: "infomundi_session"
      BASE_DOMAIN: ${BASE_DOMAIN}

      # Banco de dados
      MYSQL_HOST: "infomundi-mysql"
      MYSQL_USERNAME: ${MYSQL_USERNAME}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}

      # Redis (cache + fila do Socket.IO)
      REDIS_HOST: "infomundi-redis"
      REDIS_PASSWORD: ${REDIS_PASSWORD}

      # Integrações OPCIONAIS (defina somente se usar)
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
    # Para testes locais sem proxy reverso, publique a porta:
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
      # Se você rodar um microserviço de CAPTCHA separado, adicione aqui e configure as variáveis CAP_*.
      # - cap
    networks:
      - infomundi-network      # rede pública/borda (ex.: nginx)
      - infomundi-intranet     # rede privada para DB/Redis
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
```

**Notas sobre o container do app**

* Usa a imagem oficial `python:3.12-alpine`.
* Instala dependências Python no boot (cache via volume `infomundi-app-pip-cache`).
* Serve via **Gunicorn** + **eventlet** na porta **8000**.
* Conecta-se a duas redes:
  * `infomundi-intranet`: comunicação privada com MySQL e Redis.
  * `infomundi-network`: exposta por seu proxy reverso (ex.: nginx) em produção.

### 3) O arquivo `.env` (nível do compose)

Crie um `.env` ao lado do `docker-compose.yml`. O Docker Compose o lê automaticamente.

```dotenv
# Banco de dados (obrigatório)
MYSQL_ROOT_PASSWORD=change-me
MYSQL_DATABASE=infomundi
MYSQL_USERNAME=infomundi
MYSQL_PASSWORD=change-me

# Redis (obrigatório)
REDIS_PASSWORD=change-me

# Básico do app
BASE_DOMAIN=infomundi.local
SECRET_KEY=generate-a-random-hex
ENCRYPTION_KEY=generate-a-random-hex
HMAC_KEY=generate-a-random-hex

# Integrações opcionais (preencha somente se usadas)
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

# Tuning do Gunicorn
GUNICORN_WORKERS=2
```

> Dica: em produção, considere **Docker secrets** ou um gerenciador de segredos em vez de `.env`.

### 4) Inicialização

**Primeira execução (local):**

```bash
# Suba banco e cache primeiro
docker compose up -d infomundi-mysql infomundi-redis

# (Opcional) Se não montar sql/ como init, importe o schema manualmente:
# docker compose exec -T infomundi-mysql sh -lc 'exec mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' < website/sql/infomundi.sql

# Suba o app
docker compose up -d infomundi-app

# Acompanhe logs
docker compose logs -f infomundi-app
```

**Seeding de dados de referência** (categorias, publishers, países etc.):

```bash
docker compose exec infomundi-app python insert_feeds_to_database.py
# Opcional:
docker compose exec infomundi-app python get_statistics.py
docker compose exec infomundi-app python create_cache.py
```

Abra:

* **Direto (dev)**: [http://localhost:8000](http://localhost:8000)  *(apenas se mapeou a porta em `ports:`)*
* **Atrás do proxy reverso (prod)**: use seu host do proxy em `infomundi-network` (veja a seção de Implantação).

### 5) Operações comuns

```bash
# Recriar o app após mudar requirements.txt
docker compose up -d --force-recreate --no-deps infomundi-app

# Shell no container do app
docker compose exec infomundi-app sh

# Aplicar migrações/manutenção no DB
docker compose exec infomundi-app python some_script.py

# Parar tudo
docker compose down
```

### 6) Tuning & dicas de produção (infomundi-app)

* **Workers**: `GUNICORN_WORKERS` default 2; ajuste conforme CPU/RAM. Com **Socket.IO**, mantenha workers **eventlet** e use **Redis** como fila para escalar horizontalmente.
* **Assets estáticos**: bundles do `Flask-Assets` são gerados em runtime. Para alto tráfego, pré-construa em CI ou bake uma imagem dedicada.
* **Health checks**: adicione uma rota `/healthz` simples e configure um healthcheck no Compose/orquestrador para o container do app.
* **Proxy reverso**: termine TLS no nginx (ou na borda), encaminhe para `infomundi-app:8000` em `infomundi-network`.
* **Persistência**: volumes do MySQL e Redis (`infomundi_mysql_data`, `infomundi_redis_data`) são persistidos pelo Compose. Faça backup antes de upgrades.

### 7) Variante de desenvolvimento

O repositório também inclui um serviço voltado a desenvolvimento (ex.: `dev-infomundi`) que espelha `infomundi-app`, mas aponta para DB/Redis de dev separados e pode publicar a porta 8000 diretamente. Use para testes sem tocar dados de produção.

## Tarefas e scripts auxiliares

* `insert_feeds_to_database.py`: carrega fontes RSS (categorias/publishers).
* `collect_world_data.py`: atualiza JSONs com indicadores (ações, moedas, cripto).
* `get_statistics.py` / `create_cache.py`: inicializam/atualizam caches usados pelas páginas.
* Agende via **cron** (ou Celery beat) em produção para manter dados atualizados.

## API (visão geral)

Principais rotas **JSON**, consumidas via AJAX no front-end:

* `GET /api/get_stories` — lista histórias (filtros por país/categoria, paginação).
* `POST /api/comments` — cria comentário (encadeado); `GET /api/comments/get/<page_id>`.
* Reações: `POST /api/story/<action>`, `POST /api/comments/<id>/<action>`.
* Social: `POST /api/friends` (solicitações), `POST /api/user/<id>/block` (bloqueio).
* Perfil/imagens: `POST /api/user/image/<category>` (avatar/banner/wallpaper).
* Notificações: `GET /api/notifications`, `POST /api/notifications/<id>/read`.

**Autorização e proteção**: decoradores `@api_login_required` + **rate limiting**.

## Tempo real (Socket.IO)

Eventos **WebSocket** para mensagens privadas e presença:

* `send_message` → persiste no MySQL e emite `receive_message` ao destinatário.
* Indicadores de **digitando** e **lido**.
* Em produção, use **Gunicorn** com **eventlet**; para escalar horizontalmente,
  configure uma *fila de mensagens* (ex.: Redis) em `socketio.init_app(...)`.

## Segurança

* **Senhas** com **Argon2id**; **2FA (TOTP)** com segredo criptografado.
* **E-mails de usuários** criptografados (**AES-GCM**) e **HMAC** para fingerprint nas consultas.
* **Sanitização de HTML** em comentários (Bleach) e limites de tamanho.
* **CAPTCHA**: Cloudflare Turnstile (verificação server-side) + CAPTCHA de imagem customizado.

## Cache e performance

* **Flask-Caching (Redis)** em rotas quentes (home/news) com *memoize* (1h/6h).
* **Flask-Assets** gera bundles `gen/*.js` e `gen/*.css` para reduzir requisições.
* **/static/** com **Cache-Control** agressivo (30 dias) e opção de servir via CDN/Nginx.

## Implantação

* Recomendado **container** (código em `/app`), usando **Gunicorn** com **eventlet**:

  ```bash
  gunicorn -w 1 --worker-class eventlet -b 0.0.0.0:5000 app:app
  ```
* **Nginx/Proxy** na frente para TLS e assets estáticos (ou use CDN/Cloudflare).
* **HTTPS** obrigatório (cookies `Secure`; domínio do cookie via `BASE_DOMAIN`).
* **Cloudflare R2** para uploads — garanta chaves/bucket e domínio público configurados.
* **SMTP** com STARTTLS: configure SPF/DKIM para o remetente de produção.
* **Tarefas**: agende `collect_world_data.py`, busca de RSS e estatísticas.

## Solução de problemas

* **MySQL**: prefira `MYSQL_HOST=127.0.0.1` (TCP). Revise variáveis de ambiente.
* **Dependências de front-end**: instale filtros `jsmin/cssmin` para o Flask-Assets reconstruir bundles.
* **Serviços externos**: se não usar OpenAI/Google OAuth em dev, desabilite rotas ou forneça chaves dummy.

## Roadmap e melhorias

* Dividir `api.py` (1700+ linhas) por domínio (ex.: `comments_api`, `friends_api` etc.).
* Reorganizar `scripts.py` em módulos focados (finanças, parsing etc.).
* Melhorar crawling e refresh de cache (evitar dados obsoletos).
* Escalar Socket.IO com fila e adicionar paginação do histórico de chat.
* Corrigir detalhes de modelo (campos duplicados) e consolidar utilitários de amizade/notificações.
* Implementar futuro **sistema de reputação** e páginas stub (ex.: Doações, Admin).
