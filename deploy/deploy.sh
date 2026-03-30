#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy.sh — Deploy latest code to EC2
# Pulls from GitHub and restarts the gunicorn service.
# Usage:  bash deploy/deploy.sh <EC2_PUBLIC_IP>
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
EC2_IP="${1:-}"
KEY_FILE="${EC2_KEY_PAIR_FILE:-./../cloud-key-pair.pem}"
EC2_USER="ec2-user"
APP_DIR="/home/ec2-user/health-analytics"

if [ -z "$EC2_IP" ]; then
  echo "Usage: bash deploy.sh <EC2_PUBLIC_IP>"
  exit 1
fi

echo "=== Deploying to ${EC2_IP} ==="

ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_IP}" <<'REMOTE'
  set -euo pipefail
  APP_DIR="/home/ec2-user/health-analytics"

  echo "--- Git pull ---"
  cd "$APP_DIR"
  git pull

  echo "--- Install/update dependencies ---"
  pip3 install -r backend/requirements.txt --quiet

  echo "--- Restart service ---"
  sudo systemctl restart healthtrack
  echo "--- Deployment complete ---"
REMOTE

echo "=== Deploy finished! App is live at http://${EC2_IP}:5000 ==="
