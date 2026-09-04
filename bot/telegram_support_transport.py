"""CHAT07 authorized durable ticket/notification composition.

The private Telegram/Core bridge remains the authorization authority. This
wrapper only persists commands after re-authorizing the Telegram principal via
``TelegramPrivateSupportRuntime.case_status``. No private Evidence payload is
accepted or produced.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# Support both package imports used by pytest (``bot.*``) and direct
# ``python bot/main.py`` execution, without loading duplicate class identities.
try:
    from .support_mvp import (
        SafeCaseNotification,
        SupportRejected,
        build_case_support_request,
        build_safe_case_notification,
    )
    from .support_transport import (
        NotificationClaim,
        SupportTransportRejected,
        SupportTransportStore,
        TicketReceipt,
    )
    from .telegram_private_support import (
        TelegramPrivateSupportRejected,
        TelegramPrivateSupportRuntime,
    )
except ImportError:  # pragma: no cover - exercised by direct bot entrypoint smoke
    from support_mvp import (
        SafeCaseNotification,
        SupportRejected,
        build_case_support_request,
        build_safe_case_notification,
    )
    from support_transport import (
        NotificationClaim,
        SupportTransportRejected,
        SupportTransportStore,
        TicketReceipt,
    )
    from telegram_private_support import (
        TelegramPrivateSupportRejected,
        TelegramPrivateSupportRuntime,
    )

TELEGRAM_DURABLE_SUPPORT_VERSION = "1.1.0"


class TelegramDurableSupportRejected(ValueError):
    """Uniform failure for private durable support without existence leakage."""


class TelegramDurableSupportRuntime:
    def __init__(self, *, private_runtime: TelegramPrivateSupportRuntime, transport_db_path: str | Path):
        if not isinstance(private_runtime, TelegramPrivateSupportRuntime):
            raise TelegramDurableSupportRejected("durable_support_unavailable")
        self.private_runtime = private_runtime
        try:
            self.transport = SupportTransportStore(transport_db_path)
        except SupportTransportRejected as exc:
            raise TelegramDurableSupportRejected("durable_support_unavailable") from exc

    def _owner_verdict(self, *, telegram_principal: str, support_session_id: str, case_id: str) -> dict[str, Any]:
        try:
            return self.private_runtime.case_status(
                telegram_principal=telegram_principal,
                support_session_id=support_session_id,
                case_id=case_id,
            )
        except TelegramPrivateSupportRejected as exc:
            raise TelegramDurableSupportRejected("durable_support_failed") from exc

    def create_ticket(
        self,
        *,
        telegram_principal: str,
        support_session_id: str,
        case_id: str,
        summary: str,
        category: str = "GENERAL",
        escalate: bool = False,
    ) -> TicketReceipt:
        verdict = self._owner_verdict(
            telegram_principal=telegram_principal,
            support_session_id=support_session_id,
            case_id=case_id,
        )
        try:
            request = build_case_support_request(
                case_id=verdict["case_id"],
                summary=summary,
                category=category,
                requester_is_case_owner=verdict["requester_is_case_owner"],
                escalate=escalate,
            )
            return self.transport.create_ticket(
                request=request,
                telegram_principal=telegram_principal,
            )
        except (SupportRejected, SupportTransportRejected) as exc:
            raise TelegramDurableSupportRejected("durable_support_failed") from exc

    def claim_notification_delivery(
        self,
        *,
        telegram_principal: str,
        support_session_id: str,
        case_id: str,
        event_type: str,
        lease_seconds: int = 60,
        now: float | None = None,
    ) -> tuple[NotificationClaim, SafeCaseNotification]:
        """Authorize and claim one privacy-minimized notification atomically enough for transport.

        The returned message is generated from the canonical Core owner verdict and
        the fixed safe notification catalog. It contains no private Evidence or
        caller-supplied free-form Case text. External delivery still requires an
        explicit sender followed by ``mark_notification_delivered``.
        """
        verdict = self._owner_verdict(
            telegram_principal=telegram_principal,
            support_session_id=support_session_id,
            case_id=case_id,
        )
        try:
            notification = build_safe_case_notification(
                case_id=verdict["case_id"],
                event_type=event_type,
                case_version=int(verdict["case_version"]),
                requester_is_case_owner=verdict["requester_is_case_owner"],
            )
            claim = self.transport.claim_notification(
                notification=notification,
                telegram_principal=telegram_principal,
                lease_seconds=lease_seconds,
                now=now,
            )
            return claim, notification
        except (SupportRejected, SupportTransportRejected, TypeError, ValueError) as exc:
            raise TelegramDurableSupportRejected("durable_support_failed") from exc

    def claim_notification(
        self,
        *,
        telegram_principal: str,
        support_session_id: str,
        case_id: str,
        event_type: str,
        lease_seconds: int = 60,
        now: float | None = None,
    ) -> NotificationClaim:
        claim, _ = self.claim_notification_delivery(
            telegram_principal=telegram_principal,
            support_session_id=support_session_id,
            case_id=case_id,
            event_type=event_type,
            lease_seconds=lease_seconds,
            now=now,
        )
        return claim

    def mark_notification_delivered(
        self,
        *,
        delivery_id: str,
        claim_token: str,
        transport_message_id: str,
        now: float | None = None,
    ) -> dict[str, Any]:
        try:
            return self.transport.mark_notification_delivered(
                delivery_id=delivery_id,
                claim_token=claim_token,
                transport_message_id=transport_message_id,
                now=now,
            )
        except SupportTransportRejected as exc:
            raise TelegramDurableSupportRejected("durable_support_failed") from exc


__all__ = [
    "TELEGRAM_DURABLE_SUPPORT_VERSION",
    "TelegramDurableSupportRejected",
    "TelegramDurableSupportRuntime",
]
