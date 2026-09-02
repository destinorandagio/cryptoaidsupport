"""Authenticated CHAT01 user/Case API facade for the CryptoAID MVP.

``CaseEngine`` remains the authoritative internal service. External user-facing
routes should use this facade so the authenticated subject is derived from a
live SIC-ID session rather than accepted as a caller-supplied ``user_id``.

Session creation itself remains the responsibility of the trusted SIC-ID/auth
adapter. This module deliberately does not create a second identity authority.
"""
from __future__ import annotations

from pathlib import Path

from .case_engine import CoreError
from .case_engine_mvp import CaseEngine

CORE_API_FACADE_VERSION = "1.2.0"


class CoreAPI:
    """Fail-closed authenticated facade over CHAT01 Case truth."""

    def __init__(self, db_path: str | Path):
        self.engine = CaseEngine(db_path)

    @staticmethod
    def _required(value: str, code: str, message: str, status: int = 401) -> str:
        if not value or not value.strip():
            raise CoreError(code, message, status)
        return value.strip()

    @classmethod
    def _mutation_meta(cls, request_id: str, idempotency_key: str) -> tuple[str, str]:
        """Require attributable and replay-safe metadata before any user mutation."""
        return (
            cls._required(request_id, "REQUEST_ID_REQUIRED", "request_id is required", 400),
            cls._required(
                idempotency_key,
                "IDEMPOTENCY_KEY_REQUIRED",
                "idempotency_key is required",
                400,
            ),
        )

    def _principal(self, session_id: str, sic_id: str) -> dict:
        session_id = self._required(session_id, "SESSION_REQUIRED", "active session is required")
        sic_id = self._required(sic_id, "SIC_ID_REQUIRED", "SIC-ID is required")
        return self.engine.resume_session(session_id, sic_id)

    def resume_session(self, *, session_id: str, sic_id: str) -> dict:
        return self._principal(session_id, sic_id)

    def revoke_session(self, *, session_id: str, sic_id: str) -> dict:
        principal = self._principal(session_id, sic_id)
        return self.engine.revoke_session(session_id, principal["user_id"])

    def bind_wallet(
        self,
        *,
        session_id: str,
        sic_id: str,
        wallet: str,
        request_id: str,
        idempotency_key: str,
    ) -> dict:
        principal = self._principal(session_id, sic_id)
        request_id, idempotency_key = self._mutation_meta(request_id, idempotency_key)
        return self.engine.bind_wallet(
            principal["user_id"],
            principal["sic_id"],
            wallet,
            request_id,
            idempotency_key,
        )

    def create_case(
        self,
        *,
        session_id: str,
        sic_id: str,
        wallet: str | None,
        project_ref: str | None,
        search_hit: bool,
        request_id: str,
        idempotency_key: str,
    ) -> dict:
        principal = self._principal(session_id, sic_id)
        request_id, idempotency_key = self._mutation_meta(request_id, idempotency_key)
        return self.engine.open_case(
            principal["user_id"],
            principal["sic_id"],
            wallet,
            project_ref,
            search_hit,
            "USER",
            request_id,
            idempotency_key,
        )

    def resume_case(self, *, session_id: str, sic_id: str, case_id: str) -> dict:
        principal = self._principal(session_id, sic_id)
        return self.engine.get_case(case_id, principal["user_id"])

    def transition_case(
        self,
        *,
        session_id: str,
        sic_id: str,
        case_id: str,
        new_state: str,
        reason: str,
        request_id: str,
        idempotency_key: str,
        expected_version: int,
    ) -> dict:
        """Apply a user command without accepting privileged authorization claims.

        Paid activation remains possible only through a trusted internal/system
        call after CHAT02 has persisted its settlement/entitlement effect. A
        user-facing request cannot submit ``ENTITLEMENT_GRANTED`` or
        ``FREE_PRODUCT_AUTHORIZED`` through this facade.
        """
        principal = self._principal(session_id, sic_id)
        request_id, idempotency_key = self._mutation_meta(request_id, idempotency_key)
        reason = self._required(reason, "REASON_REQUIRED", "transition reason is required", 400)
        return self.engine.transition(
            case_id=case_id,
            user_id=principal["user_id"],
            new_state=new_state,
            actor="USER",
            reason=reason,
            request_id=request_id,
            idempotency_key=idempotency_key,
            authorization="OWNER",
            expected_version=expected_version,
        )

    def select_product(
        self,
        *,
        session_id: str,
        sic_id: str,
        case_id: str,
        product_code: str,
        request_id: str,
        idempotency_key: str,
        expected_version: int,
    ) -> dict:
        """Select a Case product as an audited optimistic-concurrency mutation.

        Product choice is part of the payment contract. It therefore cannot be a
        silent last-write-wins field update: the request is bound to the live
        principal, Case, product and expected Case version, and the engine locks
        selection once Evidence/payment processing has begun.
        """
        principal = self._principal(session_id, sic_id)
        request_id, idempotency_key = self._mutation_meta(request_id, idempotency_key)
        return self.engine.select_product(
            case_id,
            principal["user_id"],
            product_code,
            request_id,
            idempotency_key,
            expected_version,
        )

    def timeline(self, *, session_id: str, sic_id: str, case_id: str) -> list[dict]:
        principal = self._principal(session_id, sic_id)
        return self.engine.timeline(case_id, principal["user_id"])

    def support_case_authorization(
        self,
        *,
        session_id: str,
        sic_id: str,
        case_id: str,
    ) -> dict:
        """Return the canonical, privacy-minimized Case-owner verdict for support.

        CHAT07/CHAT10 support transports must not decide Case ownership themselves.
        They may consume this result only after the user presents a live SIC-ID
        session. Cross-user lookups intentionally fail as ``CASE_NOT_FOUND`` to
        avoid Case enumeration. No Evidence, wallet, payment data, SIC-ID, user ID,
        or free-form Case content is exposed by this projection.
        """
        principal = self._principal(session_id, sic_id)
        case = self.engine.get_case(case_id, principal["user_id"])
        return {
            "case_id": case["case_id"],
            "requester_is_case_owner": True,
            "case_state": case["state"],
            "case_version": int(case["version"]),
        }

    def next_action(self, *, session_id: str, sic_id: str, case_id: str) -> dict | None:
        """Return one open Next Action for My Recovery, oldest first."""
        principal = self._principal(session_id, sic_id)
        self.engine.get_case(case_id, principal["user_id"])
        with self.engine.conn() as conn:
            row = conn.execute(
                "SELECT task_id,case_id,title,status,next_action,created_at,updated_at "
                "FROM core_case_tasks WHERE case_id=? AND status='OPEN' "
                "ORDER BY created_at,task_id LIMIT 1",
                (case_id,),
            ).fetchone()
        return dict(row) if row else None
