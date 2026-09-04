"""CHAT01 fail-closed request metadata guard for SIC-ID registration/session creation.

The canonical ``core.case_engine.CaseEngine`` remains the only identity/session
storage authority.  This module only hardens its two trusted auth mutations so
blank or whitespace request/idempotency metadata cannot enter ``core_requests``
or create cross-operation collisions.
"""
from __future__ import annotations

from typing import Any

from .case_engine import CaseEngine as _BaseCaseEngine
from .case_engine import CoreError

AUTH_SESSION_GUARD_VERSION = "1.0.0"

# Capture the canonical implementations before installing the wrappers.  The
# wrappers delegate to these exact methods; no second user/session engine exists.
_ORIGINAL_REGISTER_USER = _BaseCaseEngine.register_user
_ORIGINAL_CREATE_SESSION = _BaseCaseEngine.create_session


def _required_meta(value: str, code: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CoreError(code, f"{field} is required", 400)
    return value.strip()


def _register_user(
    self: _BaseCaseEngine,
    sic_id: str,
    profile: dict[str, Any],
    idempotency_key: str,
    request_id: str,
) -> dict:
    """Reject unattributable registration before any DB write."""
    request_id = _required_meta(request_id, "REQUEST_ID_REQUIRED", "request_id")
    idempotency_key = _required_meta(
        idempotency_key,
        "IDEMPOTENCY_KEY_REQUIRED",
        "idempotency_key",
    )
    return _ORIGINAL_REGISTER_USER(
        self,
        sic_id,
        profile,
        idempotency_key,
        request_id,
    )


def _create_session(
    self: _BaseCaseEngine,
    user_id: str,
    sic_id: str,
    request_id: str,
    idempotency_key: str,
    ttl_seconds: int = 3600,
) -> dict:
    """Reject unattributable session creation before any DB write."""
    request_id = _required_meta(request_id, "REQUEST_ID_REQUIRED", "request_id")
    idempotency_key = _required_meta(
        idempotency_key,
        "IDEMPOTENCY_KEY_REQUIRED",
        "idempotency_key",
    )
    return _ORIGINAL_CREATE_SESSION(
        self,
        user_id,
        sic_id,
        request_id,
        idempotency_key,
        ttl_seconds,
    )


# Trusted legacy consumers import CaseEngine from ``core.case_engine`` directly.
# Patch the existing class rather than introducing a parallel identity authority.
_BaseCaseEngine.register_user = _register_user
_BaseCaseEngine.create_session = _create_session
