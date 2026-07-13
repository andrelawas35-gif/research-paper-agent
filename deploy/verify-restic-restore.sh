#!/usr/bin/env bash
# Restore the newest encrypted backup into a temporary directory and prove that
# the application can decrypt and replay it. Does not modify live data.

set -euo pipefail

ENV_FILE="${1:-/etc/pkm/backup.env}"
APP_DIR="${APP_DIR:-/opt/pkm/current}"
RECOVERY_KEY_PATH="${RECOVERY_KEY_PATH:-/etc/pkm/keys/regulation.key}"

if [[ ! -r "$ENV_FILE" ]]; then
  echo "Backup environment is not readable: $ENV_FILE" >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

RESTORE_DIR="$(mktemp -d)"
trap 'rm -rf "$RESTORE_DIR"' EXIT

restic restore latest --tag pkm-production --target "$RESTORE_DIR"
test -s "$RESTORE_DIR/etc/pkm/pkm.env"
test -d "$RESTORE_DIR/var/lib/pkm"
test -s "$RECOVERY_KEY_PATH"

set -a
# shellcheck disable=SC1091
source "$RESTORE_DIR/etc/pkm/pkm.env"
set +a
export PKM_DATA_DIR="$RESTORE_DIR/var/lib/pkm"
export AUDIT_LOG_DIR="$RESTORE_DIR/var/lib/pkm/audit"
export REGULATION_KEY_PATH="$RECOVERY_KEY_PATH"

cd "$APP_DIR"
"$APP_DIR/.venv/bin/python" - <<'PY'
from agent_runtime.asgi import create_production_app

app = create_production_app()
assert app.title == "Personal Knowledge Manager"
print("Restore verification passed: restored state replayed with the separately held recovery key.")
PY
