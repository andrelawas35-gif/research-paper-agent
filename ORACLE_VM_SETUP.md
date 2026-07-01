# Oracle VM Setup Guide — Research Paper Agent + Discord Bot

Deploy your Research Paper Agent to an always-free Oracle Cloud VM and chat with it from mobile Discord.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Create a Discord Bot](#2-create-a-discord-bot)
3. [Create an Oracle VM](#3-create-an-oracle-vm)
4. [SSH into Your VM](#4-ssh-into-your-vm)
5. [Deploy the Agent](#5-deploy-the-agent)
6. [Invite the Bot to Your Discord Server](#6-invite-the-bot-to-your-discord-server)
7. [Test & Troubleshoot](#7-test--troubleshoot)
8. [Daily Usage](#8-daily-usage)

---

## 1. Prerequisites

- An **Oracle Cloud account** (free tier — [sign up here](https://signup.cloud.oracle.com/))
- A **DeepSeek API key** ([get one here](https://platform.deepseek.com/api_keys))
- A **Discord account** with the mobile app installed
- **Terminal** on your Mac (built-in)

---

## 2. Create a Discord Bot

### 2.1 Create the Application

1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** → name it (e.g. "Research Agent")
3. Click **Create**

### 2.2 Configure the Bot

1. In the left sidebar, click **Bot**
2. Click **Reset Token** → copy the token (you won't see it again)
3. Under **Privileged Gateway Intents**, enable:
   - ✅ **Message Content Intent**
4. Click **Save Changes**

### 2.3 Get Your Discord User ID

1. In Discord (desktop or mobile), go to **Settings → Advanced**
2. Enable **Developer Mode**
3. Right-click your username in any chat → **Copy User ID**
4. Save this — you'll need it for `.env`

### 2.4 Invite the Bot (do this AFTER deployment)

See [Section 6](#6-invite-the-bot-to-your-discord-server). You need the VM's public IP first to configure OAuth2 redirect.

---

## 3. Create an Oracle VM

### 3.1 Launch the Instance

1. Log in to [Oracle Cloud Console](https://cloud.oracle.com/)
2. Navigate to **Compute → Instances**
3. Click **Create instance**
4. Configure:
   | Setting | Value |
   |---|---|
   | Name | `research-agent` |
   | Placement | Leave default |
   | Image | **Ubuntu 22.04** or **Ubuntu 24.04** |
   | Shape | **VM.Standard.A1.Flex** (ARM, 4 OCPU, 24 GB) — always free |
   | Boot volume | 50–100 GB (free up to 200 GB) |

5. Under **Add SSH keys**, choose **Generate a key pair for me**
   - This downloads `ssh-key-YYYY-MM-DD.zip` — **save it**
6. Click **Create**

### 3.2 Open Firewall Ports

Once the instance is running:

1. Click on your instance name
2. Click **Attached VNICs** → click the VNIC name
3. Click **Security Lists** → click the default security list
4. Click **Add Ingress Rules**:
   | Source Type | Source CIDR | IP Protocol | Dest Port | Description |
   |---|---|---|---|---|
   | CIDR | `0.0.0.0/0` | TCP | 22 | SSH |
   | CIDR | `0.0.0.0/0` | TCP | 8000 | ADK Web UI (optional) |

5. Click **Add Ingress Rules**

### 3.3 Find Your Public IP

On the instance details page, copy the **Public IP address**.

---

## 4. SSH into Your VM

### 4.1 Extract the SSH Key

Unzip the key file you downloaded:

```bash
cd ~/Downloads
unzip ssh-key-*.zip
chmod 600 ssh-key-*.key
```

### 4.2 Connect

```bash
ssh -i ~/Downloads/ssh-key-YYYY-MM-DD.key ubuntu@<YOUR_VM_PUBLIC_IP>
```

Replace `<YOUR_VM_PUBLIC_IP>` with the IP from step 3.3.

### 4.3 (Optional) Set Up SSH Config for Convenience

On your Mac:

```bash
mkdir -p ~/.ssh
cp ~/Downloads/ssh-key-*.key ~/.ssh/oracle_vm.key
chmod 600 ~/.ssh/oracle_vm.key
```

Add to `~/.ssh/config`:

```
Host oracle
    HostName <YOUR_VM_PUBLIC_IP>
    User ubuntu
    IdentityFile ~/.ssh/oracle_vm.key
```

Then connect with just: `ssh oracle`

---

## 5. Deploy the Agent

From your Mac, run the deployment script:

```bash
cd /Users/andrelawas/Documents/Codex/2026-07-01/add/research_paper_agent
chmod +x deploy.sh
./deploy.sh <YOUR_VM_PUBLIC_IP>
```

This will:
- Copy all project files to the VM
- Install Python 3.11+ and system dependencies
- Create a virtual environment and install packages
- Prepare the `.env` file
- Install and start the systemd service

### 5.1 Configure Your API Keys

After deployment, edit the `.env` file on the VM:

```bash
ssh oracle
nano ~/research_paper_agent/.env
```

Fill in your actual keys:

```ini
DEEPSEEK_API_KEY=sk-your-actual-deepseek-key
DISCORD_BOT_TOKEN=MTE-your-actual-discord-bot-token
DISCORD_USER_ID=123456789012345678
```

Save (`Ctrl+O`, `Enter`, `Ctrl+X`) then restart:

```bash
sudo systemctl restart research-agent
```

---

## 6. Invite the Bot to Your Discord Server

1. Go back to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your bot application
3. In the left sidebar, click **OAuth2**
4. Under **OAuth2 URL Generator**, check:
   - ✅ **bot**
5. Under **Bot Permissions**, check:
   - ✅ **Send Messages**
   - ✅ **Read Messages/View Channels**
   - ✅ **Read Message History**
   - ✅ **Use Slash Commands**
6. Copy the generated URL (at the bottom of the page)
7. Open that URL in your browser → select your Discord server → **Authorize**

The bot will appear offline until the VM service starts successfully.

### 6.1 Check the Bot is Online

On the VM:

```bash
sudo systemctl status research-agent
```

You should see `active (running)`. If not:

```bash
sudo journalctl -u research-agent -n 30 --no-pager
```

---

## 7. Test & Troubleshoot

### 7.1 Quick Smoke Test

In any Discord channel the bot can see, @mention it:

```
@Research Agent help
```

Or DM the bot directly. It should respond with the agent's greeting.

### 7.2 Useful VM Commands

```bash
# Check if the bot is running
sudo systemctl status research-agent

# View live logs
tail -f ~/research_paper_agent/logs/bot.log

# View error logs
tail -f ~/research_paper_agent/logs/bot_error.log

# Restart after config changes
sudo systemctl restart research-agent

# Stop the bot
sudo systemctl stop research-agent

# View full journal
sudo journalctl -u research-agent -n 50 --no-pager

# Manually trigger a backup
~/research_paper_agent/backup.sh

# List backups
ls -la ~/research_paper_agent/backups/
```

### 7.3 Backups

The deploy script sets up a **daily cron job** that backs up `knowledge_base/` and `user_model/` at 3 AM UTC. It keeps the 7 most recent snapshots.

```bash
# Check backup log
tail ~/research_paper_agent/logs/backup.log

# Restore from a backup
cd ~/research_paper_agent
tar xzf backups/agent-data-YYYY-MM-DD.tar.gz
sudo systemctl restart research-agent
```

### 7.4 Common Issues

| Symptom | Fix |
|---|---|
| Bot offline in Discord | `sudo systemctl restart research-agent` |
| `DISCORD_BOT_TOKEN not set` | Edit `.env` and restart |
| `ModuleNotFoundError: adk_connectors` | `.venv/bin/pip install adk-connector` on the VM |
| Agent responds with errors | Check `logs/bot_error.log` — likely a DeepSeek API key issue |
| Bot only works in DMs | @mention it in channels; it only responds to mentions in servers |
| Can't SSH | Check firewall ingress rule for port 22 |
| Cron backup not running | `crontab -l` to verify; `chmod +x backup.sh` if missing |

### 7.5 Cross-Device Session Sync (Optional)

If you set `DISCORD_USER_ID` in `.env`, you can also run the ADK web UI locally and see your Discord conversations:

```bash
# On your Mac (NOT the VM):
cd /Users/andrelawas/Documents/Codex/2026-07-01/add
research_paper_agent/.venv/bin/adk web research_paper_agent --port 8000
```

Then open `http://localhost:8000` — your Discord chats appear under the "user" namespace.

> **Note:** This requires `session_management_across_device=True` (already set in `discord_bot.py`). The VM and your Mac share the same SQLite DB path structure, so sessions are readable from either side.

---

## 8. Daily Usage

Once deployed, just open Discord on your phone and @mention the bot (or DM it). Example prompts:

- `Ingest all papers in the papers folder.`
- `Brief me on all papers.`
- `Search for evidence about transformer attention.`
- `Compare the papers on evaluation methodology.`
- `Make a study guide with recall questions.`
- `Grill me on the limitations across all papers.`
- `Remember: I prefer concise answers with citations.`
- `Audit how you should improve around my style.`

### 8.1 Adding New Papers

```bash
# From your Mac:
scp your-new-paper.pdf oracle:~/research_paper_agent/papers/
```

Then ask the bot: `Ingest all papers in the papers folder.`

### 8.2 Updating the Code

```bash
# From your Mac:
cd /Users/andrelawas/Documents/Codex/2026-07-01/add/research_paper_agent
./deploy.sh <YOUR_VM_PUBLIC_IP>
```

The deploy script uses rsync to sync changes and restarts the service automatically.

---

## Cost Summary

| Item | Monthly Cost |
|---|---|
| Oracle VM (4 ARM cores, 24 GB RAM) | **$0** |
| 200 GB block storage | **$0** |
| 10 TB outbound bandwidth | **$0** |
| DeepSeek API (pay-per-token) | **Same as local use** |
| Discord API | **$0** |
| **Total** | **Just your DeepSeek usage** |
