import sqlite3
from pathlib import Path

import pytest

from bot.telegram_private_support import TelegramPrivateSupportRuntime
from bot.telegram_support_transport import TelegramDurableSupportRuntime
from bot.telegram_ticket_commands import (
    TelegramTicketCommandRejected,
    create_case_ticket_command,
)
from core import CaseEngine


def fixture(tmp_path: Path):
    core_db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    binding_db = tmp_path / "private" / "support-binding.sqlite"
    transport_db = tmp_path / "private" / "support-transport.sqlite"
    core = CaseEngine(core_db)
    owner = core.register_user("SIC-TICKET-OWNER", {}, "reg-owner", "req-owner")
    other = core.register_user("SIC-TICKET-OTHER", {}, "reg-other", "req-other")
    owner_session = core.create_session(owner["user_id"], owner["sic_id"], "req-so", "idem-so", 3600)
    other_session = core.create_session(other["user_id"], other["sic_id"], "req-sx", "idem-sx", 3600)
    case = core.open_case(owner["user_id"], owner["sic_id"], None, "project:unknown", False, "USER", "req-case-ticket", "idem-case-ticket")
    private = TelegramPrivateSupportRuntime(binding_db, core_db)
    durable = TelegramDurableSupportRuntime(private_runtime=private, transport_db_path=transport_db)
    return core, private, durable, transport_db, owner, other, owner_session, other_session, case


def bind(private, session, sic_id, principal):
    code = private.store.issue_link_code(core_session_id=session["session_id"], sic_id=sic_id)
    return private.bind(telegram_principal=principal, link_code=code)


def test_ticket_command_is_owner_authorized_minimized_and_idempotent(tmp_path: Path):
    _, private, durable, db, owner, _, session, _, case = fixture(tmp_path)
    principal = "telegram:ticket-owner"
    token = bind(private, session, owner["sic_id"], principal)

    first = create_case_ticket_command(
        durable_runtime=durable,
        telegram_principal=principal,
        support_session_id=token,
        args=[case["case_id"]],
    )
    replay = create_case_ticket_command(
        durable_runtime=durable,
        telegram_principal=principal,
        support_session_id=token,
        args=[case["case_id"]],
    )

    assert first.ticket_id == replay.ticket_id
    assert first.category == "CASE_STATUS" and first.escalate is False
    assert first.idempotent is False and replay.idempotent is True
    with sqlite3.connect(db) as connection:
        row = connection.execute("SELECT case_id, category, summary, escalate FROM support_tickets").fetchone()
    assert row == (case["case_id"], "CASE_STATUS", "Telegram Case support request", 0)
    raw = db.read_bytes().lower()
    assert b"evidence" not in raw
    assert principal.encode() not in raw


def test_escalate_command_uses_fixed_minimized_payload(tmp_path: Path):
    _, private, durable, db, owner, _, session, _, case = fixture(tmp_path)
    principal = "telegram:ticket-escalate"
    token = bind(private, session, owner["sic_id"], principal)
    receipt = create_case_ticket_command(
        durable_runtime=durable,
        telegram_principal=principal,
        support_session_id=token,
        args=[case["case_id"]],
        escalate=True,
    )
    assert receipt.category == "ESCALATION" and receipt.escalate is True
    with sqlite3.connect(db) as connection:
        row = connection.execute("SELECT summary, escalate FROM support_tickets").fetchone()
    assert row == ("Telegram Case escalation request", 1)


def test_free_text_or_missing_case_is_rejected_before_persistence(tmp_path: Path):
    _, private, durable, db, owner, _, session, _, case = fixture(tmp_path)
    principal = "telegram:ticket-minimize"
    token = bind(private, session, owner["sic_id"], principal)
    with pytest.raises(TelegramTicketCommandRejected):
        create_case_ticket_command(
            durable_runtime=durable,
            telegram_principal=principal,
            support_session_id=token,
            args=[case["case_id"], "my seed phrase is alpha beta gamma"],
        )
    with pytest.raises(TelegramTicketCommandRejected):
        create_case_ticket_command(
            durable_runtime=durable,
            telegram_principal=principal,
            support_session_id=token,
            args=[],
        )
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM support_tickets").fetchone()[0] == 0


def test_cross_user_and_revoked_session_fail_closed(tmp_path: Path):
    core, private, durable, db, owner, other, owner_session, other_session, case = fixture(tmp_path)
    other_principal = "telegram:ticket-other"
    other_token = bind(private, other_session, other["sic_id"], other_principal)
    with pytest.raises(TelegramTicketCommandRejected):
        create_case_ticket_command(
            durable_runtime=durable,
            telegram_principal=other_principal,
            support_session_id=other_token,
            args=[case["case_id"]],
        )

    owner_principal = "telegram:ticket-revoked"
    owner_token = bind(private, owner_session, owner["sic_id"], owner_principal)
    core.revoke_session(owner_session["session_id"], owner["user_id"])
    with pytest.raises(TelegramTicketCommandRejected):
        create_case_ticket_command(
            durable_runtime=durable,
            telegram_principal=owner_principal,
            support_session_id=owner_token,
            args=[case["case_id"]],
        )
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM support_tickets").fetchone()[0] == 0
