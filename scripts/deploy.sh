#!/bin/bash
# Deployment script for infomundi-app
# This script is allowed to run as root via sudoers with no password
# It restricts docker interaction to only what's needed for deployment

set -euo pipefail

COMPOSE_FILE="/root/docker/docker-compose.yml"
REPO_DIR="/opt/infomundi/website"
ALLOWED_ACTIONS=("pull" "restart" "status" "rollback" "get-commit" "healthcheck" "logs" "migrate")

action="${1:-}"
param="${2:-}"

case "$action" in
    pull)
        cd "$REPO_DIR"
        git fetch origin main
        git reset --hard origin/main
        git submodule update --init --recursive
        echo "Code pulled successfully"
        ;;
    restart)
        docker compose -f "$COMPOSE_FILE" restart infomundi-app
        echo "Application restarted"
        ;;
    status)
        docker ps --filter "name=infomundi-app" --format "{{.Status}}"
        ;;
    rollback)
        # Rollback to a specific commit hash
        if [[ -z "$param" ]]; then
            echo "Error: commit hash required"
            exit 1
        fi
        # Validate commit hash format (7-40 hex characters)
        if ! [[ "$param" =~ ^[a-f0-9]{7,40}$ ]]; then
            echo "Error: invalid commit hash format"
            exit 1
        fi
        cd "$REPO_DIR"
        git reset --hard "$param"
        git submodule update --init --recursive
        echo "Rolled back to $param"
        ;;
    get-commit)
        cd "$REPO_DIR"
        git rev-parse HEAD
        ;;
    healthcheck)
        # Check if container is running and healthy
        container_status=$(docker ps --filter "name=infomundi-app" --format "{{.Status}}" 2>/dev/null || echo "")
        if [[ -z "$container_status" ]]; then
            echo "Container not found"
            exit 1
        fi
        if ! echo "$container_status" | grep -q "Up"; then
            echo "Container not running: $container_status"
            exit 1
        fi
        # Check if gunicorn is responding (basic check via container logs)
        if docker logs --since 60s infomundi-app 2>&1 | grep -qi "error\|exception\|traceback"; then
            echo "Errors detected in container logs"
            exit 1
        fi
        echo "Healthy"
        ;;
    migrate)
        docker compose -f "$COMPOSE_FILE" exec -T infomundi-app flask db upgrade
        echo "Migrations applied successfully"
        ;;
    logs)
        # Get recent logs for debugging
        docker logs --since 90s infomundi-app 2>&1 | tail -50
        ;;
    *)
        echo "Usage: $0 {pull|restart|status|rollback <commit>|get-commit|healthcheck|logs|migrate}"
        echo "Allowed actions: ${ALLOWED_ACTIONS[*]}"
        exit 1
        ;;
esac
