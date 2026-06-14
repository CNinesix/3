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
REPO_URL="${REPO_URL:-https://github.com/CNinesix/3.git}"   # repo to clone
BRANCH="${BRANCH:-claude/proxmox-pdf-editing-suite-5rxg9w}" # branch with the code
TUNNEL_TOKEN="${TUNNEL_TOKEN:-}"     # optional: Cloudflare Tunnel token
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

echo "==> Cloning $REPO_URL ($BRANCH) inside the container and starting the stack"
pct exec "$CTID" -- bash -lc "
  set -e
  git clone -b '$BRANCH' '$REPO_URL' /opt/pdfsuite
  cd /opt/pdfsuite
  [ -f .env ] || cp .env.example .env
  if [ -n '$TUNNEL_TOKEN' ]; then
    sed -i 's|^TUNNEL_TOKEN=.*|TUNNEL_TOKEN=$TUNNEL_TOKEN|' .env
    docker compose --profile tunnel up -d --build
  else
    docker compose up -d --build   # LAN only; add token + --profile tunnel later
  fi
"

IP="$(pct exec "$CTID" -- bash -lc "hostname -I | awk '{print \$1}'" 2>/dev/null || true)"
echo
echo "==> Done."
echo "    Container ID : $CTID"
echo "    Container IP : ${IP:-<container-ip>}"
echo "    LAN URL      : http://${IP:-<container-ip>}:9932   (login: pdf / 1)"
echo "    Public URL   : https://pdf.snmk.xyz  (via Cloudflare Tunnel — set TUNNEL_TOKEN)"
echo
echo "    >> Your container's LOCAL IP is: ${IP:-<run hostname -I in the container>}"
echo "    >> Use http://${IP:-<ip>}:9932 as the Cloudflare Tunnel Service URL,"
echo "       or http://gateway:3000 if using the bundled cloudflared."
