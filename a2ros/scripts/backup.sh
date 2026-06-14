#!/usr/bin/env bash
# ============================================================
# A2 ROS database backup script.
# Supports SQLite (default) and PostgreSQL via DATABASE_URL.
# Usage:  ./scripts/backup.sh [backup_dir]
# Cron example (daily 02:00):
#   0 2 * * *  /opt/a2ros/scripts/backup.sh /var/backups/a2ros >> /var/log/a2ros-backup.log 2>&1
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${1:-${PROJECT_DIR}/backups}"
STAMP="$(date +%Y%m%d_%H%M%S)"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Load DATABASE_URL from .env if not already in the environment.
if [[ -z "${DATABASE_URL:-}" && -f "${PROJECT_DIR}/.env" ]]; then
  DATABASE_URL="$(grep -E '^DATABASE_URL=' "${PROJECT_DIR}/.env" | head -1 | cut -d= -f2-)"
fi
DATABASE_URL="${DATABASE_URL:-sqlite:///${PROJECT_DIR}/a2ros.db}"

mkdir -p "$BACKUP_DIR"

if [[ "$DATABASE_URL" == sqlite* ]]; then
  # SQLAlchemy form: sqlite:///relative.db  or  sqlite:////absolute/path.db
  # Stripping "sqlite://" then one separator slash yields the real path for both.
  DB_PATH="${DATABASE_URL#sqlite://}"
  DB_PATH="${DB_PATH#/}"
  OUT="${BACKUP_DIR}/a2ros_${STAMP}.sqlite"
  echo "Backing up SQLite ${DB_PATH} -> ${OUT}"
  # Use the online backup API (via python3 stdlib) for a consistent copy
  # without requiring the sqlite3 CLI.
  python3 - "$DB_PATH" "$OUT" <<'PYEOF'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
with sqlite3.connect(src) as s, sqlite3.connect(dst) as d:
    s.backup(d)
PYEOF
  gzip -f "$OUT"
  echo "Done: ${OUT}.gz"
elif [[ "$DATABASE_URL" == postgres* ]]; then
  OUT="${BACKUP_DIR}/a2ros_${STAMP}.sql.gz"
  echo "Backing up PostgreSQL -> ${OUT}"
  pg_dump "$DATABASE_URL" | gzip > "$OUT"
  echo "Done: ${OUT}"
else
  echo "Unsupported DATABASE_URL: ${DATABASE_URL}" >&2
  exit 1
fi

# Prune old backups.
find "$BACKUP_DIR" -name 'a2ros_*' -type f -mtime "+${RETENTION_DAYS}" -delete
echo "Pruned backups older than ${RETENTION_DAYS} days."
