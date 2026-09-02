"""CHAT07 private Telegram support runtime bridge.

This module is transport glue only. It does not mint SIC-ID, Case ownership,
Evidence, payment, entitlement, or Knowledge truth. A Telegram principal first
consumes a short-lived DApp link through :class:`SupportBindingStore`; every
private Case lookup is then re-authorized by ``core.TrustedSupportAPI`` against
the canonical LIVE Core session and Case owner.

The opaque support-session token returned by ``bind`` is intended to remain in
process/session memory (for example python-telegram-bot ``context.user_data``),
not Telegram messages or persistent public storage. Durable ticket/notification
receipts are a separate transport concern and are deliberately not invented
here.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core import CoreError, TrustedSupportAPI
from bot.support_binding import SupportBindingRejected, SupportBindingStore

TELEGRAM_PRIVATE_SUPPORT_VERSION = "1.0.0"


class TelegramPrivateSupportRejected(ValueError):
    """Uniform fail-closed rejection without Case/session existence leakage."""


def _clean(value: str, *, max_len: int = 256) -> str:
    if not isinstance(value, str):
        raise TelegramPrivateSupportRejected("private_support_failed")
    value = value.strip()
    if not value or len(value) > max_len:
        raise TelegramPrivateSupportRejected("private_support_failed")
    return value


class TelegramPrivateSupportRuntime:
    """Authenticated Telegram principal -> canonical Core Case-owner bridge."""

    def __init__(self, binding_db_path: str | Path, core_db_path: str | Path):
        self.binding_db_path = Path(binding_db_path)
        self.core_db_path = Path(core_db_path)
        self.store = SupportBindingStore(self.binding_db_path, self.core_db_path)

    @classmethod
    def from_env(cls) -> "TelegramPrivateSupportRuntime":
        binding_db = os.getenv("CRYPTOAID_SUPPORT_BINDING_DB", "").strip()
        core_db = os.getenv("CRYPTOAID_CORE_DB", "").strip()
        if not binding_db or not core_db:
            raise TelegramPrivateSupportRejected("private_support_unavailable")
        try:
            return cls(binding_db, core_db)
        except (OSError, ValueError, SupportBindingRejected) as exc:
            raise TelegramPrivateSupportRejected("private_support_unavailable") from exc

    def bind(self, *, telegram_principal: str, link_code: str) -> str:
        """Consume one DApp-issued link and return an opaque in-memory token."""
        principal = _clean(telegram_principal, max_len=128)
        code = _clean(link_code, max_len=128)
        try:
            return self.store.consume_link_code(
                telegram_principal=principal,
                link_code=code,
            )
        except SupportBindingRejected as exc:
            raise TelegramPrivateSupportRejected("private_support_failed") from exc

    def case_status(
        self,
        *,
        telegram_principal: str,
        support_session_id: str,
        case_id: str,
    ) -> dict[str, Any]:
        """Return only Core's privacy-minimized owner verdict/state projection."""
        principal = _clean(telegram_principal, max_len=128)
        token = _clean(support_session_id)
        case = _clean(case_id, max_len=128)
        resolver = self.store.resolver_for_principal(principal)
        api = TrustedSupportAPI(self.core_db_path, resolver)
        try:
            verdict = api.case_authorization(
                support_session_id=token,
                case_id=case,
            )
        except (CoreError, SupportBindingRejected) as exc:
            raise TelegramPrivateSupportRejected("private_support_failed") from exc
        if verdict.get("requester_is_case_owner") is not True:
            raise TelegramPrivateSupportRejected("private_support_failed")
        allowed = {"case_id", "requester_is_case_owner", "case_state", "case_version"}
        if set(verdict) != allowed:
            raise TelegramPrivateSupportRejected("private_support_failed")
        return {key: verdict[key] for key in ("case_id", "requester_is_case_owner", "case_state", "case_version")}
