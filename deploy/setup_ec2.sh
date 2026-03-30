#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup_ec2.sh — One-time EC2 instance bootstrap
# Run this ONCE after launching a fresh Amazon Linux 2023 instance.
# Usage:  bash setup_ec2.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

echo "=== [1/7] Update system packages ==="
sudo dnf update -y

echo "=== [2/7] Install Python 3.11, pip, git ==="
sudo dnf install -y python3.11 python3.11-pip git

# Make python3 and pip3 point to Python 3.11
sudo alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.11 1

echo "=== [3/7] Install gunicorn system-wide ==="
sudo pip3 install --upgrade pip gunicorn

echo "=== [4/7] Clone / pull the project repository ==="
APP_DIR="/home/ec2-user/health-analytics"
if [ -d "$APP_DIR" ]; then
  cd "$APP_DIR" && git pull
else
  # Replace with your repo URL (can use PAT for private repos)
  REPO_URL="${GITHUB_REPO:-https://github.com/ShubhamDhanne/api-project}"
  git clone "$REPO_URL" "$APP_DIR"
fi

echo "=== [5/7] Install Python dependencies ==="
pip3 install -r "$APP_DIR/backend/requirements.txt"

echo "=== [6/7] Copy .env file ==="
if [ -f "$APP_DIR/.env" ]; then
  echo ".env already present."
else
  echo "WARNING: .env not found in $APP_DIR. Copy it manually before starting the app."
fi

echo "=== [7/7] Create systemd service ==="
sudo tee /etc/systemd/system/healthtrack.service > /dev/null <<EOF
[Unit]
Description=HealthTrack Flask Application
After=network.target

[Service]
User=ec2-user
WorkingDirectory=${APP_DIR}/backend
EnvironmentFile=${APP_DIR}/.env
ExecStart=/usr/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 wsgi:application
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable healthtrack
sudo systemctl start healthtrack

echo ""
echo "=== HealthTrack is now running on port 5000 ==="
echo "Check status:  sudo systemctl status healthtrack"
echo "View logs:     sudo journalctl -u healthtrack -f"
