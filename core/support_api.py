"""Trusted support-principal facade over CHAT01 canonical SIC-ID sessions.

CHAT01 owns identity/session truth. Telegram or another support transport may own
its own authenticated principal/session token, but it must not infer Case
ownership or mint a parallel CryptoAID identity. This facade accepts only an
opaque support-session token and delegates the transport-specific lookup to an
injected trusted resolver. The resolver may return an existing Core
``session_id`` + ``sic_id`` pair; Core then re-validates that pair against the
canonical live session before returning the privacy-minimized Case-owner
verdict.

The resolver is a runtime trust boundary, not a second authority. It must be
wired only after the transport has authenticated its principal. No Telegram ID,
SIC-ID, user_id, wallet, Evidence or payment data is returned by this facade.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .api import CoreAPI
from .case_engine import CoreError

SUPPORT_API_FACADE_VERSION = "1.0.0"


class TrustedSupportAPI:
    """Fail-closed bridge from a trusted support principal to Core Case auth."""

    def __init__(
        self,
        db_path: str | Path,
        principal_resolver: Callable[[str], Mapping[str, Any] | None],
    ):
        if not callable(principal_resolver):
            raise CoreError(
                "SUPPORT_RESOLVER_REQUIRED",
                "trusted support principal resolver is required",
                500,
            )
        self._core = CoreAPI(db_path)
        self._principal_resolver = principal_resolver

    @staticmethod
    def _denied() -> CoreError:
        # Deliberately uniform: callers must not learn whether a support token,
        # Core session, user or Case exists.
        return CoreError(
            "SUPPORT_AUTHORIZATION_FAILED",
            "support authorization failed",
            403,
        )

    def _core_session(self, support_session_id: str) -> dict:
        if not isinstance(support_session_id, str) or not support_session_id.strip():
            raise self._denied()

        try:
            resolved = self._principal_resolver(support_session_id.strip())
        except Exception as exc:  # trusted adapter failures still fail closed
            raise self._denied() from exc

        if not isinstance(resolved, Mapping):
            raise self._denied()
        session_id = resolved.get("session_id")
        sic_id = resolved.get("sic_id")
        if (
            not isinstance(session_id, str)
            or not session_id.strip()
            or not isinstance(sic_id, str)
            or not sic_id.strip()
        ):
            # A user_id/SIC-ID pair is intentionally insufficient. A currently
            # live canonical Core session must be presented by the trusted resolver.
            raise self._denied()

        try:
            principal = self._core.resume_session(
                session_id=session_id.strip(),
                sic_id=sic_id.strip(),
            )
        except CoreError as exc:
            raise self._denied() from exc

        # Keep the sensitive principal internal to this trust boundary.
        return {
            "session_id": principal["session_id"],
            "sic_id": principal["sic_id"],
        }

    def case_authorization(self, *, support_session_id: str, case_id: str) -> dict:
        """Return Core's minimal owner verdict for one authenticated support Case.

        External support callers supply neither ``user_id`` nor ``sic_id``. The
        transport-specific resolver supplies an existing Core session reference,
        which is revalidated at request time so revocation/expiry takes effect
        immediately.
        """
        if not isinstance(case_id, str) or not case_id.strip():
            raise self._denied()

        principal = self._core_session(support_session_id)
        try:
            return self._core.support_case_authorization(
                session_id=principal["session_id"],
                sic_id=principal["sic_id"],
                case_id=case_id.strip(),
            )
        except CoreError as exc:
            raise self._denied() from exc
