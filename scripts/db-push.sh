#!/usr/bin/env bash
# Apply supabase/migrations/ to the database in apps/api/.env (DATABASE_URL).
#   bash scripts/db-push.sh            # asks for confirmation
#   bash scripts/db-push.sh --dry-run  # lists what would be applied, changes nothing
# Extra arguments go straight to `supabase db push`.
set -euo pipefail
cd "$(dirname "$0")/.."

# Load apps/api/.env as plain variables. Quoting is handled here, so nobody has to
# type --db-url "$DATABASE_URL" by hand (a missing space there breaks the flag).
set -a
# shellcheck disable=SC1091
. apps/api/.env
set +a

if [[ -z "${DATABASE_URL:-}" || "$DATABASE_URL" == *"[YOUR-PASSWORD]"* ]]; then
  echo "DATABASE_URL in apps/api/.env is missing or still has the [YOUR-PASSWORD] placeholder." >&2
  exit 1
fi

exec npx --yes supabase@2 db push --db-url "$DATABASE_URL" "$@"
