"""Privacy-minimized Telegram notification sender for CHAT07 MVP support.

This module is transport-only. It may send only a fixed SafeCaseNotification that
was re-authorized against the Telegram principal and canonical Core Case owner by
``TelegramDurableSupportRuntime``. It never carries Evidence, payment details,
SIC-ID values, wallet data or caller-authored free text.

Delivery is claim -> Telegram send -> durable ACK. A send failure is never ACKed.
A process crash after Telegram accepted the message but before ACK can still cause
an at-least-once retry after the lease expires; Telegram sendMessage offers no
server-side idempotency key, so this residual duplicate window is explicit rather
than hidden.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from .telegram_support_transport import (
        TelegramDurableSupportRejected,
        TelegramDurableSupportRuntime,
    )
except ImportError:  # pragma: no cover - direct bot entrypoint compatibility
    from telegram_support_transport import (
        TelegramDurableSupportRejected,
        TelegramDurableSupportRuntime,
    )

TELEGRAM_NOTIFICATION_SENDER_VERSION = "1.0.0"


class TelegramNotificationSendRejected(ValueError):
    """Uniform fail-closed delivery error."""


@dataclass(frozen=True)
class TelegramNotificationDelivery:
    delivery_id: str
    state: str
    attempt_count: int
    sent: bool
    transport_message_id: str | None


def _private_chat_binding(telegram_principal: str, telegram_chat_id: int) -> str:
    if isinstance(telegram_chat_id, bool) or not isinstance(telegram_chat_id, int) or telegram_chat_id <= 0:
        raise TelegramNotificationSendRejected("notification_delivery_failed")
    expected = f"telegram:{telegram_chat_id}"
    if not isinstance(telegram_principal, str) or telegram_principal.strip() != expected:
        raise TelegramNotificationSendRejected("notification_delivery_failed")
    return expected


class TelegramNotificationSender:
    def __init__(self, *, durable_runtime: TelegramDurableSupportRuntime, bot: Any):
        if not isinstance(durable_runtime, TelegramDurableSupportRuntime):
            raise TelegramNotificationSendRejected("notification_delivery_unavailable")
        if bot is None or not callable(getattr(bot, "send_message", None)):
            raise TelegramNotificationSendRejected("notification_delivery_unavailable")
        self.runtime = durable_runtime
        self.bot = bot

    async def deliver(
        self,
        *,
        telegram_principal: str,
        telegram_chat_id: int,
        support_session_id: str,
        case_id: str,
        event_type: str,
        lease_seconds: int = 60,
        now: float | None = None,
    ) -> TelegramNotificationDelivery:
        """Authorize, claim, send and ACK one safe Case notification.

        ``telegram_chat_id`` must be the direct-chat ID matching the already-bound
        principal. Group/channel IDs and confused-deputy principal/chat mismatches
        fail before claim or network I/O.
        """
        principal = _private_chat_binding(telegram_principal, telegram_chat_id)
        try:
            claim, notification = self.runtime.claim_notification_delivery(
                telegram_principal=principal,
                support_session_id=support_session_id,
                case_id=case_id,
                event_type=event_type,
                lease_seconds=lease_seconds,
                now=now,
            )
        except TelegramDurableSupportRejected as exc:
            raise TelegramNotificationSendRejected("notification_delivery_failed") from exc

        if not claim.should_send:
            return TelegramNotificationDelivery(
                delivery_id=claim.delivery_id,
                state=claim.state,
                attempt_count=claim.attempt_count,
                sent=False,
                transport_message_id=None,
            )
        if not claim.claim_token:
            raise TelegramNotificationSendRejected("notification_delivery_failed")

        try:
            sent_message = await self.bot.send_message(
                chat_id=telegram_chat_id,
                text=notification.message,
                disable_web_page_preview=True,
            )
        except Exception as exc:
            # Deliberately do not ACK: the durable lease can be retried later.
            raise TelegramNotificationSendRejected("notification_delivery_failed") from exc

        raw_message_id = getattr(sent_message, "message_id", None)
        if isinstance(raw_message_id, bool) or not isinstance(raw_message_id, int) or raw_message_id <= 0:
            # Telegram acceptance cannot be proven without a message identifier;
            # leave the claim unacknowledged rather than invent delivery truth.
            raise TelegramNotificationSendRejected("notification_delivery_failed")
        transport_message_id = str(raw_message_id)

        try:
            receipt = self.runtime.mark_notification_delivered(
                delivery_id=claim.delivery_id,
                claim_token=claim.claim_token,
                transport_message_id=transport_message_id,
                now=now,
            )
        except TelegramDurableSupportRejected as exc:
            raise TelegramNotificationSendRejected("notification_delivery_failed") from exc
        if receipt.get("state") != "DELIVERED":
            raise TelegramNotificationSendRejected("notification_delivery_failed")

        return TelegramNotificationDelivery(
            delivery_id=claim.delivery_id,
            state="DELIVERED",
            attempt_count=claim.attempt_count,
            sent=True,
            transport_message_id=transport_message_id,
        )


__all__ = [
    "TELEGRAM_NOTIFICATION_SENDER_VERSION",
    "TelegramNotificationDelivery",
    "TelegramNotificationSendRejected",
    "TelegramNotificationSender",
]
