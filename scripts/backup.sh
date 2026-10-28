#!/usr/bin/env bash
# Database backup (D45). Run nightly from cron on the VM; credentials never leave the VM.
#
#   ./scripts/backup.sh                      # DATABASE_URL from apps/api/.env
#   BACKUP_DIR=/mnt/backups KEEP_DAYS=30 ./scripts/backup.sh
#
# Writes two files: <stamp>-app.sql.gz (all app data, the `public` schema) and <stamp>-users.sql.gz
# (the user accounts the data belongs to: without them a restored project would have orphaned rows).
# pg_dump must be the same major version as Supabase's server (17): a local client of 17 or newer is
# used when there is one, otherwise the Postgres 17 Docker image.
set -euo pipefail
cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-$HOME/db-backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
ENV_FILE="${ENV_FILE:-apps/api/.env}"

if [ -z "${DATABASE_URL:-}" ]; then
  DATABASE_URL="$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
  DATABASE_URL="${DATABASE_URL%\"}"; DATABASE_URL="${DATABASE_URL#\"}"  # tolerate "quoted" values
fi
[ -n "$DATABASE_URL" ] || { echo "DATABASE_URL not found in $ENV_FILE" >&2; exit 1; }

# Run a Postgres tool (pg_dump, psql) at version 17+, locally or through Docker.
pg() {
  local tool="$1"; shift
  if command -v "$tool" >/dev/null 2>&1 && [ "$("$tool" --version | grep -oE '[0-9]+' | head -1)" -ge 17 ]; then
    "$tool" "$@"
  else
    docker run --rm -i --network host postgres:17-alpine "$tool" "$@"
  fi
}

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"
umask 077  # backups hold resumes and transcripts: owner-only

dump() { # $1 = output name, $2 = smallest believable size in bytes, rest = pg_dump arguments
  local name="$1" min_bytes="$2"; shift 2
  local tmp="$BACKUP_DIR/.$stamp-$name.tmp" final="$BACKUP_DIR/$stamp-$name.sql.gz"
  pg pg_dump "$DATABASE_URL" --no-owner --no-privileges "$@" \
    | gzip -9 > "$tmp"
  # A failed pg_dump still leaves a tiny valid gzip: check it is real before keeping it.
  gzip -t "$tmp"
  [ "$(stat -c %s "$tmp")" -gt "$min_bytes" ] || { echo "$name backup is suspiciously small" >&2; rm -f "$tmp"; exit 1; }
  mv "$tmp" "$final"  # appears atomically: a half-written file never looks like a backup
  echo "wrote $final ($(du -h "$final" | cut -f1))"
}

dump app 500 --schema=public
dump users 100 --data-only --table=auth.users

# Keep the last KEEP_DAYS days.
find "$BACKUP_DIR" -maxdepth 1 -name '*.sql.gz' -mtime "+$KEEP_DAYS" -delete
