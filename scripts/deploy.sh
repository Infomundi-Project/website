#!/bin/bash
# Deployment script for infomundi-app
# This script is allowed to run as root via sudoers with no password
# It restricts docker interaction to only what's needed for deployment

set -euo pipefail

COMPOSE_FILE="/root/docker/docker-compose.yml"
REPO_DIR="/opt/infomundi/website"
ALLOWED_ACTIONS=("pull" "restart" "status")

action="${1:-}"

case "$action" in
    pull)
        cd "$REPO_DIR"
        git fetch origin main
        git reset --hard origin/main
        git submodule update --init --recursive
        echo "Code pulled successfully"
        ;;
    restart)
        docker compose -f $COMPOSE_FILE restart infomundi-app
        echo "Application restarted"
        ;;
    status)
        docker ps --filter "name=infomundi-app" --format "{{.Status}}"
        ;;
    *)
        echo "Usage: $0 {pull|restart|status}"
        echo "Allowed actions: ${ALLOWED_ACTIONS[*]}"
        exit 1
        ;;
esac
