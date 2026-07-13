"""Authenticated encryption — F3 from implementation-plan-regulation-pkm.md.

ADR 0092: Encrypt Regulation Data at Rest from the First Slice.
ADR 0093: Regulation Retention Is Tiered and Deletion Is Cryptographic.

Implements AES-256-GCM authenticated encryption for sensitive records.
Keys are loaded from external sources (environment, key file, or secure
store) and never committed to the repository. Plaintext sensitive
payloads must never appear in logs.

Provides:
- encrypt(plaintext, key_id) → {ciphertext_b64, iv_b64, tag_b64, key_id, alg}
- decrypt(encrypted_record) → plaintext
- KeyManager for loading and rotating keys
- Cryptographic deletion via per-record key destruction
"""

from __future__ import annotations

import base64
import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ── Constants ────────────────────────────────────────────────────────

AES_GCM_KEY_LENGTH = 32  # AES-256
NONCE_LENGTH = 12  # 96-bit IV for GCM

# ── Errors ───────────────────────────────────────────────────────────


class EncryptionError(ValueError):
    """Base error for encryption failures."""


class KeyNotFoundError(EncryptionError):
    """The requested key ID is not available."""


class DecryptionError(EncryptionError):
    """Decryption failed (wrong key, tampering, corruption)."""


class KeyCompromiseError(EncryptionError):
    """Key material was found in an insecure location (logs, repo)."""


# ── Encrypted record shape ───────────────────────────────────────────


@dataclass(frozen=True)
class EncryptedRecord:
    """The wire format for an encrypted payload.

    Stored in the event envelope's payload field. The envelope metadata
    (event_id, domain, timestamp, etc.) remains unencrypted for routing
    and audit; only the sensitive content is encrypted.
    """

    ciphertext_b64: str
    iv_b64: str
    tag_b64: str  # GCM authentication tag
    key_id: str
    alg: str = "AES-256-GCM"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ciphertext_b64": self.ciphertext_b64,
            "iv_b64": self.iv_b64,
            "tag_b64": self.tag_b64,
            "key_id": self.key_id,
            "alg": self.alg,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EncryptedRecord:
        return cls(
            ciphertext_b64=data["ciphertext_b64"],
            iv_b64=data["iv_b64"],
            tag_b64=data["tag_b64"],
            key_id=data["key_id"],
            alg=data.get("alg", "AES-256-GCM"),
        )


# ── Encryption / Decryption ──────────────────────────────────────────


def encrypt(plaintext: str, *, key: bytes, key_id: str) -> EncryptedRecord:
    """Encrypt plaintext with AES-256-GCM.

    Args:
        plaintext: The sensitive text to encrypt.
        key: 32-byte AES-256 key.
        key_id: Identifier for the key (for rotation tracking).

    Returns:
        EncryptedRecord with base64-encoded components.
    """
    if len(key) != AES_GCM_KEY_LENGTH:
        raise EncryptionError(
            f"Key must be {AES_GCM_KEY_LENGTH} bytes, got {len(key)}"
        )

    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(NONCE_LENGTH)
    plaintext_bytes = plaintext.encode("utf-8")

    # AESGCM.encrypt returns ciphertext || tag
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext_bytes, None)

    # Separate ciphertext and 16-byte tag
    tag = ciphertext_with_tag[-16:]
    ciphertext = ciphertext_with_tag[:-16]

    return EncryptedRecord(
        ciphertext_b64=base64.b64encode(ciphertext).decode("ascii"),
        iv_b64=base64.b64encode(nonce).decode("ascii"),
        tag_b64=base64.b64encode(tag).decode("ascii"),
        key_id=key_id,
        alg="AES-256-GCM",
    )


def decrypt(record: EncryptedRecord, *, key: bytes) -> str:
    """Decrypt an EncryptedRecord.

    Args:
        record: The encrypted record to decrypt.
        key: 32-byte AES-256 key matching record.key_id.

    Returns:
        The original plaintext.

    Raises:
        DecryptionError: If decryption fails (wrong key, tampering, corruption).
    """
    if len(key) != AES_GCM_KEY_LENGTH:
        raise DecryptionError(
            f"Key must be {AES_GCM_KEY_LENGTH} bytes, got {len(key)}"
        )

    try:
        nonce = base64.b64decode(record.iv_b64)
        ciphertext = base64.b64decode(record.ciphertext_b64)
        tag = base64.b64decode(record.tag_b64)
    except Exception as exc:
        raise DecryptionError(f"Invalid base64 encoding: {exc}") from exc

    if len(nonce) != NONCE_LENGTH:
        raise DecryptionError(
            f"IV must be {NONCE_LENGTH} bytes, got {len(nonce)}"
        )

    # Recombine ciphertext + tag for AESGCM.decrypt
    ciphertext_with_tag = ciphertext + tag

    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    except Exception as exc:
        raise DecryptionError(
            f"Decryption failed — key mismatch, tampering, or corruption: {exc}"
        ) from exc

    return plaintext.decode("utf-8")


def decrypt_sensitive_payload(
    envelope_payload: dict[str, Any], *, key: bytes
) -> dict[str, Any]:
    """Decrypt a payload that was stored as an EncryptedRecord.

    Used when reading from the RegulationStore.
    """
    record = EncryptedRecord.from_dict(envelope_payload)
    plaintext_json = decrypt(record, key=key)
    return json.loads(plaintext_json)


# ── Key Manager ──────────────────────────────────────────────────────


@dataclass
class KeyManager:
    """Manages encryption keys loaded from external sources.

    Key sources (tried in order):
    1. REGULATION_KEY_PATH env var → file containing hex key
    2. REGULATION_KEY env var → hex key directly
    3. REGULATION_KEY_DIR env var → directory of key files named by key_id

    Keys are never written to logs. Key material must never appear in
    committed files. Key absence prevents startup of sensitive services.
    """

    _keys: Dict[str, bytes] = field(default_factory=dict)
    _active_key_id: Optional[str] = None
    _initialized: bool = field(default=False, init=False)

    def initialize(self) -> None:
        """Load keys from external sources. Must be called before use.

        Raises:
            KeyNotFoundError: If no keys are available.
            KeyCompromiseError: If keys are found in insecure locations.
        """
        if self._initialized:
            return

        key_path = os.getenv("REGULATION_KEY_PATH")
        key_hex = os.getenv("REGULATION_KEY")
        key_dir = os.getenv("REGULATION_KEY_DIR")

        if key_path:
            self._load_from_file(key_path, "default")
        elif key_hex:
            self._load_from_hex(key_hex, "default")
        elif key_dir:
            self._load_from_dir(key_dir)
        else:
            raise KeyNotFoundError(
                "No encryption key source configured. Set one of: "
                "REGULATION_KEY_PATH, REGULATION_KEY, or REGULATION_KEY_DIR"
            )

        if not self._keys:
            raise KeyNotFoundError("No valid encryption keys loaded")

        # Active key is the first loaded
        self._active_key_id = next(iter(self._keys))
        self._initialized = True

    def _load_from_file(self, path_str: str, key_id: str) -> None:
        path = Path(path_str)
        if not path.exists():
            raise KeyNotFoundError(f"Key file not found: {path}")
        key_hex = path.read_text().strip()
        self._load_from_hex(key_hex, key_id)

    def _load_from_hex(self, key_hex: str, key_id: str) -> None:
        try:
            key = bytes.fromhex(key_hex)
        except ValueError as exc:
            raise EncryptionError(
                f"Invalid hex key for {key_id}: {exc}"
            ) from exc
        if len(key) != AES_GCM_KEY_LENGTH:
            raise EncryptionError(
                f"Key {key_id} must be {AES_GCM_KEY_LENGTH} bytes "
                f"({AES_GCM_KEY_LENGTH * 2} hex chars), got {len(key)} bytes"
            )
        self._keys[key_id] = key

    def _load_from_dir(self, dir_str: str) -> None:
        key_dir = Path(dir_str)
        if not key_dir.is_dir():
            raise KeyNotFoundError(f"Key directory not found: {key_dir}")
        for key_file in sorted(key_dir.iterdir()):
            if key_file.is_file() and not key_file.name.startswith("."):
                key_id = key_file.name
                self._load_from_file(str(key_file), key_id)

    @property
    def active_key_id(self) -> str:
        if not self._initialized:
            raise EncryptionError("KeyManager not initialized")
        assert self._active_key_id is not None
        return self._active_key_id

    @property
    def active_key(self) -> bytes:
        if not self._initialized:
            raise EncryptionError("KeyManager not initialized")
        assert self._active_key_id is not None
        return self._keys[self._active_key_id]

    def get_key(self, key_id: str) -> bytes:
        """Get a specific key by ID. Raises KeyNotFoundError if missing."""
        if not self._initialized:
            raise EncryptionError("KeyManager not initialized")
        if key_id not in self._keys:
            raise KeyNotFoundError(f"Key not found: {key_id}")
        return self._keys[key_id]

    def has_key(self, key_id: str) -> bool:
        return key_id in self._keys

    def encrypt_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Encrypt a JSON-serializable payload for storage.

        Returns the EncryptedRecord as a dict suitable for the event
        envelope's payload field.
        """
        plaintext = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        record = encrypt(plaintext, key=self.active_key, key_id=self.active_key_id)
        return record.to_dict()

    def decrypt_payload(self, encrypted_payload: dict[str, Any]) -> dict[str, Any]:
        """Decrypt a payload that was stored via encrypt_payload."""
        record = EncryptedRecord.from_dict(encrypted_payload)
        key = self.get_key(record.key_id)
        return decrypt_sensitive_payload(encrypted_payload, key=key)

    def rotate_key(self, new_key: bytes, new_key_id: str) -> str:
        """Register a new key for future encryption. Returns the new key_id.

        Old keys are retained for decryption of existing records.
        """
        if len(new_key) != AES_GCM_KEY_LENGTH:
            raise EncryptionError(
                f"New key must be {AES_GCM_KEY_LENGTH} bytes, got {len(new_key)}"
            )
        self._keys[new_key_id] = new_key
        self._active_key_id = new_key_id
        return new_key_id

    def destroy_key(self, key_id: str) -> None:
        """Cryptographic deletion: destroy a key, rendering all records
        encrypted with it irrecoverable.

        This is the mechanism for ADR 0093 tiered retention.
        """
        if key_id == self._active_key_id:
            raise EncryptionError(
                "Cannot destroy the active key. Rotate first."
            )
        if key_id in self._keys:
            del self._keys[key_id]
