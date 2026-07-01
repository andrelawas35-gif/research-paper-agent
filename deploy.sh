#!/usr/bin/env bash
# deploy.sh — Deploy the Research Paper Agent + Discord bot to an Oracle VM.
#
# Usage:
#   ./deploy.sh <vm-ip> [ssh-user]
#
# Example:
#   ./deploy.sh 129.153.100.42 ubuntu
#
# This script:
#   1. Copies the project to the VM via rsync
#   2. Installs Python + system dependencies on the VM
#   3. Creates a venv and installs Python dependencies
#   4. Sets up the .env file (prompts for missing keys)
#   5. Installs and starts the systemd service
# ---------------------------------------------------------------------------

set -euo pipefail

# ---- helpers ----
say()   { echo -e "\n\033[1;34m→\033[0m $*"; }
ok()    { echo -e "  \033[1;32m✓\033[0m $*"; }
warn()  { echo -e "  \033[1;33m⚠\033[0m $*"; }
die()   { echo -e "\033[1;31m✗ $*\033[0m" >&2; exit 1; }

# ---- args ----
VM_IP="${1:-}"
SSH_USER="${2:-ubuntu}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"
REMOTE_BASE="/home/${SSH_USER}"

if [ -z "$VM_IP" ]; then
    echo "Usage: ./deploy.sh <vm-ip> [ssh-user]"
    echo "Example: ./deploy.sh 129.153.100.42 ubuntu"
    exit 1
fi

SSH="ssh -o StrictHostKeyChecking=accept-new ${SSH_USER}@${VM_IP}"
SCP="scp -o StrictHostKeyChecking=accept-new"

say "=== Step 1: Check SSH connectivity ==="
if ! ${SSH} "echo ok" &>/dev/null; then
    die "Cannot SSH to ${SSH_USER}@${VM_IP}. Check your Oracle VM's public IP and that your SSH key is authorized."
fi
ok "SSH connection works"

# -----------------------------------------------------------------------
say "=== Step 2: Copy project files to VM ==="
${SSH} "mkdir -p ${REMOTE_BASE}/${PROJECT_NAME}"
# Use rsync if available, fall back to scp.
if command -v rsync &>/dev/null; then
    rsync -avz --delete \
        --exclude '.venv' \
        --exclude '.adk' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.git' \
        --exclude 'logs' \
        --exclude 'backups' \
        --exclude '.env' \
        -e "ssh -o StrictHostKeyChecking=accept-new" \
        "${PROJECT_DIR}/" "${SSH_USER}@${VM_IP}:${REMOTE_BASE}/${PROJECT_NAME}/"
else
    warn "rsync not found; using scp (slower)"
    tar czf /tmp/research_paper_agent_deploy.tar.gz \
        --exclude='.venv' --exclude='.adk' --exclude='__pycache__' \
        --exclude='*.pyc' --exclude='.git' --exclude='logs' --exclude='.env' \
        -C "$(dirname "$PROJECT_DIR")" "$PROJECT_NAME"
    ${SCP} /tmp/research_paper_agent_deploy.tar.gz "${SSH_USER}@${VM_IP}:/tmp/"
    ${SSH} "tar xzf /tmp/research_paper_agent_deploy.tar.gz -C ${REMOTE_BASE} && rm /tmp/research_paper_agent_deploy.tar.gz"
    rm /tmp/research_paper_agent_deploy.tar.gz
fi
ok "Project files copied"

# -----------------------------------------------------------------------
say "=== Step 3: Install system dependencies on VM ==="
${SSH} 'bash -s' << 'REMOTE_SCRIPT'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

# Update package list
sudo apt-get update -qq

# Python 3.10+ (Ubuntu 22.04+ ships it; 20.04 needs deadsnakes PPA)
if ! command -v python3 &>/dev/null || [ "$(python3 -c 'import sys; print(sys.version_info.minor)')" -lt 10 ]; then
    echo "Installing Python 3.11..."
    sudo apt-get install -y -qq software-properties-common
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3.11 python3.11-venv python3.11-dev
    sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
fi

# Tesseract (for OCR fallback on scanned PDFs)
sudo apt-get install -y -qq tesseract-ocr || echo "Tesseract skipped (non-essential)"

echo "System dependencies OK"
REMOTE_SCRIPT
ok "System dependencies installed"

# -----------------------------------------------------------------------
say "=== Step 4: Create venv and install Python packages ==="
${SSH} "cd ${REMOTE_BASE}/${PROJECT_NAME} && python3 -m venv .venv && .venv/bin/pip install --upgrade pip -q"
${SSH} "cd ${REMOTE_BASE}/${PROJECT_NAME} && .venv/bin/pip install -r requirements.txt -q"
ok "Python packages installed"

# -----------------------------------------------------------------------
say "=== Step 5: Set up .env file ==="
# Copy .env.example if .env doesn't exist on the VM.
${SSH} "cd ${REMOTE_BASE}/${PROJECT_NAME} && [ -f .env ] || cp .env.example .env"

# Check if essential env vars are still placeholders.
NEEDS_DEEPSEEK=$(${SSH} "grep -q 'your_deepseek_api_key' ${REMOTE_BASE}/${PROJECT_NAME}/.env && echo 1 || echo 0" || echo "1")
NEEDS_DISCORD=$(${SSH} "grep -q 'DISCORD_BOT_TOKEN' ${REMOTE_BASE}/${PROJECT_NAME}/.env && echo 0 || echo 1" || echo "1")

if [ "$NEEDS_DEEPSEEK" = "1" ] || [ "$NEEDS_DISCORD" = "1" ]; then
    warn ".env needs your API keys."
    echo ""
    echo "  Edit the .env file on your VM:"
    echo "    ssh ${SSH_USER}@${VM_IP}"
    echo "    nano ${REMOTE_BASE}/${PROJECT_NAME}/.env"
    echo ""
    echo "  You need at minimum:"
    echo "    DEEPSEEK_API_KEY=sk-..."
    echo "    DISCORD_BOT_TOKEN=MTE..."
    echo ""
    echo "  See ORACLE_VM_SETUP.md for how to get these tokens."
    echo ""
fi

# Append Discord-specific env vars to .env if missing.
${SSH} "grep -q 'DISCORD_BOT_TOKEN' ${REMOTE_BASE}/${PROJECT_NAME}/.env || printf '\n# Discord bot\nDISCORD_BOT_TOKEN=your_discord_bot_token\n# DISCORD_ALLOWED_CHANNELS=123456789,987654321\n# DISCORD_MSG_LIMIT_PER_USER=50\n' >> ${REMOTE_BASE}/${PROJECT_NAME}/.env"
ok ".env file prepared"

# -----------------------------------------------------------------------
say "=== Step 6: Create log directory ==="
${SSH} "mkdir -p ${REMOTE_BASE}/${PROJECT_NAME}/logs"
ok "Log directory created"

# -----------------------------------------------------------------------
say "=== Step 7: Install systemd service ==="
${SSH} "sudo cp ${REMOTE_BASE}/${PROJECT_NAME}/research-agent.service /etc/systemd/system/"
${SSH} "sudo systemctl daemon-reload"
${SSH} "sudo systemctl enable research-agent"
ok "systemd service installed and enabled"

# -----------------------------------------------------------------------
say "=== Step 8: Set up daily backup cron job ==="
${SSH} "chmod +x ${REMOTE_BASE}/${PROJECT_NAME}/backup.sh"
# Add a cron job that runs backup.sh daily at 3 AM UTC (quiet if absent).
${SSH} "(crontab -l 2>/dev/null | grep -v 'backup.sh' || true; echo '0 3 * * * ${REMOTE_BASE}/${PROJECT_NAME}/backup.sh >> ${REMOTE_BASE}/${PROJECT_NAME}/logs/backup.log 2>&1') | crontab -"
ok "Daily backup cron installed (3 AM UTC, keeps 7 days)"

# -----------------------------------------------------------------------
say "=== Step 9: Start the service ==="
${SSH} "sudo systemctl restart research-agent"
sleep 3
STATUS=$(${SSH} "sudo systemctl is-active research-agent" || echo "inactive")
if [ "$STATUS" = "active" ]; then
    ok "Service is running!"
else
    warn "Service status: ${STATUS}. Check logs with:"
    echo "    ssh ${SSH_USER}@${VM_IP}"
    echo "    sudo journalctl -u research-agent -n 50 --no-pager"
fi

# -----------------------------------------------------------------------
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Deployment complete!"
echo ""
echo "  Check service status:"
echo "    ssh ${SSH_USER}@${VM_IP} 'sudo systemctl status research-agent'"
echo ""
echo "  View logs:"
echo "    ssh ${SSH_USER}@${VM_IP} 'tail -f ${REMOTE_BASE}/${PROJECT_NAME}/logs/bot.log'"
echo ""
echo "  Daily backup (3 AM UTC, 7-day rotation):"
echo "    ssh ${SSH_USER}@${VM_IP} 'ls -la ${REMOTE_BASE}/${PROJECT_NAME}/backups/'"
echo "    ssh ${SSH_USER}@${VM_IP} 'tail ${REMOTE_BASE}/${PROJECT_NAME}/logs/backup.log'"
echo ""
echo "  Restart after config changes:"
echo "    ssh ${SSH_USER}@${VM_IP} 'sudo systemctl restart research-agent'"
echo ""
echo "  DON'T FORGET to edit .env with your real API keys:"
echo "    ssh ${SSH_USER}@${VM_IP}"
echo "    nano ${REMOTE_BASE}/${PROJECT_NAME}/.env"
echo "    sudo systemctl restart research-agent"
echo "═══════════════════════════════════════════════════════════════"
