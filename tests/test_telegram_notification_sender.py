import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from bot.telegram_notification_sender import (
    TelegramNotificationSendRejected,
    TelegramNotificationSender,
)
from bot.telegram_private_support import TelegramPrivateSupportRuntime
from bot.telegram_support_transport import TelegramDurableSupportRuntime
from core import CaseEngine


class FakeBot:
    def __init__(self, *, fail: bool = False, message_id: int | None = 42):
        self.fail = fail
        self.message_id = message_id
        self.calls = []

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("synthetic telegram failure")
        return SimpleNamespace(message_id=self.message_id)


def fixture(tmp_path: Path):
    core_db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    binding_db = tmp_path / "private" / "support-binding.sqlite"
    transport_db = tmp_path / "private" / "support-transport.sqlite"
    core = CaseEngine(core_db)
    owner = core.register_user("SIC-NOTIFY-OWNER", {}, "reg-owner", "req-owner")
    other = core.register_user("SIC-NOTIFY-OTHER", {}, "reg-other", "req-other")
    owner_session = core.create_session(owner["user_id"], owner["sic_id"], "req-so", "idem-so", 3600)
    other_session = core.create_session(other["user_id"], other["sic_id"], "req-sx", "idem-sx", 3600)
    case = core.open_case(
        owner["user_id"],
        owner["sic_id"],
        None,
        "project:notify",
        False,
        "USER",
        "req-case-notify",
        "idem-case-notify",
    )
    private = TelegramPrivateSupportRuntime(binding_db, core_db)
    durable = TelegramDurableSupportRuntime(
        private_runtime=private,
        transport_db_path=transport_db,
    )
    return core, private, durable, transport_db, owner, other, owner_session, other_session, case


def bind(private, session, sic_id, principal):
    code = private.store.issue_link_code(core_session_id=session["session_id"], sic_id=sic_id)
    return private.bind(telegram_principal=principal, link_code=code)


@pytest.mark.asyncio
async def test_authorized_notification_claim_send_ack_and_replay_dedupe(tmp_path: Path):
    _, private, durable, db, owner, _, session, _, case = fixture(tmp_path)
    chat_id = 1001
    principal = f"telegram:{chat_id}"
    token = bind(private, session, owner["sic_id"], principal)
    bot = FakeBot(message_id=77)
    sender = TelegramNotificationSender(durable_runtime=durable, bot=bot)

    first = await sender.deliver(
        telegram_principal=principal,
        telegram_chat_id=chat_id,
        support_session_id=token,
        case_id=case["case_id"],
        event_type="STATUS_CHANGED",
        now=1000.0,
    )
    second = await sender.deliver(
        telegram_principal=principal,
        telegram_chat_id=chat_id,
        support_session_id=token,
        case_id=case["case_id"],
        event_type="STATUS_CHANGED",
        now=1001.0,
    )

    assert first.sent is True and first.state == "DELIVERED" and first.transport_message_id == "77"
    assert second.sent is False and second.state == "DELIVERED"
    assert len(bot.calls) == 1
    assert bot.calls[0]["chat_id"] == chat_id
    assert case["case_id"] not in bot.calls[0]["text"]
    assert "Evidence" not in bot.calls[0]["text"]
    with sqlite3.connect(db) as connection:
        row = connection.execute(
            "SELECT state,attempt_count,transport_message_id FROM notification_deliveries"
        ).fetchone()
    assert row == ("DELIVERED", 1, "77")


@pytest.mark.asyncio
async def test_principal_chat_confused_deputy_rejected_before_claim_or_send(tmp_path: Path):
    _, private, durable, db, owner, _, session, _, case = fixture(tmp_path)
    token = bind(private, session, owner["sic_id"], "telegram:1001")
    bot = FakeBot()
    sender = TelegramNotificationSender(durable_runtime=durable, bot=bot)

    with pytest.raises(TelegramNotificationSendRejected):
        await sender.deliver(
            telegram_principal="telegram:1001",
            telegram_chat_id=2002,
            support_session_id=token,
            case_id=case["case_id"],
            event_type="ACTION_REQUIRED",
        )

    assert bot.calls == []
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM notification_deliveries").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_cross_user_fails_before_network_and_persistence(tmp_path: Path):
    _, private, durable, db, _, other, _, other_session, case = fixture(tmp_path)
    chat_id = 2002
    principal = f"telegram:{chat_id}"
    token = bind(private, other_session, other["sic_id"], principal)
    bot = FakeBot()
    sender = TelegramNotificationSender(durable_runtime=durable, bot=bot)

    with pytest.raises(TelegramNotificationSendRejected):
        await sender.deliver(
            telegram_principal=principal,
            telegram_chat_id=chat_id,
            support_session_id=token,
            case_id=case["case_id"],
            event_type="STATUS_CHANGED",
        )

    assert bot.calls == []
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM notification_deliveries").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_send_failure_is_not_acked_and_retries_only_after_lease(tmp_path: Path):
    _, private, durable, db, owner, _, session, _, case = fixture(tmp_path)
    chat_id = 3003
    principal = f"telegram:{chat_id}"
    token = bind(private, session, owner["sic_id"], principal)
    failing = FakeBot(fail=True)
    sender = TelegramNotificationSender(durable_runtime=durable, bot=failing)

    with pytest.raises(TelegramNotificationSendRejected):
        await sender.deliver(
            telegram_principal=principal,
            telegram_chat_id=chat_id,
            support_session_id=token,
            case_id=case["case_id"],
            event_type="MANUAL_REVIEW",
            lease_seconds=10,
            now=100.0,
        )

    with sqlite3.connect(db) as connection:
        row = connection.execute(
            "SELECT state,attempt_count,transport_message_id FROM notification_deliveries"
        ).fetchone()
    assert row == ("CLAIMED", 1, None)

    holding = FakeBot(message_id=88)
    retry_sender = TelegramNotificationSender(durable_runtime=durable, bot=holding)
    within_lease = await retry_sender.deliver(
        telegram_principal=principal,
        telegram_chat_id=chat_id,
        support_session_id=token,
        case_id=case["case_id"],
        event_type="MANUAL_REVIEW",
        lease_seconds=10,
        now=105.0,
    )
    assert within_lease.sent is False and holding.calls == []

    after_lease = await retry_sender.deliver(
        telegram_principal=principal,
        telegram_chat_id=chat_id,
        support_session_id=token,
        case_id=case["case_id"],
        event_type="MANUAL_REVIEW",
        lease_seconds=10,
        now=111.0,
    )
    assert after_lease.sent is True and after_lease.attempt_count == 2
    assert len(holding.calls) == 1


@pytest.mark.asyncio
async def test_missing_telegram_message_id_is_never_acked(tmp_path: Path):
    _, private, durable, db, owner, _, session, _, case = fixture(tmp_path)
    chat_id = 4004
    principal = f"telegram:{chat_id}"
    token = bind(private, session, owner["sic_id"], principal)
    sender = TelegramNotificationSender(durable_runtime=durable, bot=FakeBot(message_id=None))

    with pytest.raises(TelegramNotificationSendRejected):
        await sender.deliver(
            telegram_principal=principal,
            telegram_chat_id=chat_id,
            support_session_id=token,
            case_id=case["case_id"],
            event_type="ACTION_REQUIRED",
            now=200.0,
        )

    with sqlite3.connect(db) as connection:
        row = connection.execute("SELECT state,transport_message_id FROM notification_deliveries").fetchone()
    assert row == ("CLAIMED", None)
