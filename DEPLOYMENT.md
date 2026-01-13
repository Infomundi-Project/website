# Deployment Guide

This document explains how production deployments work and how to manage them.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [GitHub Actions Pipeline](#github-actions-pipeline)
- [Self-Hosted Runner](#self-hosted-runner)
- [Required Secrets](#required-secrets)
- [Deploy Script Reference](#deploy-script-reference)
- [Manual Deployment](#manual-deployment)
- [Rollback Procedures](#rollback-procedures)
- [Accessing Production](#accessing-production)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)

---

## Overview

Deployments are automated via GitHub Actions. When code is pushed to `main`, the pipeline:

1. Saves current commit for potential rollback
2. Pulls latest code to production server
3. Runs database migrations
4. Restarts the application
5. Runs health check
6. Rolls back automatically if health check fails
7. Notifies Discord of success/failure

**Important:** There is no staging environment. Merges to `main` deploy directly to production.

---

## Architecture

```
┌─────────────────┐      push to main      ┌──────────────────┐
│  GitHub Repo    │ ────────────────────▶  │  GitHub Actions  │
└─────────────────┘                        └────────┬─────────┘
                                                    │
                                                    │ runs on
                                                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Production Server                         │
│  ┌─────────────────┐    ┌─────────────────────────────────┐ │
│  │ GitHub Actions  │    │  Docker Compose Stack           │ │
│  │ Runner (self-   │───▶│  ┌─────────────────────────┐    │ │
│  │ hosted)         │    │  │ infomundi-app (Flask)   │    │ │
│  └─────────────────┘    │  ├─────────────────────────┤    │ │
│                         │  │ infomundi-mysql         │    │ │
│                         │  ├─────────────────────────┤    │ │
│                         │  │ infomundi-redis         │    │ │
│                         │  └─────────────────────────┘    │ │
│                         └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Production Paths

| Path | Purpose |
|------|---------|
| `/opt/infomundi/website` | Git repository clone |
| `/opt/infomundi/scripts/deploy.sh` | Deployment script |
| `/opt/infomundi/docker/docker-compose.yml` | Production Docker Compose file |

---

## GitHub Actions Pipeline

The pipeline is defined in `.github/workflows/deploy.yml`.

### Trigger

```yaml
on:
  push:
    branches:
      - main
```

Only pushes to `main` trigger deployment. Feature branches do not deploy.

### Pipeline Steps

| Step | Action | On Failure |
|------|--------|------------|
| 1. Save rollback point | Records current commit hash | - |
| 2. Pull latest changes | `git fetch && git reset --hard origin/main` | Rollback |
| 3. Run migrations | `flask db upgrade` | Rollback |
| 4. Restart application | `docker compose restart infomundi-app` | Rollback |
| 5. Wait for startup | Sleep 40 seconds | - |
| 6. Health check | Check container status and logs | Rollback |
| 7. Notify Discord | Send success/failure embed | - |

### Automatic Rollback

If any step fails, the pipeline:
1. Resets git to the previous commit
2. Attempts to run migrations (may fail for irreversible migrations)
3. Restarts the application
4. Notifies Discord of the rollback

---

## Self-Hosted Runner

The GitHub Actions runner is installed on the production server itself.

### Runner Location

```
Server: connect.infomundi.net
User: deployment
Runner directory: /home/deployment/actions-runner
```

### Runner Service

The runner runs as a systemd service:

```bash
# Check runner status
sudo systemctl status actions.runner.Infomundi-Project-website.infomundi.service

# Restart runner if stuck
sudo systemctl restart actions.runner.Infomundi-Project-website.infomundi.service

# View runner logs
journalctl -u actions.runner.Infomundi-Project-website.infomundi.service -f
```

### Sudoers Configuration

The runner user has passwordless sudo access to the deploy script only:

```
# /etc/sudoers.d/github-runner
github-runner ALL=(ALL) NOPASSWD: /opt/infomundi/scripts/deploy.sh
```

This restricts the runner to only the allowed deployment actions.

---

## Required Secrets

Configure these in GitHub repo -> Settings -> Secrets and variables -> Actions if needed (already set up):

| Secret | Purpose | Example |
|--------|---------|---------|
| `DISCORD_WEBHOOK_URL` | Deployment notifications | `https://discord.com/api/webhooks/...` |

### Creating Discord Webhook

1. In Discord, go to Server Settings -> Integrations -> Webhooks
2. Create new webhook for your deployments channel
3. Copy webhook URL
4. Add as GitHub secret

---

## Deploy Script Reference

The deploy script (`/opt/infomundi/scripts/deploy.sh`) is the only interface for deployments.

### Available Commands

```bash
# Pull latest code from main
sudo /opt/infomundi/scripts/deploy.sh pull

# Restart the application container
sudo /opt/infomundi/scripts/deploy.sh restart

# Check container status
sudo /opt/infomundi/scripts/deploy.sh status

# Get current commit hash
sudo /opt/infomundi/scripts/deploy.sh get-commit

# Run database migrations
sudo /opt/infomundi/scripts/deploy.sh migrate

# Check application health
sudo /opt/infomundi/scripts/deploy.sh healthcheck

# View recent logs
sudo /opt/infomundi/scripts/deploy.sh logs

# Rollback to specific commit
sudo /opt/infomundi/scripts/deploy.sh rollback <commit-hash>
```

### What Each Command Does

**pull:**
```bash
git fetch origin main
git reset --hard origin/main
git submodule update --init --recursive
```

**restart:**
```bash
docker compose -f /opt/infomundi/docker/docker-compose.yml restart infomundi-app
```

**healthcheck:**
- Verifies container is running
- Checks recent logs for errors/exceptions/tracebacks
- Returns exit code 0 (healthy) or 1 (unhealthy)

**rollback:**
- Validates commit hash format (7-40 hex chars)
- Runs `git reset --hard <commit>`
- Updates submodules

---

## Manual Deployment

If GitHub Actions fails or you need to deploy manually:

### SSH to Production

SSH server accepts public key authentication only.

```bash
ssh user@connect.infomundi.net
```

### RDP to Production

Production server also has RDP enabled. You need to use your SSH connection to forward the RDP port:

```bash
setsid nohup ssh -L 3389:localhost:3389 user@connect.infomundi.net -N &
```

And then use your favorite RDP client to connect to production using RDP. For instance,

```
xfreerdp /v:localhost /u:user /p:password
```

Remember, since it's a port forward, to connect via RDP, you'll need to pass "localhost" or "127.0.0.1" as the hostname, not the usual "connect.infomundi.net".

### Manual Deploy Steps

All actions can be done using [our Portainer instance](https://portainer.infomundi.net/).

```bash
# 1. Save current commit (for rollback)
current=$(/opt/infomundi/scripts/deploy.sh get-commit)
echo "Rollback point: $current"

# 2. Pull latest code
/opt/infomundi/scripts/deploy.sh pull

# 3. Run migrations
/opt/infomundi/scripts/deploy.sh migrate

# 4. Restart application
/opt/infomundi/scripts/deploy.sh restart

# 5. Wait and check health
sleep 40
/opt/infomundi/scripts/deploy.sh healthcheck

# 6. If unhealthy, rollback
/opt/infomundi/scripts/deploy.sh rollback $current
/opt/infomundi/scripts/deploy.sh restart
```

### Deploy Specific Branch/Commit

```bash
# SSH to server
cd /opt/infomundi/website

# Fetch all branches
git fetch --all

# Checkout specific branch (for testing - not recommended for production)
git checkout feature-branch
git pull origin feature-branch

# Or checkout specific commit
git checkout abc1234

# Update submodules
git submodule update --init --recursive

# Restart
sudo /opt/infomundi/scripts/deploy.sh restart
```

---

## Rollback Procedures

### Automatic Rollback

The pipeline automatically rolls back if:
- Migration fails
- Restart fails
- Health check fails

Check Discord for notification with rollback details.

### Manual Rollback

```bash
# 1. Find the commit to rollback to
cd /opt/infomundi/website
git log --oneline -10

# 2. Rollback to that commit
sudo /opt/infomundi/scripts/deploy.sh rollback <commit-hash>

# 3. Restart
sudo /opt/infomundi/scripts/deploy.sh restart

# 4. Verify
sudo /opt/infomundi/scripts/deploy.sh healthcheck
```

### Rollback Limitations

**Database migrations may not be reversible.** If a deployment included migrations that:
- Dropped columns/tables
- Renamed columns
- Deleted data

Rolling back the code won't restore the database. You may need to:
1. Restore from database backup
2. Write a compensating migration
3. Manually fix data

---

## Accessing Production

You can manage all containers via our Portainer instance at https://portainer.infomundi.net/

### SSH Access

```bash
ssh user@connect.infomundi.net
```

Keys should be distributed to team members who need production access.

### View Application Logs


```bash
# Recent logs (via deploy script)
sudo /opt/infomundi/scripts/deploy.sh logs

# Full logs
docker logs infomundi-app

# Follow logs in real-time
docker logs -f infomundi-app

# Logs since specific time
docker logs --since 1h infomundi-app
```

### Access Application Shell

```bash
# Python shell with app context
docker exec -it infomundi-app python

# Bash shell in container
docker exec -it infomundi-app bash

# Run one-off command
docker exec infomundi-app python -m utils.search_news
```

### Access Database

```bash
# MySQL shell
docker exec -it infomundi-mysql mysql -u infomundi -p

# Password is in production env
```

### Access Redis

```bash
docker exec -it infomundi-redis redis-cli -a [REDIS_PASSWORD]
```

---

## Troubleshooting

### Deployment Stuck

**Symptom:** GitHub Action shows "In progress" for too long

**Fix:**
1. Check if runner is online: GitHub -> Settings -> Actions -> Runners
2. If offline, SSH to server and restart runner service
3. If stuck job, cancel it in GitHub Actions UI

### Health Check Failing

**Symptom:** Deployment rolls back immediately after restart

**Debug:**
```bash
# Check what health check sees
sudo /opt/infomundi/scripts/deploy.sh healthcheck

# Check container status
docker ps -a | grep infomundi

# Check recent logs for errors
docker logs --since 2m infomundi-app 2>&1 | grep -i error
```

**Common causes:**
- Missing environment variable
- Database connection failed
- Port already in use
- Syntax error in Python code

### Container Won't Start

All containers are manageable via Portainer at https://portainer.infomundi.net/.

```bash
# Check container status
docker ps -a

# Check why it exited
docker logs infomundi-app

# Check docker compose config
docker compose -f /opt/infomundi/docker/docker-compose.yml config
```

### Migration Failed

```bash
# Check migration status
docker exec infomundi-app flask db current
docker exec infomundi-app flask db history

# See what migration tried to do
docker exec infomundi-app flask db show
```

### Runner Can't Execute Deploy Script?

**Symptom:** `Permission denied` errors

**Fix:** Check sudoers configuration:
```bash
sudo visudo -f /etc/sudoers.d/github-runner
# Should contain:
# github-runner ALL=(ALL) NOPASSWD: /opt/infomundi/scripts/deploy.sh
```

### Discord Notifications Not Working?

1. Check webhook URL is valid
2. Check secret is set in GitHub
3. Test webhook manually:
```bash
curl -H "Content-Type: application/json" \
  -d '{"content": "Test message"}' \
  "YOUR_WEBHOOK_URL"
```

---

## Known Limitations

### No Staging Environment

**Risk:** Bugs go directly to production.

**Mitigation:**
- Test thoroughly locally with Docker
- Use feature flags for risky changes
- Deploy during low-traffic hours

**Recommendation:** Set up a staging server that mirrors production.

### No Tests in Pipeline

**Risk:** Broken code can be deployed.

**Mitigation:**
- Run `pytest tests/` locally before pushing
- Require PR reviews

**Recommendation:** Add test step to pipeline before deploy.

### Basic Health Check

**Risk:** Only checks for error strings in logs, not actual functionality.

**Recommendation:** Add `/health` endpoint that checks:
- Database connection
- Redis connection
- Critical dependencies

---

## Production Environment Variables

Production environment is configured in docker compose file at `/opt/infomundi/docker/` or via Portainer.

Key variables that differ from development:

| Variable | Production Value | Notes |
|----------|------------------|-------|
| `FLASK_DEBUG` | `0` | Never enable debug in production |
| `BASE_URL` | `https://infomundi.net` | No trailing slash |
| `SESSION_COOKIE_SECURE` | `True` | Requires HTTPS |
| `R2_*` | Set | Cloudflare R2 credentials for media |
| `OPENAI_API_KEY` | Set | For AI features |

---

## Deployment Checklist

Before merging to main:

- [ ] Tested locally with `docker compose up`
- [ ] Ran `pytest tests/` (if applicable)
- [ ] Database migrations are reversible (or documented if not)
- [ ] No secrets/credentials in code
- [ ] PR reviewed by another developer
- [ ] Deployment during low-traffic hours (for risky changes)

After deployment:

- [ ] Check Discord for success notification
- [ ] Verify site is accessible
- [ ] Check key functionality works
- [ ] Monitor logs for errors: `sudo /opt/infomundi/scripts/deploy.sh logs`

---

## Emergency Contacts

| Who | Contact | When to Contact |
|------|---------|-----------------|
| ex-Maintainer | via discord, Infomundi private server  | Production is down, can't rollback |

---

## Server Details

| Item | Value |
|------|-------|
| Production Server IP | `connect.infomundi.net` |
| Hosting Provider | `Hostinger` |
| Domain Registrar | `Namecheap` |
| DNS Provider | `Cloudflare` |
| R2 Bucket Name | `bucket.infomundi.net` |

---

## Appendix: Production Docker Compose

The production `docker-compose.yml` at `/opt/infomundi/docker/docker-compose.yml` differs from the development one:

- Uses production environment variables
- May have different resource limits
- Uses production database credentials
- Connects to external services (R2, etc.)

If you need to modify it, SSH to the server and edit directly. Or, use our [Portainer](https://portainer.infomundi.net/#!/3/docker/stacks/prod?id=5&type=2&regular=true&orphaned=false&orphanedRunning=false) instance with your provided credentials. Changes to the repo's `docker-compose.yml` do not affect production.
