import asyncio
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from bot.core_event_dispatcher import (
    CoreEventNotificationDispatcher,
    EphemeralNotificationRouteRegistry,
)
from bot.telegram_notification_sender import TelegramNotificationSender
from bot.telegram_private_support import TelegramPrivateSupportRuntime
from bot.telegram_support_transport import TelegramDurableSupportRuntime
from core import CaseEngine


class FakeBot:
    def __init__(self):
        self.calls = []
        self._next_message_id = 100

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)
        self._next_message_id += 1
        return SimpleNamespace(message_id=self._next_message_id)


def fixture(tmp_path: Path):
    core_db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    binding_db = tmp_path / "private" / "support-binding.sqlite"
    transport_db = tmp_path / "private" / "support-transport.sqlite"
    core = CaseEngine(core_db)

    owner = core.register_user("SIC-DISPATCH-OWNER", {}, "reg-owner", "req-owner")
    other = core.register_user("SIC-DISPATCH-OTHER", {}, "reg-other", "req-other")
    owner_session = core.create_session(
        owner["user_id"], owner["sic_id"], "req-owner-session", "idem-owner-session", 3600
    )
    other_session = core.create_session(
        other["user_id"], other["sic_id"], "req-other-session", "idem-other-session", 3600
    )
    case = core.open_case(
        owner["user_id"],
        owner["sic_id"],
        None,
        "project:dispatcher",
        False,
        "USER",
        "req-case",
        "idem-case",
    )

    private = TelegramPrivateSupportRuntime(binding_db, core_db)
    durable = TelegramDurableSupportRuntime(
        private_runtime=private,
        transport_db_path=transport_db,
    )
    return (
        core_db,
        binding_db,
        transport_db,
        core,
        private,
        durable,
        owner,
        other,
        owner_session,
        other_session,
        case,
    )


def bind(private, session, sic_id: str, principal: str) -> str:
    code = private.store.issue_link_code(
        core_session_id=session["session_id"],
        sic_id=sic_id,
    )
    return private.bind(telegram_principal=principal, link_code=code)


def activate_free_case(core: CaseEngine, case: dict, owner: dict) -> dict:
    state = core.transition(
        case["case_id"],
        owner["user_id"],
        "TRIAGE",
        "USER",
        "triage",
        "dispatch-r1",
        "dispatch-i1",
        "OWNER",
        1,
    )
    state = core.transition(
        case["case_id"],
        owner["user_id"],
        "PRODUCT_SELECTED",
        "USER",
        "free product selected",
        "dispatch-r2",
        "dispatch-i2",
        "OWNER",
        state["version"],
    )
    return core.transition(
        case["case_id"],
        owner["user_id"],
        "ACTIVE",
        "SYSTEM",
        "free product authorized",
        "dispatch-r3",
        "dispatch-i3",
        "FREE_PRODUCT_AUTHORIZED",
        state["version"],
    )


def test_only_canonical_active_event_is_ingested_and_delivered_once(tmp_path: Path):
    (
        core_db,
        _,
        transport_db,
        core,
        private,
        durable,
        owner,
        _,
        owner_session,
        _,
        case,
    ) = fixture(tmp_path)
    dispatcher = CoreEventNotificationDispatcher(
        core_db_path=core_db,
        durable_runtime=durable,
    )
    routes = EphemeralNotificationRouteRegistry()

    state = core.transition(
        case["case_id"], owner["user_id"], "TRIAGE", "USER", "triage",
        "pre-r1", "pre-i1", "OWNER", 1,
    )
    core.transition(
        case["case_id"], owner["user_id"], "PRODUCT_SELECTED", "USER",
        "free product selected", "pre-r2", "pre-i2", "OWNER", state["version"],
    )
    assert dispatcher.ingest() == 0
    assert dispatcher.pending() == ()

    current = core.get_case(case["case_id"], owner["user_id"])
    active = core.transition(
        case["case_id"], owner["user_id"], "ACTIVE", "SYSTEM",
        "free product authorized", "pre-r3", "pre-i3", "FREE_PRODUCT_AUTHORIZED",
        current["version"],
    )
    chat_id = 51001
    principal = f"telegram:{chat_id}"
    token = bind(private, owner_session, owner["sic_id"], principal)
    routes.register(
        telegram_principal=principal,
        telegram_chat_id=chat_id,
        support_session_id=token,
    )
    bot = FakeBot()
    sender = TelegramNotificationSender(durable_runtime=durable, bot=bot)

    first = asyncio.run(dispatcher.dispatch_once(sender=sender, routes=routes))
    second = asyncio.run(dispatcher.dispatch_once(sender=sender, routes=routes))

    assert active["state"] == "ACTIVE"
    assert first.ingested_events == 1
    assert first.delivered_events == 1
    assert second.ingested_events == 0
    assert second.delivered_events == 0
    assert len(bot.calls) == 1
    assert bot.calls[0]["chat_id"] == chat_id
    assert bot.calls[0]["text"] == (
        "Your CryptoAID Case status changed. Open the official app to view the current status."
    )
    assert case["case_id"] not in bot.calls[0]["text"]
    with sqlite3.connect(transport_db) as connection:
        receipt = connection.execute(
            "SELECT case_id,case_version,event_type,state,delivery_id "
            "FROM core_event_dispatch_receipts"
        ).fetchone()
        delivery_count = connection.execute(
            "SELECT COUNT(*) FROM notification_deliveries"
        ).fetchone()[0]
    assert receipt[0] == case["case_id"]
    assert receipt[1] == active["version"]
    assert receipt[2] == "STATUS_CHANGED"
    assert receipt[3] == "DELIVERED"
    assert isinstance(receipt[4], str) and receipt[4].startswith("nd_")
    assert delivery_count == 1


def test_pending_event_survives_without_route_then_delivers_after_fresh_link(tmp_path: Path):
    (
        core_db, _, transport_db, core, private, durable, owner, _, owner_session, _, case,
    ) = fixture(tmp_path)
    active = activate_free_case(core, case, owner)
    dispatcher = CoreEventNotificationDispatcher(core_db_path=core_db, durable_runtime=durable)
    empty_routes = EphemeralNotificationRouteRegistry()
    bot = FakeBot()
    sender = TelegramNotificationSender(durable_runtime=durable, bot=bot)

    no_route = asyncio.run(dispatcher.dispatch_once(sender=sender, routes=empty_routes))
    assert no_route.ingested_events == 1
    assert no_route.delivered_events == 0
    assert bot.calls == []

    restarted_routes = EphemeralNotificationRouteRegistry()
    chat_id = 52002
    principal = f"telegram:{chat_id}"
    token = bind(private, owner_session, owner["sic_id"], principal)
    restarted_routes.register(
        telegram_principal=principal,
        telegram_chat_id=chat_id,
        support_session_id=token,
    )
    after_link = asyncio.run(dispatcher.dispatch_once(sender=sender, routes=restarted_routes))

    assert active["state"] == "ACTIVE"
    assert after_link.ingested_events == 0
    assert after_link.delivered_events == 1
    assert len(bot.calls) == 1
    with sqlite3.connect(transport_db) as connection:
        assert connection.execute(
            "SELECT state FROM core_event_dispatch_receipts"
        ).fetchone()[0] == "DELIVERED"


def test_cross_user_route_cannot_consume_owner_event_and_raw_route_is_not_persisted(tmp_path: Path):
    (
        core_db, binding_db, transport_db, core, private, durable, owner, other,
        owner_session, other_session, case,
    ) = fixture(tmp_path)
    activate_free_case(core, case, owner)
    dispatcher = CoreEventNotificationDispatcher(core_db_path=core_db, durable_runtime=durable)
    routes = EphemeralNotificationRouteRegistry()
    other_chat = 53003
    other_principal = f"telegram:{other_chat}"
    other_token = bind(private, other_session, other["sic_id"], other_principal)
    routes.register(
        telegram_principal=other_principal,
        telegram_chat_id=other_chat,
        support_session_id=other_token,
    )
    bot = FakeBot()
    sender = TelegramNotificationSender(durable_runtime=durable, bot=bot)

    denied = asyncio.run(dispatcher.dispatch_once(sender=sender, routes=routes))
    assert denied.ingested_events == 1
    assert denied.delivered_events == 0
    assert bot.calls == []
    with sqlite3.connect(transport_db) as connection:
        assert connection.execute(
            "SELECT state FROM core_event_dispatch_receipts"
        ).fetchone()[0] == "PENDING"
        assert connection.execute(
            "SELECT COUNT(*) FROM notification_deliveries"
        ).fetchone()[0] == 0

    owner_chat = 54004
    owner_principal = f"telegram:{owner_chat}"
    owner_token = bind(private, owner_session, owner["sic_id"], owner_principal)
    routes.register(
        telegram_principal=owner_principal,
        telegram_chat_id=owner_chat,
        support_session_id=owner_token,
    )
    allowed = asyncio.run(dispatcher.dispatch_once(sender=sender, routes=routes))
    assert allowed.delivered_events == 1
    assert len(bot.calls) == 1 and bot.calls[0]["chat_id"] == owner_chat

    persistent = binding_db.read_bytes() + transport_db.read_bytes()
    for raw_value in (other_principal, other_token, owner_principal, owner_token):
        assert raw_value.encode("utf-8") not in persistent


def test_core_event_reader_is_read_only_and_receipt_binds_canonical_event_id(tmp_path: Path):
    (
        core_db, _, transport_db, core, private, durable, owner, _, owner_session, _, case,
    ) = fixture(tmp_path)
    active = activate_free_case(core, case, owner)
    with sqlite3.connect(core_db) as connection:
        before = connection.execute(
            "SELECT event_id,case_id,new_state,audit_event,case_version "
            "FROM core_case_events WHERE case_id=? AND new_state='ACTIVE'",
            (case["case_id"],),
        ).fetchone()
        before_count = connection.execute("SELECT COUNT(*) FROM core_case_events").fetchone()[0]

    dispatcher = CoreEventNotificationDispatcher(core_db_path=core_db, durable_runtime=durable)
    chat_id = 55005
    principal = f"telegram:{chat_id}"
    token = bind(private, owner_session, owner["sic_id"], principal)
    routes = EphemeralNotificationRouteRegistry()
    routes.register(
        telegram_principal=principal,
        telegram_chat_id=chat_id,
        support_session_id=token,
    )
    sender = TelegramNotificationSender(durable_runtime=durable, bot=FakeBot())
    asyncio.run(dispatcher.dispatch_once(sender=sender, routes=routes))

    with sqlite3.connect(core_db) as connection:
        after = connection.execute(
            "SELECT event_id,case_id,new_state,audit_event,case_version "
            "FROM core_case_events WHERE event_id=?",
            (before[0],),
        ).fetchone()
        after_count = connection.execute("SELECT COUNT(*) FROM core_case_events").fetchone()[0]
    with sqlite3.connect(transport_db) as connection:
        receipt = connection.execute(
            "SELECT event_id,case_id,case_version,event_type,state "
            "FROM core_event_dispatch_receipts"
        ).fetchone()

    assert after == before
    assert after_count == before_count
    assert receipt == (before[0], before[1], active["version"], "STATUS_CHANGED", "DELIVERED")
