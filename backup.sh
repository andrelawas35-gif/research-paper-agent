#!/usr/bin/env bash
# Encrypted off-VM backup. Configuration comes from /etc/pkm/backup.env.

set -euo pipefail

: "${RESTIC_REPOSITORY:?Set RESTIC_REPOSITORY in /etc/pkm/backup.env}"
: "${RESTIC_PASSWORD_FILE:?Set RESTIC_PASSWORD_FILE in /etc/pkm/backup.env}"

# A short planned API stop gives Restic a consistent SQLite/WAL filesystem
# image on this explicitly non-HA single-host deployment.
API_WAS_ACTIVE=false
if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet pkm-api.service; then
  API_WAS_ACTIVE=true
  systemctl stop pkm-api.service
fi
restart_api() {
  if [[ "$API_WAS_ACTIVE" == "true" ]]; then
    systemctl start pkm-api.service
  fi
}
trap restart_api EXIT

restic backup \
  --tag pkm-production \
  --exclude "$RESTIC_PASSWORD_FILE" \
  --exclude /etc/pkm/backup.env \
  --exclude /etc/pkm/pkm.env \
  --exclude /etc/pkm/keys \
  /var/lib/pkm /etc/pkm

restic forget \
  --tag pkm-production \
  --keep-daily 7 \
  --keep-weekly 4 \
  --keep-monthly 6 \
  --prune

restic check

restart_api
API_WAS_ACTIVE=false
trap - EXIT
