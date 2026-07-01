#!/usr/bin/env bash
# backup.sh — Daily backup of agent data (knowledge base + user model).
# Runs via cron on the Oracle VM.  Keeps 7 daily snapshots.
# ------------------------------------------------------------------

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"
TIMESTAMP=$(date +%Y-%m-%d)
BACKUP_FILE="${BACKUP_DIR}/agent-data-${TIMESTAMP}.tar.gz"
MAX_BACKUPS=7

mkdir -p "${BACKUP_DIR}"

# Create the backup tarball.
tar czf "${BACKUP_FILE}" \
    -C "${PROJECT_DIR}" \
    knowledge_base/ \
    user_model/

echo "[$(date -Iseconds)] Backup created: ${BACKUP_FILE} (${du -sh "${BACKUP_FILE}" | cut -f1})"

# Prune old backups — keep only the most recent MAX_BACKUPS.
cd "${BACKUP_DIR}"
ls -1t agent-data-*.tar.gz 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | while read -r old; do
    rm -f "${old}"
    echo "[$(date -Iseconds)] Pruned old backup: ${old}"
done
