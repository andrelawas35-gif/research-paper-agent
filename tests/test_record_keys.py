"""Behavioral tests for per-record cryptographic key custody."""

from pathlib import Path

import pytest

from agent_runtime.encryption import KeyNotFoundError
from agent_runtime.record_keys import FileRecordKeyProvider
from agent_runtime.record_keys import OCIObjectStorageRecordKeyProvider
from agent_runtime.record_keys import create_record_key_provider_from_env


class _Response:
    def __init__(self, data) -> None:
        self.data = data


class _ObjectBody:
    def __init__(self, content: bytes) -> None:
        self.content = content


class _StreamingObjectBody:
    def __init__(self, content: bytes) -> None:
        self.raw = type("Raw", (), {"read": lambda self: content})()


class _FakeObjectStorageClient:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.versioning = "Disabled"
        self.retention_rules: list[object] = []

    def get_bucket(self, namespace: str, bucket: str) -> _Response:
        return _Response(type("Bucket", (), {"versioning": self.versioning})())

    def list_retention_rules(self, namespace: str, bucket: str) -> _Response:
        return _Response(type("Rules", (), {"items": self.retention_rules})())

    def put_object(
        self,
        namespace: str,
        bucket: str,
        name: str,
        body: bytes,
        **kwargs,
    ) -> _Response:
        if kwargs.get("if_none_match") == "*" and name in self.objects:
            raise RuntimeError("already exists")
        self.objects[name] = body
        return _Response(None)

    def get_object(self, namespace: str, bucket: str, name: str) -> _Response:
        if name not in self.objects:
            raise KeyError(name)
        return _Response(_ObjectBody(self.objects[name]))

    def head_object(self, namespace: str, bucket: str, name: str) -> _Response:
        if name not in self.objects:
            raise KeyError(name)
        return _Response(None)

    def delete_object(self, namespace: str, bucket: str, name: str) -> _Response:
        self.objects.pop(name, None)
        return _Response(None)


def test_file_record_key_survives_restart_and_destruction_is_irreversible(
    tmp_path: Path,
) -> None:
    key_directory = tmp_path / "record-keys"
    first = FileRecordKeyProvider(key_directory)
    original = first.get_or_create("session:reg-1")

    restarted = FileRecordKeyProvider(key_directory)
    assert restarted.get("session:reg-1") == original

    restarted.destroy("session:reg-1")

    assert not restarted.exists("session:reg-1")
    with pytest.raises(KeyNotFoundError):
        restarted.get("session:reg-1")
    assert restarted.was_destroyed("session:reg-1")
    assert [path.suffix for path in key_directory.glob("*")] == [".destroyed"]


def test_oci_record_keys_stay_off_vm_and_bucket_must_allow_permanent_delete() -> None:
    client = _FakeObjectStorageClient()
    provider = OCIObjectStorageRecordKeyProvider(
        client=client,
        namespace="tenant",
        bucket="pkm-record-keys",
    )

    provider.validate_configuration()
    key = provider.get_or_create("record:reg-1")
    assert provider.get("record:reg-1") == key
    assert all("record:reg-1" not in object_name for object_name in client.objects)

    provider.destroy("record:reg-1")
    assert not provider.exists("record:reg-1")
    assert provider.was_destroyed("record:reg-1")

    client.versioning = "Enabled"
    with pytest.raises(RuntimeError, match="versioning must be Disabled"):
        provider.validate_configuration()

    client.versioning = "Disabled"
    client.retention_rules = [object()]
    with pytest.raises(RuntimeError, match="retention rules must be empty"):
        provider.validate_configuration()


def test_production_provider_factory_requires_validated_oci_custody(
    monkeypatch,
) -> None:
    client = _FakeObjectStorageClient()
    monkeypatch.setenv("REGULATION_RECORD_KEY_PROVIDER", "oci")
    monkeypatch.setenv("OCI_RECORD_KEY_NAMESPACE", "tenant")
    monkeypatch.setenv("OCI_RECORD_KEY_BUCKET", "pkm-record-keys")

    provider = create_record_key_provider_from_env(client=client)

    assert isinstance(provider, OCIObjectStorageRecordKeyProvider)
    assert provider.get_or_create("record:one")

    monkeypatch.delenv("REGULATION_RECORD_KEY_PROVIDER")
    with pytest.raises(RuntimeError, match="must be 'oci'"):
        create_record_key_provider_from_env(client=client)


def test_oci_provider_reads_sdk_streaming_response() -> None:
    client = _FakeObjectStorageClient()
    provider = OCIObjectStorageRecordKeyProvider(
        client=client, namespace="tenant", bucket="keys"
    )
    key = bytes(range(32))
    client.get_object = lambda *args: _Response(_StreamingObjectBody(key.hex().encode()))

    assert provider.get("record:streamed") == key
