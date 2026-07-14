"""Production ASGI application factory.

Startup fails closed when owner authentication or Regulation encryption is
missing. Model credentials are intentionally optional: the deterministic
offline protocol remains available when OpenAI is unavailable.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from .api import ApiConfig, create_app
from .encryption import KeyManager
from .model_provider import OpenAIProvider
from .regulation_persistence import EncryptedRegulationPersistence
from .record_keys import (
    FileRecordKeyProvider,
    RecordKeyProvider,
    create_record_key_provider_from_env,
)
from .stores import StoreRegistry

PROJECT_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def create_production_app(
    *,
    record_key_provider: RecordKeyProvider | None = None,
    load_project_env: bool = True,
):
    """Build the PKM API without replacing deployment-provided settings.

    The systemd unit supplies its own ``EnvironmentFile`` in production. For
    local development, load the project ``.env`` so the documented Uvicorn
    command starts the same configured API used by the PWA.
    """
    if load_project_env:
        load_dotenv(PROJECT_ENV_PATH, override=False)

    config = ApiConfig()
    if not config.is_configured:
        raise RuntimeError("PKM_API_KEY_HASH is required in production")

    keys = None
    if any(
        os.getenv(name)
        for name in ("REGULATION_KEY_PATH", "REGULATION_KEY", "REGULATION_KEY_DIR")
    ):
        keys = KeyManager()
        keys.initialize()
    registry = StoreRegistry()
    protected_record_keys = (
        record_key_provider or create_record_key_provider_from_env()
    )
    persistence = EncryptedRegulationPersistence(
        registry.regulation,
        keys,
        owner_id=os.getenv("PKM_OWNER_ID", "owner"),
        record_keys=protected_record_keys,
        allow_legacy=False,
    )
    provider = OpenAIProvider()

    return create_app(
        store_registry=registry,
        config=config,
        owner_id=os.getenv("PKM_OWNER_ID", "owner"),
        model_provider=provider,
        regulation_persistence=persistence,
        readiness_checks={
            "record_key_provider": protected_record_keys.validate_configuration,
        },
    )


def create_local_app():
    """Build a local-development API with owner-only file record keys.

    This factory is intentionally separate from ``create_production_app``:
    production must retain external OCI key custody, while local development
    needs a self-contained API for the Vite PWA without VM credentials.
    """
    load_dotenv(PROJECT_ENV_PATH, override=False)
    data_dir = Path(os.getenv("PKM_DATA_DIR", "data"))
    return create_production_app(
        record_key_provider=FileRecordKeyProvider(data_dir / "record-keys"),
        load_project_env=False,
    )
