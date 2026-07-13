#!/usr/bin/env bash
# Encrypted off-VM backup. Configuration comes from /etc/pkm/backup.env.

set -euo pipefail

: "${RESTIC_REPOSITORY:?Set RESTIC_REPOSITORY in /etc/pkm/backup.env}"
: "${RESTIC_PASSWORD_FILE:?Set RESTIC_PASSWORD_FILE in /etc/pkm/backup.env}"

restic backup \
  --tag pkm-production \
  --exclude "$RESTIC_PASSWORD_FILE" \
  --exclude /etc/pkm/backup.env \
  --exclude /etc/pkm/keys \
  /var/lib/pkm /etc/pkm

restic forget \
  --tag pkm-production \
  --keep-daily 7 \
  --keep-weekly 4 \
  --keep-monthly 6 \
  --prune

restic check
