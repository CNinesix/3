#!/usr/bin/env bash
#
# Run this INSIDE an existing Debian/Ubuntu LXC or VM to install Docker
# and bring up the PDF Suite. Run from the project root:
#
#   bash deploy/install.sh
#
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi

[ -f .env ] || { cp .env.example .env; echo "==> Created .env from template (edit it to change the password/secret/token)"; }

# Start the Cloudflare tunnel too only if a real token is present in .env.
TOKEN="$(grep -E '^TUNNEL_TOKEN=' .env | cut -d= -f2-)"
if [ -n "$TOKEN" ] && [ "$TOKEN" != "paste-your-cloudflare-tunnel-token-here" ]; then
  echo "==> Building and starting the stack (with Cloudflare tunnel)"
  docker compose --profile tunnel up -d --build
else
  echo "==> Building and starting the stack (LAN only — set TUNNEL_TOKEN in .env for pdf.snmk.xyz)"
  docker compose up -d --build
fi

IP="$(hostname -I | awk '{print $1}')"
echo
echo "==> Up. (login: pdf / 1)"
echo "    On LAN  : http://${IP}:9932"
echo "    Public  : https://pdf.snmk.xyz   (via Cloudflare Tunnel once TUNNEL_TOKEN is set)"
echo
echo "    >> This host's LOCAL IP is: ${IP}"
echo "    >> Cloudflare Tunnel Service URL: http://${IP}:9932  (or http://gateway:3000)"
