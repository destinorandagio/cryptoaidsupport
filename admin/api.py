"""Authenticated CHAT08 Admin/CRM API facade for the CryptoAID MVP.

The lower-level :class:`AdminOps` object intentionally accepts a role collection
because it is also used by trusted internal tests/composition.  External Admin
routes should use this facade instead: callers provide only an opaque admin
session identifier, while actor identity and roles are resolved by a trusted
admin-auth adapter injected by the runtime.

No admin identity database or parallel authority is created here.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from .ops import ADMIN_ROLE, AdminError, AdminOps

ADMIN_API_FACADE_VERSION = "1.0.0"
AdminSessionResolver = Callable[[str], Mapping[str, Any]]


class AdminAPI:
    """Fail-closed authenticated facade over CHAT08 minimum Admin operations."""

    def __init__(self, db_path: str | Path, session_resolver: AdminSessionResolver):
        if not callable(session_resolver):
            raise AdminError(
                "ADMIN_SESSION_RESOLVER_REQUIRED",
                "trusted admin session resolver is required",
                500,
            )
        self.ops = AdminOps(db_path)
        self._session_resolver = session_resolver

    def _principal(self, admin_session_id: str) -> tuple[str, tuple[str, ...]]:
        if not admin_session_id or not admin_session_id.strip():
            raise AdminError("ADMIN_SESSION_REQUIRED", "admin session is required", 401)
        try:
            resolved = self._session_resolver(admin_session_id.strip())
        except Exception as exc:  # auth adapters must fail closed, without leaking details
            raise AdminError("ADMIN_SESSION_INVALID", "admin session is invalid", 401) from exc
        if not isinstance(resolved, Mapping):
            raise AdminError("ADMIN_SESSION_INVALID", "admin session is invalid", 401)

        actor = str(resolved.get("actor") or "").strip()
        raw_roles = resolved.get("roles")
        if not actor:
            raise AdminError("ADMIN_SESSION_INVALID", "admin actor is missing", 401)
        if isinstance(raw_roles, str):
            roles: tuple[str, ...] = (raw_roles,)
        elif isinstance(raw_roles, Iterable):
            roles = tuple(str(role) for role in raw_roles)
        else:
            roles = ()
        if ADMIN_ROLE not in roles:
            raise AdminError("ADMIN_FORBIDDEN", "Admin case-review role required", 403)
        return actor, roles

    def case_queue(
        self, *, admin_session_id: str, state: str | None = None, limit: int = 100
    ) -> list[dict]:
        _, roles = self._principal(admin_session_id)
        return self.ops.case_queue(roles=roles, state=state, limit=limit)

    def case_summary(self, *, admin_session_id: str, case_id: str) -> dict:
        _, roles = self._principal(admin_session_id)
        return self.ops.case_summary(roles=roles, case_id=case_id)

    def user_lookup(
        self,
        *,
        admin_session_id: str,
        sic_id: str | None = None,
        case_id: str | None = None,
    ) -> dict:
        _, roles = self._principal(admin_session_id)
        return self.ops.user_lookup(roles=roles, sic_id=sic_id, case_id=case_id)

    def crm_timeline(
        self, *, admin_session_id: str, sic_id: str, limit: int = 100
    ) -> list[dict]:
        _, roles = self._principal(admin_session_id)
        return self.ops.crm_timeline(roles=roles, sic_id=sic_id, limit=limit)

    def manual_review_queue(
        self, *, admin_session_id: str, limit: int = 100
    ) -> list[dict]:
        _, roles = self._principal(admin_session_id)
        return self.ops.manual_review_queue(roles=roles, limit=limit)

    def transition_case(
        self,
        *,
        admin_session_id: str,
        case_id: str,
        new_state: str,
        reason: str,
        request_id: str,
        idempotency_key: str,
        expected_version: int,
    ) -> dict:
        actor, roles = self._principal(admin_session_id)
        return self.ops.transition_case(
            roles=roles,
            case_id=case_id,
            new_state=new_state,
            actor=actor,
            reason=reason,
            request_id=request_id,
            idempotency_key=idempotency_key,
            expected_version=expected_version,
        )
