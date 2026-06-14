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

[ -f .env ] || { cp .env.example .env; echo "==> Created .env from template (edit it to change the password/secret)"; }

echo "==> Building and starting the stack"
docker compose up -d --build

IP="$(hostname -I | awk '{print $1}')"
echo
echo "==> Up. Open http://${IP}:8088   (login: pdf / 1)"
