"""Static guardrails for the single-VM production artifacts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_api_and_web_are_loopback_only() -> None:
    service = (ROOT / "deploy/pkm-api.service").read_text()
    caddy = (ROOT / "deploy/Caddyfile").read_text()
    assert "--host 127.0.0.1" in service
    assert "bind 127.0.0.1" in caddy
    assert "0.0.0.0" not in service + caddy


def test_deploy_requires_supported_python_and_node_minimum() -> None:
    installer = (ROOT / "deploy/install-oracle-vm.sh").read_text()
    assert "(3, 12)" in installer
    assert "minor < 19" in installer
    assert 'NODE_MAJOR="${NODE_MAJOR:-24}"' in installer


def test_example_environment_has_no_embedded_secret() -> None:
    example = (ROOT / ".env.example").read_text()
    assert "Sk-b1f0" not in example
    assert "OPENAI_API_KEY=\n" in example
    assert "DISCORD_BOT_TOKEN=\n" in example


def test_backup_is_encrypted_and_has_restore_verification() -> None:
    backup = (ROOT / "backup.sh").read_text()
    restore = (ROOT / "deploy/verify-restic-restore.sh").read_text()
    assert "RESTIC_PASSWORD_FILE" in backup
    assert "--exclude /etc/pkm/keys" in backup
    assert "--exclude /etc/pkm/backup.env" in backup
    assert "--exclude /etc/pkm/pkm.env" in backup
    assert "restic check" in backup
    assert "systemctl stop pkm-api.service" in backup
    assert "trap restart_api EXIT" in backup
    assert "restic restore latest" in restore
    assert "EncryptedRegulationPersistence" in restore
    assert "RECOVERY_SOURCE_DIR" in restore
    assert "RECOVERY_ENV_FILE" in restore
    assert "RECOVERY_EXPECTED_MIN_SESSIONS" in restore
    assert "persistence.load()" in restore
    assert "/opt/pkm/current" not in restore


def test_installer_requires_off_vm_record_key_provider() -> None:
    installer = (ROOT / "deploy/install-oracle-vm.sh").read_text()
    assert "REGULATION_RECORD_KEY_PROVIDER=oci" in installer
    assert "OCI_RECORD_KEY_NAMESPACE" in installer
    assert "OCI_RECORD_KEY_BUCKET" in installer
    assert "openssl rand -hex 32 > /etc/pkm/keys/regulation.key" not in installer
