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

## 2. Provision off-VM record-key custody

In the OCI Console, create a private Standard Object Storage bucket named, for
example, `pkm-record-keys`. Leave versioning **Disabled** and add no retention
rule. This bucket stores only independently destructible random data-encryption
keys; Regulation ciphertext remains on the VM and in Restic.

Create an instance-principal dynamic group whose matching rule selects this VM
(prefer its instance OCID rather than the whole compartment), then grant only:

```text
Allow dynamic-group <pkm-vm-group> to read buckets in compartment <compartment> where target.bucket.name='<bucket>'
Allow dynamic-group <pkm-vm-group> to manage objects in compartment <compartment> where target.bucket.name='<bucket>'
```

The first permission lets startup verify versioning and retention; the second
allows per-record key create/read/delete. Do not grant bucket management, and do
not enable object versioning later. Record the Object Storage namespace shown
in the bucket details.

## 3. First deployment

From the Mac workspace:

```bash
chmod +x deploy.sh backup.sh deploy/install-oracle-vm.sh deploy/verify-restic-restore.sh
export OCI_RECORD_KEY_NAMESPACE='<namespace>'
export OCI_RECORD_KEY_BUCKET='pkm-record-keys'
./deploy.sh <VM_PUBLIC_IP> ubuntu
```

The installer:

- requires Python 3.12+ (Ubuntu 24.04)
- installs Node 24 LTS, which exceeds the frontend's Node 20.19 minimum
- builds the PWA, then deletes `node_modules` from the release
- binds FastAPI to `127.0.0.1:8000` and Caddy to `127.0.0.1:8080`
- creates `/var/lib/pkm` for persistent data
- authenticates to the external key bucket with the VM instance principal
- refuses startup if the key bucket is unavailable, versioned, or retained
- generates and prints the owner access key once
- keeps the newest three atomic releases

Save the printed owner access key in a password manager. The VM stores only its
SHA-256 hash. If it is lost, generate a new key and replace
`PKM_API_KEY_HASH` in `/etc/pkm/pkm.env`.

## 4. Configure GPT

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

## 5. Private HTTPS with Tailscale

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

## 6. Encrypted off-VM recovery

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

Initialize and back up. For restore verification, independently stage the exact
release source (for example, a fresh checkout of the committed release) outside
`/opt/pkm/current`; the verifier creates a fresh virtual environment:

```bash
sudo bash -c 'set -a; source /etc/pkm/backup.env; set +a; restic init'
sudo systemctl start pkm-backup.service
sudo RECOVERY_SOURCE_DIR=/tmp/pkm-clean-release \
  RECOVERY_ENV_FILE=/root/recovery/pkm.env \
  RECOVERY_EXPECTED_MIN_SESSIONS=1 \
  RECOVERY_EXPECTED_MIN_RULES=4 \
  /opt/pkm/current/deploy/verify-restic-restore.sh
sudo systemctl enable --now pkm-backup.timer
systemctl list-timers pkm-backup.timer
```

Keep the Restic credentials and a protected recovery copy of `pkm.env` outside
the VM. Restic backs up Regulation ciphertext but excludes `pkm.env`,
`backup.env`, and its password file. Recovery also requires OCI
instance-principal access to the
record-key bucket; a retained backup cannot decrypt a record after that
record's external key has been deleted.

Do not rely on the production VM's identity for recovery. Create a second,
normally stopped recovery instance (or a temporary replacement instance) in a
separate `pkm-recovery-group` dynamic group. Grant it `read buckets` and `read
objects` only for the record-key bucket. The production group remains the only
principal allowed to create or delete record-key objects. Stage the protected
recovery env and Restic credentials independently on the recovery instance.

```text
Allow dynamic-group <pkm-recovery-group> to read buckets in compartment <compartment> where target.bucket.name='<bucket>'
Allow dynamic-group <pkm-recovery-group> to read objects in compartment <compartment> where target.bucket.name='<bucket>'
```

Before each drill, create a disposable completed Regulation session and record
the Privacy Center's session and rule counts. The verifier requires those
minimum counts and decrypts the restored state; constructing the app alone is
not considered recovery evidence.

## 7. Launch verification

```bash
sudo systemctl status pkm-api caddy --no-pager
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/health/ready
sudo journalctl -u pkm-api -n 100 --no-pager
sudo systemctl start pkm-backup.service
sudo RECOVERY_SOURCE_DIR=/tmp/pkm-clean-release \
  RECOVERY_ENV_FILE=/root/recovery/pkm.env \
  RECOVERY_EXPECTED_MIN_SESSIONS=1 \
  RECOVERY_EXPECTED_MIN_RULES=4 \
  /opt/pkm/current/deploy/verify-restic-restore.sh
```

On the PWA:

1. Unlock with the owner access key.
2. Create and complete a non-private Regulation check-in.
3. Restart the API and confirm the session is still present.
4. Confirm a private check-in disappears after restart.
5. Export, inspect, and remove a test session from active history.
6. Delete a disposable session and prove a pre-deletion database backup cannot
   decrypt it after the external record key is destroyed.
7. Install the PWA from the browser and repeat under weak connectivity.

Only begin the seven-day shadow-use period after every check passes.

## 8. Operations

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
