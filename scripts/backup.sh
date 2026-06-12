#!/usr/bin/env bash
# Nightly SQLite backup with local pruning + optional off-box sync (rclone).
# Cron (root): 17 3 * * * /opt/switchboard/app/scripts/backup.sh >> /var/log/switchboard-backup.log 2>&1
set -euo pipefail
DB="${DB:-/opt/switchboard/data/switchboard.db}"
DEST="${DEST:-/opt/switchboard/data/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
# Optional: an rclone remote path, e.g. "b2:my-bucket/switchboard"
BACKUP_REMOTE="${BACKUP_REMOTE:-}"

mkdir -p "$DEST"
STAMP="$(date +%F)"
OUT="$DEST/switchboard-$STAMP.db"

if [ ! -f "$DB" ]; then echo "no DB at $DB yet — skipping"; exit 0; fi
# .backup is safe against a live WAL-mode database
sqlite3 "$DB" ".backup '$OUT'"
gzip -f "$OUT"
find "$DEST" -name 'switchboard-*.db.gz' -mtime +"$KEEP_DAYS" -delete

if [ -n "$BACKUP_REMOTE" ]; then
  if command -v rclone >/dev/null; then
    rclone copy "$DEST" "$BACKUP_REMOTE" --include 'switchboard-*.db.gz'
  else
    echo "BACKUP_REMOTE set but rclone not installed (apt-get install rclone)"; exit 1
  fi
fi
echo "backup OK: $OUT.gz"
