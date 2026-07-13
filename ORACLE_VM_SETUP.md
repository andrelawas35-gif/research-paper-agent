# Oracle VM Daily-Use Launch Runbook

This deploys one hardened Oracle VM as the PKM production candidate. It is a
single-host deployment with restart recovery and encrypted off-VM backups; it
does **not** claim high availability or emergency-service availability.

## 1. VM baseline

- Ubuntu 24.04 LTS, ARM64
- `VM.Standard.A1.Flex`
- Recommended: 4 OCPU, 24 GB RAM, 47–100 GB boot volume
- Oracle security list: inbound TCP 22 only
- Do not open 80, 443, 8000, or 8080 publicly

Resize the existing 1 OCPU / 6 GB A1 instance from **Compute → Instances →
Stop → Edit → Shape → 4 OCPU / 24 GB → Save → Start**. Capacity can be
temporarily unavailable; keeping the existing instance and retrying the resize
is safer than deleting it.

## 2. First deployment

Generate the Regulation recovery key on your Mac, save it in your password
manager, and provision the live copy before the first deployment:

```bash
umask 077
openssl rand -hex 32 > /tmp/pkm-regulation.key
scp /tmp/pkm-regulation.key ubuntu@<VM_PUBLIC_IP>:/tmp/pkm-regulation.key
ssh ubuntu@<VM_PUBLIC_IP> 'sudo install -d -o root -g root -m 0750 /etc/pkm/keys && sudo install -o root -g root -m 0640 /tmp/pkm-regulation.key /etc/pkm/keys/regulation.key && rm /tmp/pkm-regulation.key'
rm /tmp/pkm-regulation.key
```

From the Mac workspace:

```bash
chmod +x deploy.sh backup.sh deploy/install-oracle-vm.sh deploy/verify-restic-restore.sh
./deploy.sh <VM_PUBLIC_IP> ubuntu
```

The installer:

- requires Python 3.12+ (Ubuntu 24.04)
- installs Node 24 LTS, which exceeds the frontend's Node 20.19 minimum
- builds the PWA, then deletes `node_modules` from the release
- binds FastAPI to `127.0.0.1:8000` and Caddy to `127.0.0.1:8080`
- creates `/var/lib/pkm` for persistent data
- requires a separately provisioned `/etc/pkm/keys/regulation.key`
- generates and prints the owner access key once
- keeps the newest three atomic releases

Save the printed owner access key in a password manager. The VM stores only its
SHA-256 hash. If it is lost, generate a new key and replace
`PKM_API_KEY_HASH` in `/etc/pkm/pkm.env`.

## 3. Configure GPT

On the VM:

```bash
sudoedit /etc/pkm/pkm.env
```

Set:

```ini
OPENAI_API_KEY=sk-...
OPENAI_GPT5_MINI_MODEL=gpt-5-mini
OPENAI_GPT5_MODEL=gpt-5
```

Then:

```bash
sudo systemctl restart pkm-api
curl -fsS http://127.0.0.1:8080/health/ready
```

Without an OpenAI key, the API still starts and Regulation uses its
deterministic degradation protocol.

## 4. Private HTTPS with Tailscale

Install Tailscale using its current official Linux instructions, then:

```bash
sudo tailscale up --ssh
sudo tailscale serve --bg --yes --https=443 http://127.0.0.1:8080
tailscale serve status
```

Open the reported `https://<machine>.<tailnet>.ts.net` URL on your phone or
Mac while signed into your tailnet. Tailscale terminates HTTPS with an
automatically provisioned certificate; Caddy and FastAPI remain loopback-only.
Do not use Funnel for this private application.

## 5. Encrypted off-VM recovery

Restic encrypts the repository. Use a storage account outside this VM; a
separate provider/account gives better recovery isolation.

Create a password file that is **not** included in the backup:

```bash
sudo install -d -m 0700 /root/.config/pkm
sudo sh -c 'openssl rand -base64 48 > /root/.config/pkm/restic-password'
sudo chmod 0600 /root/.config/pkm/restic-password
sudoedit /etc/pkm/backup.env
```

Example for an S3-compatible repository:

```ini
RESTIC_REPOSITORY=s3:https://<endpoint>/<bucket>/pkm
RESTIC_PASSWORD_FILE=/root/.config/pkm/restic-password
AWS_ACCESS_KEY_ID=<backup-only-key>
AWS_SECRET_ACCESS_KEY=<backup-only-secret>
```

Initialize, back up, restore-test, then enable the timer:

```bash
sudo bash -c 'set -a; source /etc/pkm/backup.env; set +a; restic init'
sudo systemctl start pkm-backup.service
sudo APP_DIR=/opt/pkm/current /opt/pkm/current/deploy/verify-restic-restore.sh
sudo systemctl enable --now pkm-backup.timer
systemctl list-timers pkm-backup.timer
```

Keep the Restic password and Regulation recovery key as separate password-manager
items. Restic backs up encrypted application data and non-secret configuration;
it excludes `/etc/pkm/keys`, `/etc/pkm/backup.env`, and its password file. A
restore therefore requires both the Restic credentials and separately held
Regulation recovery key.

## 6. Launch verification

```bash
sudo systemctl status pkm-api caddy --no-pager
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/health/ready
sudo journalctl -u pkm-api -n 100 --no-pager
sudo systemctl start pkm-backup.service
sudo /opt/pkm/current/deploy/verify-restic-restore.sh
```

On the PWA:

1. Unlock with the owner access key.
2. Create and complete a non-private Regulation check-in.
3. Restart the API and confirm the session is still present.
4. Confirm a private check-in disappears after restart.
5. Export, inspect, and remove a test session from active history.
6. Do not begin the seven-day daily-use shadow period until ADR 0093's
   per-record cryptographic deletion is implemented and restore-tested. Current
   encrypted backup copies expire according to the configured Restic policy.
7. Install the PWA from the browser and repeat under weak connectivity.

Only begin the seven-day shadow-use period after every check passes.

## 7. Operations

```bash
sudo systemctl restart pkm-api
sudo journalctl -u pkm-api -f
sudo caddy validate --config /etc/caddy/Caddyfile
tailscale serve status
sudo systemctl start pkm-backup.service
restic snapshots
```

Rotate the owner key by generating a new plaintext key, hashing it with
SHA-256, replacing `PKM_API_KEY_HASH`, and restarting `pkm-api`. Rotate any API
key that has ever appeared in a committed file or shell history.
