"""Production ASGI application factory.

Startup fails closed when owner authentication or Regulation encryption is
missing. Model credentials are intentionally optional: the deterministic
offline protocol remains available when OpenAI is unavailable.
"""

from __future__ import annotations

import os

from .api import ApiConfig, create_app
from .encryption import KeyManager
from .model_provider import OpenAIProvider
from .regulation_persistence import EncryptedRegulationPersistence
from .stores import StoreRegistry


def create_production_app():
    config = ApiConfig()
    if not config.is_configured:
        raise RuntimeError("PKM_API_KEY_HASH is required in production")

    keys = KeyManager()
    keys.initialize()
    registry = StoreRegistry()
    persistence = EncryptedRegulationPersistence(
        registry.regulation,
        keys,
        owner_id=os.getenv("PKM_OWNER_ID", "owner"),
    )
    provider = OpenAIProvider()

    return create_app(
        store_registry=registry,
        config=config,
        owner_id=os.getenv("PKM_OWNER_ID", "owner"),
        model_provider=provider,
        regulation_persistence=persistence,
    )
