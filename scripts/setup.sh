#!/usr/bin/env bash
# Switchboard host bootstrap — Ubuntu 24.04 LTS. Idempotent.
# Usage: sudo bash scripts/setup.sh assistant.yourdomain.com
set -euo pipefail
DOMAIN="${1:-}"
[ -z "$DOMAIN" ] && { echo "Usage: sudo bash scripts/setup.sh <public-domain>"; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo/root."; exit 1; }
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> 1/8 System updates + essentials"
apt-get update && apt-get -y upgrade
apt-get -y install ufw fail2ban unattended-upgrades git curl sqlite3 \
  python3-venv python3-pip ffmpeg ca-certificates gnupg \
  debian-keyring debian-archive-keyring apt-transport-https

echo "==> 2/8 Automatic security updates"
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "==> 3/8 Firewall + brute-force protection"
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp
ufw --force enable
systemctl enable --now fail2ban

echo "==> 4/8 Node.js 22 (Agent SDK / Claude Code dependency)"
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get -y install nodejs
npm install -g @anthropic-ai/claude-code || true

echo "==> 5/8 Caddy (automatic HTTPS)"
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
apt-get update && apt-get -y install caddy
sed "s/REPLACE_DOMAIN/$DOMAIN/" "$REPO_DIR/deploy/Caddyfile.example" > /etc/caddy/Caddyfile
systemctl reload caddy

echo "==> 6/8 Service user + layout"
id -u switchboard &>/dev/null || useradd -m -s /bin/bash switchboard
mkdir -p /opt/switchboard/{app,personas,workspace,data}
cp -n "$REPO_DIR"/personas/*.md /opt/switchboard/personas/ 2>/dev/null || true
chown -R switchboard:switchboard /opt/switchboard

echo "==> 7/8 Python environment"
sudo -u switchboard python3 -m venv /opt/switchboard/venv
sudo -u switchboard /opt/switchboard/venv/bin/pip install --upgrade pip
sudo -u switchboard /opt/switchboard/venv/bin/pip install \
  fastapi "uvicorn[standard]" websockets python-telegram-bot \
  twilio apscheduler httpx claude-agent-sdk

echo "==> 8/8 Config + systemd unit"
if [ ! -f /opt/switchboard/.env ]; then
  sed "s/assistant.example.com/$DOMAIN/" "$REPO_DIR/.env.example" > /opt/switchboard/.env
  chown switchboard:switchboard /opt/switchboard/.env && chmod 600 /opt/switchboard/.env
fi
cp "$REPO_DIR/deploy/switchboard.service" /etc/systemd/system/switchboard.service
systemctl daemon-reload

cat <<MSG

Bootstrap complete. Next:
  1) nano /opt/switchboard/.env                  # fill keys (docs/configuration.md)
  2) provide src/ in /opt/switchboard/app        # docs/deployment.md
  3) systemctl enable --now switchboard && journalctl -u switchboard -f
MSG
