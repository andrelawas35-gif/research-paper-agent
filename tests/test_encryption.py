"""Tests for F3: Authenticated encryption and key loading."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


# Override the conftest autouse fixture — encryption tests are self-contained.
@pytest.fixture(autouse=True)
def _isolate_paths() -> None:
    """No-op: encryption tests do not need file-system isolation."""
    pass


from agent_runtime.encryption import (
    AES_GCM_KEY_LENGTH,
    DecryptionError,
    EncryptedRecord,
    EncryptionError,
    KeyCompromiseError,
    KeyManager,
    KeyNotFoundError,
    decrypt,
    decrypt_sensitive_payload,
    encrypt,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _random_key() -> bytes:
    import secrets
    return secrets.token_bytes(AES_GCM_KEY_LENGTH)


def _key_hex(key: bytes) -> str:
    return key.hex()


# ── encrypt / decrypt round-trip ─────────────────────────────────────


class TestEncryptDecrypt:
    def test_round_trip(self) -> None:
        key = _random_key()
        plaintext = "sensitive regulation data"
        record = encrypt(plaintext, key=key, key_id="k1")
        result = decrypt(record, key=key)
        assert result == plaintext

    def test_round_trip_unicode(self) -> None:
        key = _random_key()
        plaintext = "emoji 🎉 and 日本語"
        record = encrypt(plaintext, key=key, key_id="k1")
        result = decrypt(record, key=key)
        assert result == plaintext

    def test_round_trip_empty_string(self) -> None:
        key = _random_key()
        plaintext = ""
        record = encrypt(plaintext, key=key, key_id="k1")
        result = decrypt(record, key=key)
        assert result == plaintext

    def test_round_trip_large_payload(self) -> None:
        key = _random_key()
        plaintext = "x" * 100_000
        record = encrypt(plaintext, key=key, key_id="k1")
        result = decrypt(record, key=key)
        assert result == plaintext

    def test_different_ciphertexts_for_same_plaintext(self) -> None:
        key = _random_key()
        plaintext = "same data"
        r1 = encrypt(plaintext, key=key, key_id="k1")
        r2 = encrypt(plaintext, key=key, key_id="k1")
        # Different IV → different ciphertext
        assert r1.ciphertext_b64 != r2.ciphertext_b64
        # But both decrypt to same plaintext
        assert decrypt(r1, key=key) == decrypt(r2, key=key) == plaintext

    def test_record_to_dict_and_back(self) -> None:
        key = _random_key()
        record = encrypt("test", key=key, key_id="k1")
        d = record.to_dict()
        r2 = EncryptedRecord.from_dict(d)
        assert decrypt(r2, key=key) == "test"


# ── Wrong key / tampering ────────────────────────────────────────────


class TestDecryptionFailures:
    def test_wrong_key_fails_closed(self) -> None:
        k1 = _random_key()
        k2 = _random_key()
        record = encrypt("secret", key=k1, key_id="k1")
        with pytest.raises(DecryptionError):
            decrypt(record, key=k2)

    def test_tampered_ciphertext_fails(self) -> None:
        key = _random_key()
        record = encrypt("secret", key=key, key_id="k1")
        tampered = EncryptedRecord(
            ciphertext_b64="AAAA" + record.ciphertext_b64[4:],
            iv_b64=record.iv_b64,
            tag_b64=record.tag_b64,
            key_id=record.key_id,
        )
        with pytest.raises(DecryptionError):
            decrypt(tampered, key=key)

    def test_tampered_tag_fails(self) -> None:
        key = _random_key()
        record = encrypt("secret", key=key, key_id="k1")
        tampered = EncryptedRecord(
            ciphertext_b64=record.ciphertext_b64,
            iv_b64=record.iv_b64,
            tag_b64="AAAA" + record.tag_b64[4:],
            key_id=record.key_id,
        )
        with pytest.raises(DecryptionError):
            decrypt(tampered, key=key)

    def test_tampered_iv_fails(self) -> None:
        key = _random_key()
        record = encrypt("secret", key=key, key_id="k1")
        tampered = EncryptedRecord(
            ciphertext_b64=record.ciphertext_b64,
            iv_b64="AAAA" + record.iv_b64[4:],
            tag_b64=record.tag_b64,
            key_id=record.key_id,
        )
        with pytest.raises(DecryptionError):
            decrypt(tampered, key=key)

    def test_invalid_key_length_fails(self) -> None:
        short_key = b"short"
        with pytest.raises(EncryptionError, match="Key must be 32 bytes"):
            encrypt("test", key=short_key, key_id="k1")

    def test_decrypt_with_invalid_key_length_fails(self) -> None:
        key = _random_key()
        record = encrypt("test", key=key, key_id="k1")
        with pytest.raises(DecryptionError, match="Key must be 32 bytes"):
            decrypt(record, key=b"short")

    def test_invalid_base64_fails(self) -> None:
        key = _random_key()
        record = EncryptedRecord(
            ciphertext_b64="!!!not-valid-base64!!!",
            iv_b64="!!!invalid!!!",
            tag_b64="!!!invalid!!!",
            key_id="k1",
        )
        with pytest.raises(DecryptionError, match="Invalid base64"):
            decrypt(record, key=key)


# ── decrypt_sensitive_payload ────────────────────────────────────────


class TestDecryptSensitivePayload:
    def test_round_trip_dict_payload(self) -> None:
        key = _random_key()
        import json
        from agent_runtime.encryption import encrypt as raw_encrypt
        payload = {"session_id": "abc", "facts": ["fact1", "fact2"]}
        plaintext = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        record = raw_encrypt(plaintext, key=key, key_id="k1")
        result = decrypt_sensitive_payload(record.to_dict(), key=key)
        assert result == payload


# ── KeyManager ───────────────────────────────────────────────────────


class TestKeyManager:
    def test_initialize_from_env_hex(self, monkeypatch) -> None:
        key = _random_key()
        monkeypatch.setenv("REGULATION_KEY", _key_hex(key))
        monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
        monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)

        km = KeyManager()
        km.initialize()
        assert km.active_key_id == "default"
        assert km.active_key == key

    def test_initialize_from_key_file(self, monkeypatch, tmp_path) -> None:
        key = _random_key()
        key_file = tmp_path / "regulation.key"
        key_file.write_text(_key_hex(key))

        monkeypatch.setenv("REGULATION_KEY_PATH", str(key_file))
        monkeypatch.delenv("REGULATION_KEY", raising=False)
        monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)

        km = KeyManager()
        km.initialize()
        assert km.active_key_id == "default"
        assert km.active_key == key

    def test_initialize_from_key_dir(self, monkeypatch, tmp_path) -> None:
        k1 = _random_key()
        k2 = _random_key()
        key_dir = tmp_path / "keys"
        key_dir.mkdir()
        (key_dir / "key-2026-01").write_text(_key_hex(k1))
        (key_dir / "key-2026-07").write_text(_key_hex(k2))

        monkeypatch.setenv("REGULATION_KEY_DIR", str(key_dir))
        monkeypatch.delenv("REGULATION_KEY", raising=False)
        monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)

        km = KeyManager()
        km.initialize()
        # First key alphabetically becomes active
        assert km.active_key_id in ("key-2026-01", "key-2026-07")
        assert km.has_key("key-2026-01")
        assert km.has_key("key-2026-07")

    def test_no_key_source_raises(self, monkeypatch) -> None:
        monkeypatch.delenv("REGULATION_KEY", raising=False)
        monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
        monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)

        km = KeyManager()
        with pytest.raises(KeyNotFoundError, match="No encryption key source"):
            km.initialize()

    def test_key_file_not_found_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("REGULATION_KEY_PATH", "/nonexistent/key.file")
        monkeypatch.delenv("REGULATION_KEY", raising=False)
        monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)

        km = KeyManager()
        with pytest.raises(KeyNotFoundError, match="Key file not found"):
            km.initialize()

    def test_uninitialized_raises(self) -> None:
        km = KeyManager()
        with pytest.raises(EncryptionError, match="not initialized"):
            _ = km.active_key

    def test_get_key_not_found(self, monkeypatch) -> None:
        key = _random_key()
        monkeypatch.setenv("REGULATION_KEY", _key_hex(key))
        monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
        monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)

        km = KeyManager()
        km.initialize()
        with pytest.raises(KeyNotFoundError, match="Key not found"):
            km.get_key("nonexistent")

    def test_invalid_hex_key_fails(self, monkeypatch) -> None:
        monkeypatch.setenv("REGULATION_KEY", "not-hex!!!")
        monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
        monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)

        km = KeyManager()
        with pytest.raises(EncryptionError, match="Invalid hex key"):
            km.initialize()

    def test_wrong_length_key_fails(self, monkeypatch) -> None:
        monkeypatch.setenv("REGULATION_KEY", "aabb")  # 2 bytes, not 32
        monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
        monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)

        km = KeyManager()
        with pytest.raises(EncryptionError, match="must be 32 bytes"):
            km.initialize()

    def test_encrypt_decrypt_payload(self, monkeypatch) -> None:
        key = _random_key()
        monkeypatch.setenv("REGULATION_KEY", _key_hex(key))
        monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
        monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)

        km = KeyManager()
        km.initialize()

        payload = {"session_id": "abc", "trigger": "jealousy"}
        encrypted = km.encrypt_payload(payload)
        assert "ciphertext_b64" in encrypted
        assert encrypted["key_id"] == "default"
        assert encrypted["alg"] == "AES-256-GCM"

        decrypted = km.decrypt_payload(encrypted)
        assert decrypted == payload

    def test_key_rotation(self, monkeypatch) -> None:
        key = _random_key()
        monkeypatch.setenv("REGULATION_KEY", _key_hex(key))
        monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
        monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)

        km = KeyManager()
        km.initialize()

        # Encrypt with old key
        payload = {"data": "old-key-data"}
        encrypted = km.encrypt_payload(payload)
        assert encrypted["key_id"] == "default"

        # Rotate to new key
        new_key = _random_key()
        km.rotate_key(new_key, "key-v2")
        assert km.active_key_id == "key-v2"

        # Old record still decryptable
        decrypted = km.decrypt_payload(encrypted)
        assert decrypted == payload

        # New records use new key
        new_encrypted = km.encrypt_payload({"data": "new-key-data"})
        assert new_encrypted["key_id"] == "key-v2"
        assert km.decrypt_payload(new_encrypted) == {"data": "new-key-data"}

    def test_key_destruction(self, monkeypatch) -> None:
        key = _random_key()
        monkeypatch.setenv("REGULATION_KEY", _key_hex(key))
        monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
        monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)

        km = KeyManager()
        km.initialize()

        # Encrypt with old key
        encrypted = km.encrypt_payload({"data": "will-be-gone"})

        # Rotate
        new_key = _random_key()
        km.rotate_key(new_key, "key-v2")

        # Destroy old key
        km.destroy_key("default")
        assert not km.has_key("default")

        # Old records now undecryptable
        with pytest.raises(KeyNotFoundError):
            km.decrypt_payload(encrypted)

    def test_cannot_destroy_active_key(self, monkeypatch) -> None:
        key = _random_key()
        monkeypatch.setenv("REGULATION_KEY", _key_hex(key))
        monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
        monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)

        km = KeyManager()
        km.initialize()
        with pytest.raises(EncryptionError, match="Cannot destroy the active key"):
            km.destroy_key("default")

    def test_initialize_is_idempotent(self, monkeypatch) -> None:
        key = _random_key()
        monkeypatch.setenv("REGULATION_KEY", _key_hex(key))
        monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
        monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)

        km = KeyManager()
        km.initialize()
        km.initialize()  # second call should not reload or fail
        assert km.active_key == key

    def test_rotate_with_wrong_length_key_fails(self, monkeypatch) -> None:
        key = _random_key()
        monkeypatch.setenv("REGULATION_KEY", _key_hex(key))
        monkeypatch.delenv("REGULATION_KEY_PATH", raising=False)
        monkeypatch.delenv("REGULATION_KEY_DIR", raising=False)

        km = KeyManager()
        km.initialize()
        with pytest.raises(EncryptionError, match="must be 32 bytes"):
            km.rotate_key(b"short", "bad-key")
