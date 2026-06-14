#!/usr/bin/env bash
#
# Run this ON THE PROXMOX HOST (as root) to create a Debian LXC container
# that is ready to run Docker, then deploy the PDF Suite into it.
#
#   bash deploy/proxmox-create-lxc.sh
#
# Adjust the variables below to taste before running.
set -euo pipefail

# ---- settings --------------------------------------------------------------
CTID="${CTID:-9000}"                 # container ID (must be unused)
HOSTNAME="${HOSTNAME:-pdfsuite}"
DISK_GB="${DISK_GB:-12}"
CORES="${CORES:-2}"
RAM_MB="${RAM_MB:-2048}"
BRIDGE="${BRIDGE:-vmbr0}"
STORAGE="${STORAGE:-local-lvm}"      # rootfs storage
TPL_STORAGE="${TPL_STORAGE:-local}"  # where templates live
PASSWORD="${PASSWORD:-changeme}"     # root password for the container
TEMPLATE="debian-12-standard"
REPO_URL="${REPO_URL:-}"             # optional: git URL of this repo to clone
# ---------------------------------------------------------------------------

echo "==> Ensuring Debian 12 template is available"
pveam update >/dev/null 2>&1 || true
TPL_FILE="$(pveam available --section system | awk '/debian-12-standard/ {print $2}' | sort | tail -n1)"
if ! pveam list "$TPL_STORAGE" | grep -q "$TPL_FILE"; then
  pveam download "$TPL_STORAGE" "$TPL_FILE"
fi

echo "==> Creating LXC $CTID ($HOSTNAME)"
pct create "$CTID" "${TPL_STORAGE}:vztmpl/${TPL_FILE}" \
  --hostname "$HOSTNAME" \
  --cores "$CORES" \
  --memory "$RAM_MB" \
  --swap 512 \
  --rootfs "${STORAGE}:${DISK_GB}" \
  --net0 "name=eth0,bridge=${BRIDGE},ip=dhcp" \
  --features nesting=1,keyctl=1 \
  --unprivileged 1 \
  --onboot 1 \
  --password "$PASSWORD"

echo "==> Starting container"
pct start "$CTID"
sleep 6

echo "==> Installing Docker inside the container"
pct exec "$CTID" -- bash -lc '
  set -e
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y ca-certificates curl git
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
'

if [ -n "$REPO_URL" ]; then
  echo "==> Cloning $REPO_URL inside the container and starting the stack"
  pct exec "$CTID" -- bash -lc "
    set -e
    git clone '$REPO_URL' /opt/pdfsuite
    cd /opt/pdfsuite
    [ -f .env ] || cp .env.example .env
    docker compose up -d --build
  "
else
  echo "==> REPO_URL not set — copy this project into the container, then run:"
  echo "      pct exec $CTID -- bash -lc 'cd /opt/pdfsuite && cp -n .env.example .env && docker compose up -d --build'"
fi

IP="$(pct exec "$CTID" -- bash -lc "hostname -I | awk '{print \$1}'" 2>/dev/null || true)"
echo
echo "==> Done."
echo "    Container ID : $CTID"
echo "    Open         : http://${IP:-<container-ip>}:8088"
echo "    Login        : pdf / 1   (page shows a decoy 'minimum 8 characters')"
