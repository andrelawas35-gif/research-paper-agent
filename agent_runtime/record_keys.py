"""Per-record data-encryption key seam for Regulation persistence."""

from __future__ import annotations

import hashlib
import os
import secrets
from abc import ABC, abstractmethod
from pathlib import Path

from .encryption import AES_GCM_KEY_LENGTH, KeyNotFoundError


class RecordKeyProvider(ABC):
    """Custody interface for independently destructible record keys."""

    @abstractmethod
    def validate_configuration(self) -> None: ...

    @abstractmethod
    def get_or_create(self, key_id: str) -> bytes: ...

    @abstractmethod
    def get(self, key_id: str) -> bytes: ...

    @abstractmethod
    def exists(self, key_id: str) -> bool: ...

    @abstractmethod
    def destroy(self, key_id: str) -> None: ...

    def was_destroyed(self, key_id: str) -> bool:
        """Return whether custody records an intentional, irreversible delete."""
        return False


class FileRecordKeyProvider(RecordKeyProvider):
    """Owner-only local adapter for development and migration tooling."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def _path(self, key_id: str) -> Path:
        digest = hashlib.sha256(key_id.encode("utf-8")).hexdigest()
        return self._directory / f"{digest}.key"

    def _tombstone_path(self, key_id: str) -> Path:
        digest = hashlib.sha256(key_id.encode("utf-8")).hexdigest()
        return self._directory / f"{digest}.destroyed"

    def validate_configuration(self) -> None:
        """Local development adapter has no external policy to validate."""

    def get_or_create(self, key_id: str) -> bytes:
        if self.was_destroyed(key_id):
            raise KeyNotFoundError(f"Record key was destroyed: {key_id}")
        path = self._path(key_id)
        try:
            return self.get(key_id)
        except KeyNotFoundError:
            pass

        self._directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        key = secrets.token_bytes(AES_GCM_KEY_LENGTH)
        try:
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError:
            return self.get(key_id)
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            handle.write(key.hex())
            handle.flush()
            os.fsync(handle.fileno())
        return key

    def get(self, key_id: str) -> bytes:
        path = self._path(key_id)
        if not path.is_file():
            raise KeyNotFoundError(f"Record key not found: {key_id}")
        try:
            key = bytes.fromhex(path.read_text(encoding="ascii").strip())
        except ValueError as exc:
            raise KeyNotFoundError(f"Record key is invalid: {key_id}") from exc
        if len(key) != AES_GCM_KEY_LENGTH:
            raise KeyNotFoundError(f"Record key is invalid: {key_id}")
        return key

    def exists(self, key_id: str) -> bool:
        return self._path(key_id).is_file()

    def destroy(self, key_id: str) -> None:
        self._directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self._path(key_id).unlink()
        except FileNotFoundError:
            pass
        self._tombstone_path(key_id).touch(mode=0o600, exist_ok=True)

    def was_destroyed(self, key_id: str) -> bool:
        return self._tombstone_path(key_id).is_file()


class OCIObjectStorageRecordKeyProvider(RecordKeyProvider):
    """Off-VM adapter backed by a non-versioned OCI Object Storage bucket."""

    def __init__(
        self,
        *,
        client: object,
        namespace: str,
        bucket: str,
        prefix: str = "pkm-record-keys/",
    ) -> None:
        self._client = client
        self._namespace = namespace
        self._bucket = bucket
        self._prefix = prefix.rstrip("/") + "/"

    def _name(self, key_id: str) -> str:
        digest = hashlib.sha256(key_id.encode("utf-8")).hexdigest()
        return f"{self._prefix}{digest}.key"

    def _tombstone_name(self, key_id: str) -> str:
        digest = hashlib.sha256(key_id.encode("utf-8")).hexdigest()
        return f"{self._prefix}{digest}.destroyed"

    def validate_configuration(self) -> None:
        bucket = self._client.get_bucket(  # type: ignore[attr-defined]
            self._namespace, self._bucket
        ).data
        if getattr(bucket, "versioning", None) != "Disabled":
            raise RuntimeError(
                "OCI record-key bucket versioning must be Disabled"
            )
        rules = self._client.list_retention_rules(  # type: ignore[attr-defined]
            self._namespace, self._bucket
        ).data
        if list(getattr(rules, "items", []) or []):
            raise RuntimeError(
                "OCI record-key bucket retention rules must be empty"
            )

    def get_or_create(self, key_id: str) -> bytes:
        if self.was_destroyed(key_id):
            raise KeyNotFoundError(f"Record key was destroyed: {key_id}")
        try:
            return self.get(key_id)
        except KeyNotFoundError:
            pass
        key = secrets.token_bytes(AES_GCM_KEY_LENGTH)
        try:
            self._client.put_object(  # type: ignore[attr-defined]
                self._namespace,
                self._bucket,
                self._name(key_id),
                key.hex().encode("ascii"),
                if_none_match="*",
                content_type="application/octet-stream",
            )
            return key
        except Exception:
            try:
                return self.get(key_id)
            except KeyNotFoundError:
                raise

    def get(self, key_id: str) -> bytes:
        try:
            response = self._client.get_object(  # type: ignore[attr-defined]
                self._namespace, self._bucket, self._name(key_id)
            )
        except Exception as exc:
            if isinstance(exc, KeyError) or getattr(exc, "status", None) == 404:
                raise KeyNotFoundError(f"Record key not found: {key_id}") from exc
            raise
        body = response.data
        content = getattr(body, "content", None)
        if content is None:
            raw = getattr(body, "raw", None)
            if raw is None or not callable(getattr(raw, "read", None)):
                raise KeyNotFoundError(f"Record key is invalid: {key_id}")
            content = raw.read()
        try:
            key = bytes.fromhex(content.decode("ascii").strip())
        except (AttributeError, UnicodeDecodeError, ValueError) as exc:
            raise KeyNotFoundError(f"Record key is invalid: {key_id}") from exc
        if len(key) != AES_GCM_KEY_LENGTH:
            raise KeyNotFoundError(f"Record key is invalid: {key_id}")
        return key

    def exists(self, key_id: str) -> bool:
        try:
            self.get(key_id)
            return True
        except KeyNotFoundError:
            return False

    def destroy(self, key_id: str) -> None:
        try:
            self._client.delete_object(  # type: ignore[attr-defined]
                self._namespace, self._bucket, self._name(key_id)
            )
        except Exception as exc:
            if isinstance(exc, KeyError) or getattr(exc, "status", None) == 404:
                pass
            else:
                raise
        try:
            self._client.put_object(  # type: ignore[attr-defined]
                self._namespace,
                self._bucket,
                self._tombstone_name(key_id),
                b"destroyed",
                if_none_match="*",
                content_type="application/octet-stream",
            )
        except Exception:
            if not self.was_destroyed(key_id):
                raise

    def was_destroyed(self, key_id: str) -> bool:
        try:
            self._client.head_object(  # type: ignore[attr-defined]
                self._namespace, self._bucket, self._tombstone_name(key_id)
            )
            return True
        except Exception as exc:
            if isinstance(exc, KeyError) or getattr(exc, "status", None) == 404:
                return False
            raise


def create_record_key_provider_from_env(
    *, client: object | None = None
) -> RecordKeyProvider:
    """Create the fail-closed production provider from environment settings."""
    provider_name = os.getenv("REGULATION_RECORD_KEY_PROVIDER", "")
    if provider_name != "oci":
        raise RuntimeError(
            "REGULATION_RECORD_KEY_PROVIDER must be 'oci' in production"
        )
    namespace = os.getenv("OCI_RECORD_KEY_NAMESPACE", "").strip()
    bucket = os.getenv("OCI_RECORD_KEY_BUCKET", "").strip()
    if not namespace or not bucket:
        raise RuntimeError(
            "OCI_RECORD_KEY_NAMESPACE and OCI_RECORD_KEY_BUCKET are required"
        )

    if client is None:
        try:
            import oci
        except ImportError as exc:
            raise RuntimeError("The OCI Python SDK is required in production") from exc
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        client = oci.object_storage.ObjectStorageClient(
            config={}, signer=signer
        )

    provider = OCIObjectStorageRecordKeyProvider(
        client=client,
        namespace=namespace,
        bucket=bucket,
        prefix=os.getenv("OCI_RECORD_KEY_PREFIX", "pkm-record-keys/"),
    )
    provider.validate_configuration()
    return provider
