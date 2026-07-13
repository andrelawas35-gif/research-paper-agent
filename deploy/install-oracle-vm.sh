#!/usr/bin/env bash
""":"
Install one atomic PKM release on Ubuntu 24.04 ARM64 or x86_64.

Node is build-only; the running PWA is static. Node 24 LTS supersedes the
20.19 minimum because Node 20 is EOL. Override NODE_MAJOR only for a tested,
supported LTS line.
":"""

set -euo pipefail

SOURCE_DIR="${1:-}"
APP_ROOT="/opt/pkm"
RELEASE_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RELEASE_DIR="${APP_ROOT}/releases/${RELEASE_ID}"
NODE_MAJOR="${NODE_MAJOR:-24}"

if [[ "$(id -u)" -ne 0 || -z "$SOURCE_DIR" || ! -f "$SOURCE_DIR/frontend/package-lock.json" ]]; then
  echo "Usage: sudo bash deploy/install-oracle-vm.sh <staged-source-directory>" >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl gnupg openssl python3 python3-venv rsync caddy restic

python3 - <<'PY'
import sys
if sys.version_info < (3, 12):
    raise SystemExit("Python 3.12+ is required; use Ubuntu 24.04 LTS")
PY

install_node() {
  install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | gpg --dearmor --yes -o /etc/apt/keyrings/nodesource.gpg
  echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list
  apt-get update
  apt-get install -y nodejs
}

CURRENT_NODE_MAJOR="$(node -p 'process.versions.node.split(`.`)[0]' 2>/dev/null || true)"
if [[ "$CURRENT_NODE_MAJOR" != "$NODE_MAJOR" ]]; then
  install_node
fi

node - <<'JS'
const [major, minor] = process.versions.node.split('.').map(Number);
if (major < 20 || (major === 20 && minor < 19)) {
  console.error(`Node 20.19+ is required; found ${process.versions.node}`);
  process.exit(1);
}
JS

if ! id pkm >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/pkm --create-home --shell /usr/sbin/nologin pkm
fi

install -d -o pkm -g pkm -m 0700 /var/lib/pkm /var/lib/pkm/audit
install -d -o root -g pkm -m 0750 /etc/pkm /etc/pkm/keys
install -d -o pkm -g pkm -m 0755 "$APP_ROOT/releases"
install -d -o pkm -g pkm -m 0755 "$RELEASE_DIR"

rsync -a --delete \
  --exclude '.env' --exclude '.git' --exclude '.venv' --exclude 'venv' \
  --exclude 'frontend/node_modules' --exclude 'frontend/dist' \
  --exclude 'data' --exclude 'logs' --exclude 'backups' \
  "$SOURCE_DIR/" "$RELEASE_DIR/"
chown -R pkm:pkm "$RELEASE_DIR"

runuser -u pkm -- python3 -m venv "$RELEASE_DIR/.venv"
runuser -u pkm -- "$RELEASE_DIR/.venv/bin/python" -m pip install --upgrade pip
runuser -u pkm -- "$RELEASE_DIR/.venv/bin/pip" install -r "$RELEASE_DIR/requirements.txt"
runuser -u pkm -- bash -lc "cd '$RELEASE_DIR/frontend' && npm ci && npm run build && rm -rf node_modules"

OWNER_KEY=""
if [[ ! -s /etc/pkm/keys/regulation.key ]]; then
  echo "Missing /etc/pkm/keys/regulation.key. Provision a 32-byte hex key from an off-VM password manager before deploying." >&2
  exit 3
fi
chown root:pkm /etc/pkm/keys/regulation.key
chmod 0640 /etc/pkm/keys/regulation.key

if [[ ! -f /etc/pkm/pkm.env ]]; then
  OWNER_KEY="$(openssl rand -hex 32)"
  OWNER_HASH="$(printf '%s' "$OWNER_KEY" | sha256sum | cut -d' ' -f1)"
  cat > /etc/pkm/pkm.env <<EOF
PKM_OWNER_ID=owner
PKM_API_KEY_HASH=${OWNER_HASH}
PKM_DATA_DIR=/var/lib/pkm
AUDIT_LOG_DIR=/var/lib/pkm/audit
REGULATION_KEY_PATH=/etc/pkm/keys/regulation.key
OPENAI_API_KEY=
OPENAI_GPT5_MINI_MODEL=gpt-5-mini
OPENAI_GPT5_MODEL=gpt-5
CORS_ORIGINS=
EOF
  chown root:pkm /etc/pkm/pkm.env
  chmod 0640 /etc/pkm/pkm.env
fi

ln -sfn "$RELEASE_DIR" "$APP_ROOT/current"
chown -h pkm:pkm "$APP_ROOT/current"

install -o root -g root -m 0644 "$RELEASE_DIR/deploy/pkm-api.service" /etc/systemd/system/pkm-api.service
install -o root -g root -m 0644 "$RELEASE_DIR/deploy/pkm-backup.service" /etc/systemd/system/pkm-backup.service
install -o root -g root -m 0644 "$RELEASE_DIR/deploy/pkm-backup.timer" /etc/systemd/system/pkm-backup.timer
install -o root -g root -m 0644 "$RELEASE_DIR/deploy/Caddyfile" /etc/caddy/Caddyfile

systemctl daemon-reload
systemctl enable caddy pkm-api.service
systemctl restart caddy pkm-api.service
systemctl enable pkm-backup.timer
if [[ -f /etc/pkm/backup.env ]]; then
  systemctl start pkm-backup.timer
fi

for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:8080/health/ready | grep -q '"status":"ready"'; then
    break
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:8080/health/ready | grep -q '"status":"ready"' || {
  journalctl -u pkm-api.service -n 80 --no-pager
  exit 1
}

find "$APP_ROOT/releases" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
  | sort -nr | tail -n +4 | cut -d' ' -f2- | xargs -r rm -rf

echo "PKM release ${RELEASE_ID} is healthy."
echo "Node build runtime: $(node --version)"
if [[ -n "$OWNER_KEY" ]]; then
  echo
  echo "SAVE THIS OWNER ACCESS KEY NOW; it is not stored in plaintext on the VM:"
  echo "$OWNER_KEY"
fi
if ! command -v tailscale >/dev/null 2>&1; then
  echo
  echo "Tailscale is not installed. Install it from https://tailscale.com/download/linux"
fi
if [[ ! -f /etc/pkm/backup.env ]]; then
  echo
  echo "Backups are not active yet. Configure /etc/pkm/backup.env, initialize the restic repository, then start pkm-backup.timer."
fi
