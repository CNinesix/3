#!/usr/bin/env bash
# ============================================================
# A2 ROS database restore script.
# Usage:  ./scripts/restore.sh <backup_file>
#   SQLite backups: a2ros_*.sqlite.gz
#   Postgres backups: a2ros_*.sql.gz
# WARNING: this overwrites the current database. Stop the services first:
#   sudo systemctl stop a2ros-web a2ros-bot
# ============================================================
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup_file>" >&2
  exit 1
fi

BACKUP_FILE="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" && -f "${PROJECT_DIR}/.env" ]]; then
  DATABASE_URL="$(grep -E '^DATABASE_URL=' "${PROJECT_DIR}/.env" | head -1 | cut -d= -f2-)"
fi
DATABASE_URL="${DATABASE_URL:-sqlite:///${PROJECT_DIR}/a2ros.db}"

read -r -p "This will OVERWRITE the database for ${DATABASE_URL}. Continue? [y/N] " ans
[[ "$ans" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

if [[ "$DATABASE_URL" == sqlite* ]]; then
  DB_PATH="${DATABASE_URL#sqlite://}"
  DB_PATH="${DB_PATH#/}"
  TMP="$(mktemp)"
  if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" > "$TMP"
  else
    cp "$BACKUP_FILE" "$TMP"
  fi
  # Back up the current DB just in case.
  [[ -f "$DB_PATH" ]] && cp "$DB_PATH" "${DB_PATH}.pre-restore.$(date +%s)"
  mv "$TMP" "$DB_PATH"
  echo "Restored SQLite database to ${DB_PATH}"
elif [[ "$DATABASE_URL" == postgres* ]]; then
  if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" | psql "$DATABASE_URL"
  else
    psql "$DATABASE_URL" < "$BACKUP_FILE"
  fi
  echo "Restored PostgreSQL database."
else
  echo "Unsupported DATABASE_URL: ${DATABASE_URL}" >&2
  exit 1
fi

echo "Restore complete. Restart services:  sudo systemctl start a2ros-web a2ros-bot"
