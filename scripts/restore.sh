#!/usr/bin/env bash
# Restore a backup made by scripts/backup.sh into an EMPTY database (D45).
#
#   ./scripts/restore.sh <target-database-url> <stamp>-users.sql.gz <stamp>-app.sql.gz
#
# Users first (the app tables point at them), then the app data. Refuses to touch a database that
# already has app tables, so a typo can never overwrite live data. Test it on a scratch database
# before you need it: docs/deploy.md ("Backups").
set -euo pipefail

[ "$#" -eq 3 ] || { sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
target="$1" users="$2" app="$3"
psql_run() { docker run --rm -i --network host postgres:17-alpine psql "$target" -v ON_ERROR_STOP=1 -q "$@"; }

existing="$(psql_run -At -c "select count(*) from information_schema.tables where table_schema = 'public'")"
[ "$existing" = "0" ] || { echo "Refusing: the target already has $existing tables in public. Use an empty database." >&2; exit 1; }

gunzip -c "$users" | psql_run
# `public` always exists already; pg_dump's CREATE SCHEMA line would fail the restore.
gunzip -c "$app" | sed '/^CREATE SCHEMA public;$/d' | psql_run
echo "restored. Tables in public: $(psql_run -At -c "select count(*) from information_schema.tables where table_schema = 'public'")"
