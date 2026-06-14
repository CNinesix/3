#!/usr/bin/env bash
# ============================================================
# A2 Revenue OS — one-command installer / deployer.
#
# Run on the server that will host the a2.snmk.xyz origin, from inside a
# checkout of this repo:
#
#     sudo bash deploy/install.sh
#
# It is idempotent — safe to re-run after pulling new code (it will copy the
# updated files, reinstall deps and restart the services without touching your
# existing .env or database).
#
# Optional overrides (environment variables):
#   APP_DIR=/opt/a2ros           where the app is installed
#   DATA_DIR=/var/lib/a2ros      where the SQLite DB / data lives
#   SERVICE_USER=a2ros           system user the services run as
#   DOMAIN=a2.snmk.xyz           server_name for the Nginx vhost
#   INSTALL_NGINX=1              install + reload the Nginx vhost (default 1)
#   ENABLE_LETSENCRYPT=0         if 1, also obtain a Let's Encrypt cert
#   LETSENCRYPT_EMAIL=           email for certbot (required if the above is 1)
# ============================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/a2ros}"
DATA_DIR="${DATA_DIR:-/var/lib/a2ros}"
SERVICE_USER="${SERVICE_USER:-a2ros}"
DOMAIN="${DOMAIN:-a2.snmk.xyz}"
INSTALL_NGINX="${INSTALL_NGINX:-1}"
ENABLE_LETSENCRYPT="${ENABLE_LETSENCRYPT:-0}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}"

# Resolve the directory of the repo (this script lives in <repo>/deploy/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(dirname "$SCRIPT_DIR")"

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

[[ "$(id -u)" -eq 0 ]] || die "Please run as root (sudo bash deploy/install.sh)."

# ------------------------------------------------------------------ #
log "Installing system packages"
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq python3 python3-venv python3-pip rsync ca-certificates >/dev/null
  [[ "$INSTALL_NGINX" == "1" ]] && apt-get install -y -qq nginx >/dev/null || true
else
  warn "apt-get not found; ensure python3, python3-venv, pip, rsync (and nginx) are installed."
fi

# ------------------------------------------------------------------ #
log "Creating service user '$SERVICE_USER' and directories"
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi
mkdir -p "$APP_DIR" "$DATA_DIR"

# ------------------------------------------------------------------ #
log "Copying application code to $APP_DIR"
rsync -a --delete \
  --exclude='.git/' --exclude='.venv/' --exclude='__pycache__/' \
  --exclude='*.pyc' --exclude='.env' --exclude='backups/' \
  --exclude='*.db' --exclude='*.sqlite' \
  "$SRC_DIR"/ "$APP_DIR"/
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR" "$DATA_DIR"

# ------------------------------------------------------------------ #
log "Creating Python virtualenv and installing dependencies"
if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  sudo -u "$SERVICE_USER" python3 -m venv "$APP_DIR/.venv"
fi
sudo -u "$SERVICE_USER" "$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
sudo -u "$SERVICE_USER" "$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# ------------------------------------------------------------------ #
log "Configuring environment (.env)"
ENV_FILE="$APP_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$APP_DIR/.env.example" "$ENV_FILE"
  SECRET="$("$APP_DIR/.venv/bin/python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  sed -i "s|^APP_SECRET_KEY=.*|APP_SECRET_KEY=${SECRET}|" "$ENV_FILE"
  sed -i "s|^APP_BASE_URL=.*|APP_BASE_URL=https://${DOMAIN}|" "$ENV_FILE"
  sed -i "s|^DATABASE_URL=sqlite.*|DATABASE_URL=sqlite:///${DATA_DIR}/a2ros.db|" "$ENV_FILE"
  chown "$SERVICE_USER:$SERVICE_USER" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  NEW_ENV=1
  warn "A fresh .env was created with a generated APP_SECRET_KEY."
  warn "You MUST still set TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_IDS and ADMIN_PASSWORD in $ENV_FILE."
else
  NEW_ENV=0
  log ".env already exists — left unchanged."
fi

# ------------------------------------------------------------------ #
log "Initialising database + bootstrap admin"
( cd "$APP_DIR" && sudo -u "$SERVICE_USER" "$APP_DIR/.venv/bin/python" manage.py init-db )

# ------------------------------------------------------------------ #
log "Installing systemd services"
for unit in a2ros-web a2ros-bot; do
  sed -e "s|/opt/a2ros|${APP_DIR}|g" \
      -e "s|/var/lib/a2ros|${DATA_DIR}|g" \
      -e "s|^User=.*|User=${SERVICE_USER}|" \
      -e "s|^Group=.*|Group=${SERVICE_USER}|" \
      "$APP_DIR/deploy/systemd/${unit}.service" > "/etc/systemd/system/${unit}.service"
done
systemctl daemon-reload
systemctl enable --now a2ros-web
# Only start the bot if a token is configured, otherwise it would crash-loop.
if grep -qE '^TELEGRAM_BOT_TOKEN=.+' "$ENV_FILE"; then
  systemctl enable --now a2ros-bot
  systemctl restart a2ros-bot
else
  systemctl enable a2ros-bot || true
  warn "Telegram bot not started: set TELEGRAM_BOT_TOKEN in .env, then: systemctl start a2ros-bot"
fi
systemctl restart a2ros-web

# ------------------------------------------------------------------ #
if [[ "$INSTALL_NGINX" == "1" ]] && command -v nginx >/dev/null 2>&1; then
  log "Installing Nginx vhost for $DOMAIN"
  VHOST="/etc/nginx/sites-available/${DOMAIN}"
  sed -e "s|a2.snmk.xyz|${DOMAIN}|g" \
      -e "s|/opt/a2ros/static/|${APP_DIR}/static/|g" \
      "$APP_DIR/deploy/nginx/a2.snmk.xyz.conf" > "$VHOST"
  ln -sf "$VHOST" "/etc/nginx/sites-enabled/${DOMAIN}"
  mkdir -p /var/www/certbot

  if [[ "$ENABLE_LETSENCRYPT" == "1" ]]; then
    [[ -n "$LETSENCRYPT_EMAIL" ]] || die "ENABLE_LETSENCRYPT=1 requires LETSENCRYPT_EMAIL=..."
    command -v certbot >/dev/null 2>&1 || apt-get install -y -qq certbot python3-certbot-nginx >/dev/null
    # Ensure a valid config exists before certbot edits it; if no cert yet, skip the
    # 443 block so `nginx -t` passes, then let certbot add TLS.
    if [[ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
      systemctl reload nginx || systemctl restart nginx || true
      certbot --nginx -d "$DOMAIN" --redirect --non-interactive \
              --agree-tos -m "$LETSENCRYPT_EMAIL" || warn "certbot failed; configure TLS manually (deploy/SSL.md)."
    fi
  fi

  if nginx -t 2>/dev/null; then
    systemctl reload nginx
  else
    warn "nginx -t failed — likely missing TLS certs. See deploy/SSL.md, add certs, then: nginx -t && systemctl reload nginx"
  fi
else
  warn "Skipping Nginx setup (INSTALL_NGINX=0 or nginx not installed)."
fi

# ------------------------------------------------------------------ #
log "Done."
cat <<EOF

A2 Revenue OS is installed at: $APP_DIR
  Web service : systemctl status a2ros-web
  Bot service : systemctl status a2ros-bot
  Local URL   : http://127.0.0.1:8000  (proxied to https://${DOMAIN})

Next steps:
  1. Edit secrets:        nano $APP_DIR/.env
                          (TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_IDS, ADMIN_PASSWORD)
     then:                systemctl restart a2ros-web a2ros-bot
  2. TLS / Cloudflare:    see $APP_DIR/deploy/SSL.md
                          (point the Cloudflare ${DOMAIN} record at this server, SSL mode = Full strict)
  3. (optional) sample:   sudo -u $SERVICE_USER $APP_DIR/.venv/bin/python manage.py seed
  4. Daily backup cron:   0 2 * * *  $APP_DIR/scripts/backup.sh /var/backups/a2ros

EOF
[[ "${NEW_ENV:-0}" == "1" ]] && warn "Remember: the bot stays offline until TELEGRAM_BOT_TOKEN is set."
exit 0
