#!/usr/bin/env bash
# Restore the newest encrypted backup into a temporary directory and prove it
# with an independently staged source artifact and fresh virtual environment.
# This never imports application code or dependencies from the live release.

set -euo pipefail

ENV_FILE="${1:-/etc/pkm/backup.env}"
RECOVERY_SOURCE_DIR="${RECOVERY_SOURCE_DIR:-}"
RECOVERY_ENV_FILE="${RECOVERY_ENV_FILE:-}"
RECOVERY_EXPECTED_MIN_SESSIONS="${RECOVERY_EXPECTED_MIN_SESSIONS:-}"
RECOVERY_EXPECTED_MIN_RULES="${RECOVERY_EXPECTED_MIN_RULES:-}"

if [[ ! -r "$ENV_FILE" ]]; then
  echo "Backup environment is not readable: $ENV_FILE" >&2
  exit 2
fi
if [[ -z "$RECOVERY_SOURCE_DIR" || ! -f "$RECOVERY_SOURCE_DIR/requirements.txt" ]]; then
  echo "Set RECOVERY_SOURCE_DIR to an independently staged release source." >&2
  exit 2
fi
if [[ -z "$RECOVERY_ENV_FILE" || ! -r "$RECOVERY_ENV_FILE" ]]; then
  echo "Set RECOVERY_ENV_FILE to separately held production configuration." >&2
  exit 2
fi
if [[ ! "$RECOVERY_EXPECTED_MIN_SESSIONS" =~ ^[0-9]+$ || ! "$RECOVERY_EXPECTED_MIN_RULES" =~ ^[0-9]+$ ]]; then
  echo "Set numeric RECOVERY_EXPECTED_MIN_SESSIONS and RECOVERY_EXPECTED_MIN_RULES from the backup canary." >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

RESTORE_DIR="$(mktemp -d)"
trap 'rm -rf "$RESTORE_DIR"' EXIT

restic restore latest --tag pkm-production --target "$RESTORE_DIR"
test -d "$RESTORE_DIR/var/lib/pkm"

set -a
# shellcheck disable=SC1091
source "$RECOVERY_ENV_FILE"
set +a
export PKM_DATA_DIR="$RESTORE_DIR/var/lib/pkm"
export AUDIT_LOG_DIR="$RESTORE_DIR/var/lib/pkm/audit"
export RECOVERY_EXPECTED_MIN_SESSIONS RECOVERY_EXPECTED_MIN_RULES
unset REGULATION_KEY REGULATION_KEY_PATH REGULATION_KEY_DIR

python3 -m venv "$RESTORE_DIR/recovery-venv"
"$RESTORE_DIR/recovery-venv/bin/pip" install --quiet -r "$RECOVERY_SOURCE_DIR/requirements.txt"
cd "$RECOVERY_SOURCE_DIR"
"$RESTORE_DIR/recovery-venv/bin/python" - <<'PY'
import os

from agent_runtime.record_keys import create_record_key_provider_from_env
from agent_runtime.regulation_persistence import EncryptedRegulationPersistence
from agent_runtime.stores import StoreRegistry

provider = create_record_key_provider_from_env()
provider.validate_configuration()
registry = StoreRegistry()
persistence = EncryptedRegulationPersistence(
    registry.regulation,
    None,
    owner_id=os.getenv("PKM_OWNER_ID", "owner"),
    record_keys=provider,
)
sessions, rules = persistence.load()
minimum_sessions = int(os.environ["RECOVERY_EXPECTED_MIN_SESSIONS"])
minimum_rules = int(os.environ["RECOVERY_EXPECTED_MIN_RULES"])
assert len(sessions) >= minimum_sessions, (len(sessions), minimum_sessions)
assert len(rules) >= minimum_rules, (len(rules), minimum_rules)
print(
    "Restore verification passed from a clean environment: "
    f"{len(sessions)} sessions and {len(rules)} rules decrypted."
)
PY
