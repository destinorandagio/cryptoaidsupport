"""CHAT07 minimum durable Case-ticket command facade.

This module is deliberately transport-only. It consumes an already linked private
Telegram support session and delegates every authorization decision to
``TelegramDurableSupportRuntime`` -> canonical Core. It accepts no free-form user
text and carries no private Evidence, wallet or payment payload.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from bot.telegram_support_transport import (
    TelegramDurableSupportRejected,
    TelegramDurableSupportRuntime,
)

TELEGRAM_TICKET_COMMAND_VERSION = "1.0.0"


class TelegramTicketCommandRejected(ValueError):
    """Uniform fail-closed command rejection without Case existence leakage."""


@dataclass(frozen=True)
class TicketCommandReceipt:
    ticket_id: str
    case_id: str
    category: str
    escalate: bool
    idempotent: bool


_FIXED_SUMMARY = {
    False: "Telegram Case support request",
    True: "Telegram Case escalation request",
}
_FIXED_CATEGORY = {
    False: "CASE_STATUS",
    True: "ESCALATION",
}


def create_case_ticket_command(
    *,
    durable_runtime: TelegramDurableSupportRuntime,
    telegram_principal: str,
    support_session_id: str,
    args: Sequence[str],
    escalate: bool = False,
) -> TicketCommandReceipt:
    """Create a minimum Case-linked ticket after canonical owner re-authorization.

    The public Telegram command contract is intentionally only ``<Case ID>``. Any
    extra argument is rejected instead of persisting arbitrary Telegram text. The
    durable runtime revalidates the principal/session/Case ownership before writing.
    """
    if not isinstance(durable_runtime, TelegramDurableSupportRuntime):
        raise TelegramTicketCommandRejected("ticket_support_unavailable")
    if not isinstance(args, Sequence) or isinstance(args, (str, bytes)) or len(args) != 1:
        raise TelegramTicketCommandRejected("ticket_usage_invalid")
    case_id = args[0]
    if not isinstance(case_id, str) or not case_id.strip() or len(case_id.strip()) > 128:
        raise TelegramTicketCommandRejected("ticket_usage_invalid")
    try:
        receipt = durable_runtime.create_ticket(
            telegram_principal=telegram_principal,
            support_session_id=support_session_id,
            case_id=case_id.strip(),
            summary=_FIXED_SUMMARY[bool(escalate)],
            category=_FIXED_CATEGORY[bool(escalate)],
            escalate=bool(escalate),
        )
    except TelegramDurableSupportRejected as exc:
        raise TelegramTicketCommandRejected("ticket_support_failed") from exc
    return TicketCommandReceipt(
        ticket_id=receipt.ticket_id,
        case_id=receipt.case_id,
        category=receipt.category,
        escalate=receipt.escalate,
        idempotent=receipt.idempotent,
    )


__all__ = [
    "TELEGRAM_TICKET_COMMAND_VERSION",
    "TelegramTicketCommandRejected",
    "TicketCommandReceipt",
    "create_case_ticket_command",
]
