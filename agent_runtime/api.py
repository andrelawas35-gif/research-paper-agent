"""Minimal FastAPI service — F4 from implementation-plan-regulation-pkm.md.

ADR 0096: Single-Owner Private Access and Explicit Channel Linking.
ADR 0115: Production Observability Excludes Personal Content by Default.
ADR 0116: Single Hardened VM with Graceful Degradation.

Provides:
- Owner authentication (API-key, single-owner)
- Health / readiness endpoints
- Request correlation (X-Request-ID)
- Metadata-only access audit events
- No sensitive data in health or audit logs
"""

import hashlib
import hmac
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .event_envelope import Domain, EventEnvelope, EventStore, Sensitivity
from .stores import StoreRegistry

# ── Configuration ────────────────────────────────────────────────────


@dataclass
class ApiConfig:
    """Configuration loaded from environment."""

    owner_api_key_hash: str = field(
        default_factory=lambda: os.getenv("PKM_API_KEY_HASH", "")
    )
    cors_origins: List[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "").split(",")
        if os.getenv("CORS_ORIGINS") else ["http://localhost:5173"]
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.owner_api_key_hash)


# ── Authentication ───────────────────────────────────────────────────


class AuthenticationError(HTTPException):
    """401 with no sensitive detail leakage."""

    def __init__(self) -> None:
        super().__init__(status_code=401, detail="Authentication required")


def verify_api_key(provided_key: str, expected_hash: str) -> bool:
    """Constant-time API key verification."""
    if not provided_key or not expected_hash:
        return False
    provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()
    return hmac.compare_digest(provided_hash, expected_hash)


def require_auth(config: ApiConfig):
    """Dependency: require valid API key in X-API-Key header."""

    async def _auth(request: Request) -> None:
        api_key = request.headers.get("X-API-Key", "")
        if not verify_api_key(api_key, config.owner_api_key_hash):
            raise AuthenticationError()

    return _auth


# ── Audit logger ─────────────────────────────────────────────────────


@dataclass
class AuditLogger:
    """Metadata-only access audit. Never logs content or sensitive data."""

    _store: EventStore = field(init=False)

    def __post_init__(self) -> None:
        import tempfile
        audit_dir = os.getenv("AUDIT_LOG_DIR", tempfile.gettempdir())
        self._store = EventStore(
            __import__("pathlib").Path(audit_dir) / "audit.jsonl"
        )

    def set_path(self, path: Any) -> None:
        self._store = __import__("pathlib").Path(path)  # type: ignore[assignment]
        from .event_envelope import EventStore
        self._store = EventStore(path)

    def log_access(
        self,
        *,
        owner_id: str,
        endpoint: str,
        method: str,
        correlation_id: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Log an access event with metadata only — no content, no payload."""
        envelope = EventEnvelope.create(
            owner_id=owner_id,
            domain=Domain.OPERATIONAL,
            event_type="api_access",
            schema_version=1,
            sensitivity=Sensitivity.INTERNAL,
            provenance={"source": "api"},
            payload={
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
            },
            correlation_id=correlation_id,
        )
        self._store.append(envelope)


# ── Middleware ────────────────────────────────────────────────────────


class CorrelationMiddleware:
    """Inject X-Request-ID and log access audit."""

    def __init__(self, app: FastAPI, audit: AuditLogger, owner_id: str):
        self._app = app
        self._audit = audit
        self._owner_id = owner_id

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        correlation_id = str(uuid.uuid4())
        start = time.monotonic()
        status_code = 500

        # Inject correlation ID into request state
        async def _receive() -> Any:
            return await receive()

        async def _send(message: Any) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = dict(message.get("headers", []))
                headers[b"x-request-id"] = correlation_id.encode()
                message["headers"] = list(headers.items())
            await send(message)

        await self._app(scope, _receive, _send)

        # Log audit after response
        duration = (time.monotonic() - start) * 1000
        self._audit.log_access(
            owner_id=self._owner_id,
            endpoint=scope.get("path", ""),
            method=scope.get("method", ""),
            correlation_id=correlation_id,
            status_code=status_code,
            duration_ms=duration,
        )


# ── Application factory ──────────────────────────────────────────────


def create_app(
    *,
    store_registry: Optional[StoreRegistry] = None,
    config: Optional[ApiConfig] = None,
    audit: Optional[AuditLogger] = None,
    owner_id: str = "default",
    model_provider: Any = None,
    regulation_persistence: Any = None,
) -> FastAPI:
    """Create the FastAPI application.

    Args:
        store_registry: The store registry (created if not provided).
        config: API configuration (loaded from env if not provided).
        audit: Audit logger (created if not provided).
        owner_id: The owner identifier.
        model_provider: Optional ModelProvider for Regulation endpoints.

    Returns:
        Configured FastAPI application.
    """
    _config = config or ApiConfig()
    _registry = store_registry or StoreRegistry()
    _audit = audit or AuditLogger()
    _owner_id = owner_id

    app = FastAPI(
        title="Personal Knowledge Manager",
        version="0.1.0",
        docs_url=None if not _config.is_configured else "/docs",
        redoc_url=None,
    )

    # CORS for PWA
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_config.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["X-API-Key", "X-Request-ID", "Content-Type"],
    )

    # ── Health endpoints (no auth required) ──────────────────────────

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        """Basic health check. Reveals no sensitive data."""
        return {
            "status": "ok",
            "version": "0.1.0",
            "timestamp": _now_iso(),
        }

    @app.get("/health/ready")
    async def ready() -> Dict[str, Any]:
        """Readiness check. Verifies stores are accessible.

        Does NOT reveal whether regulation store has data, only that
        it is reachable.
        """
        checks: Dict[str, str] = {}
        try:
            _registry.operational.replay()
            checks["operational_store"] = "ok"
        except Exception:
            checks["operational_store"] = "error"

        try:
            _registry.general_pkm.replay()
            checks["general_pkm_store"] = "ok"
        except Exception:
            checks["general_pkm_store"] = "error"

        try:
            _registry.regulation.replay()
            checks["regulation_store"] = "ok"
        except Exception:
            checks["regulation_store"] = "error"

        all_ok = all(v == "ok" for v in checks.values())
        payload = {
            "status": "ready" if all_ok else "degraded",
            "checks": checks,
        }
        if not all_ok:
            return JSONResponse(status_code=503, content=payload)
        return payload

    # ── Protected endpoints (auth required) ──────────────────────────

    _auth = require_auth(_config)

    @app.get("/api/me")
    async def me(request: Request) -> Dict[str, Any]:
        """Return current owner identity (non-sensitive)."""
        await _auth(request)
        return {"owner_id": _owner_id, "authenticated": True}

    @app.get("/api/audit")
    async def list_audit(request: Request) -> Dict[str, Any]:
        """List access audit entries (metadata only)."""
        await _auth(request)
        events = _audit._store.replay()
        return {
            "count": len(events),
            "entries": [
                {
                    "timestamp": e.timestamp,
                    "endpoint": e.payload.get("endpoint"),
                    "method": e.payload.get("method"),
                    "status_code": e.payload.get("status_code"),
                    "correlation_id": e.correlation_id,
                }
                for e in events[-100:]  # Last 100 entries
            ],
        }

    # ── Store inspection (auth required, content-limited) ────────────

    @app.get("/api/stores/summary")
    async def store_summary(request: Request) -> Dict[str, Any]:
        """Return event counts per store. No content or sensitive data."""
        await _auth(request)
        return {
            "operational_events": len(_registry.operational.replay()),
            "general_pkm_events": len(_registry.general_pkm.replay()),
            "regulation_events": len(_registry.regulation.replay()),
        }

    # ── Regulation API router (U1) ──────────────────────────────────

    # Shared state for regulation and privacy routers
    _shared_sessions: Dict[str, Any] = {}
    _shared_rules: Dict[str, Any] = {}

    from .api_regulation import create_regulation_router
    from .api_privacy import create_privacy_router

    _regulation_router = create_regulation_router(
        store_registry=_registry,
        owner_id=_owner_id,
        model_provider=model_provider,
        sessions_dict=_shared_sessions,
        rules_dict=_shared_rules,
        persistence=regulation_persistence,
        auth_dependency=_auth,
    )
    app.include_router(_regulation_router)

    # ── Privacy API router (U3) ─────────────────────────────────────

    _privacy_router = create_privacy_router(
        store_registry=_registry,
        owner_id=_owner_id,
        sessions_dict=_shared_sessions,
        rules_dict=_shared_rules,
        persistence=regulation_persistence,
        auth_dependency=_auth,
    )
    app.include_router(_privacy_router)

    return app


# ── Helpers ──────────────────────────────────────────────────────────


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
