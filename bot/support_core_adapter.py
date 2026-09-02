"""CHAT07 adapter for canonical Core Case-owner authorization.

This module does not create identity, Case, Evidence, payment, or support truth.
A trusted transport must already possess a live SIC-ID ``session_id`` + ``sic_id``
pair. The adapter asks CHAT01 ``CoreAPI`` for the privacy-minimized Case-owner
verdict, then feeds that verdict into CHAT07's stateless support guards.

Telegram-principal -> SIC-ID session binding remains an infrastructure/runtime
responsibility and is intentionally not inferred here.
"""
from __future__ import annotations

from pathlib import Path

from core.api import CoreAPI
from core.case_engine import CoreError

from .support_mvp import (
    SafeCaseNotification,
    SupportRejected,
    SupportRequest,
    build_case_support_request,
    build_safe_case_notification,
)


class CoreLinkedSupportAdapter:
    """Fail closed on any invalid/expired/cross-user Core authorization result."""

    def __init__(self, db_path: str | Path):
        self._core = CoreAPI(db_path)

    def _owner_verdict(self, *, session_id: str, sic_id: str, case_id: str) -> dict:
        try:
            verdict = self._core.support_case_authorization(
                session_id=session_id,
                sic_id=sic_id,
                case_id=case_id,
            )
        except CoreError as exc:
            # Do not expose whether a Case exists, who owns it, or why auth failed.
            raise SupportRejected("case_support_authorization_failed") from exc
        if verdict.get("requester_is_case_owner") is not True:
            raise SupportRejected("case_support_authorization_failed")
        if verdict.get("case_id") != case_id:
            raise SupportRejected("case_support_authorization_failed")
        return verdict

    def build_request(
        self,
        *,
        session_id: str,
        sic_id: str,
        case_id: str,
        summary: str,
        category: str = "GENERAL",
        escalate: bool = False,
    ) -> SupportRequest:
        verdict = self._owner_verdict(session_id=session_id, sic_id=sic_id, case_id=case_id)
        return build_case_support_request(
            case_id=verdict["case_id"],
            summary=summary,
            category=category,
            requester_is_case_owner=True,
            escalate=escalate,
        )

    def build_notification(
        self,
        *,
        session_id: str,
        sic_id: str,
        case_id: str,
        event_type: str,
    ) -> SafeCaseNotification:
        verdict = self._owner_verdict(session_id=session_id, sic_id=sic_id, case_id=case_id)
        return build_safe_case_notification(
            case_id=verdict["case_id"],
            event_type=event_type,
            case_version=int(verdict["case_version"]),
            requester_is_case_owner=True,
        )
