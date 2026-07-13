#!/usr/bin/env bash
# Upload and atomically install the production PWA on an Oracle Ubuntu VM.

set -euo pipefail

VM_HOST="${1:-}"
SSH_USER="${2:-ubuntu}"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
REMOTE_STAGE="/tmp/pkm-release-${USER:-deploy}"

if [[ -z "$VM_HOST" ]]; then
  echo "Usage: ./deploy.sh <vm-ip-or-ssh-host> [ssh-user]" >&2
  exit 2
fi

SSH=(ssh -o StrictHostKeyChecking=accept-new "${SSH_USER}@${VM_HOST}")

"${SSH[@]}" "rm -rf '$REMOTE_STAGE' && mkdir -p '$REMOTE_STAGE'"
rsync -az --delete \
  --exclude '.git' \
  --exclude '.env' \
  --exclude '.venv' \
  --exclude 'venv' \
  --exclude 'frontend/node_modules' \
  --exclude 'frontend/dist' \
  --exclude '.pytest_cache' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude 'data' \
  --exclude 'logs' \
  --exclude 'backups' \
  "$ROOT_DIR/" "${SSH_USER}@${VM_HOST}:${REMOTE_STAGE}/"

"${SSH[@]}" "sudo bash '$REMOTE_STAGE/deploy/install-oracle-vm.sh' '$REMOTE_STAGE'"
"${SSH[@]}" "rm -rf '$REMOTE_STAGE'"

echo
echo "Deployment completed. If Tailscale Serve is not configured yet, run:"
echo "  ssh ${SSH_USER}@${VM_HOST}"
echo "  sudo tailscale up --ssh"
echo "  sudo tailscale serve --bg --yes --https=443 http://127.0.0.1:8080"
echo "  tailscale serve status"
