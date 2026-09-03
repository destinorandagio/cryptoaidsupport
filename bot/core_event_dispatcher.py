"""CHAT00/10 minimal canonical Core -> Telegram support event dispatcher.

This is integration plumbing, not a new Case or notification authority.

- Core ``core_case_events`` is opened read-only and is the sole event source.
- Only ``CASE_STATE_TRANSITION`` rows whose ``new_state`` is exactly ``ACTIVE``
  are eligible for MVP proactive notification.
- The public notification remains the existing privacy-minimized
  ``STATUS_CHANGED`` catalog item; no payment-complete/Case details are invented.
- Raw Telegram routing data and the opaque support-session token remain memory-only.
- Durable cursor/event receipts live in the already-private Support transport DB.
- Delivery still re-authorizes the current Telegram principal -> canonical Core
  Case owner through ``TelegramNotificationSender`` / ``TelegramDurableSupportRuntime``.

A restart deliberately loses raw routes and therefore requires the existing /link
flow again. Pending canonical events remain durable and can be delivered after a
fresh authorized route is registered.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Iterable

try:
    from .telegram_notification_sender import (
        TelegramNotificationSendRejected,
        TelegramNotificationSender,
    )
    from .telegram_support_transport import TelegramDurableSupportRuntime
except ImportError:  # pragma: no cover - direct bot entrypoint compatibility
    from telegram_notification_sender import (
        TelegramNotificationSendRejected,
        TelegramNotificationSender,
    )
    from telegram_support_transport import TelegramDurableSupportRuntime

CORE_EVENT_DISPATCHER_VERSION = "1.0.0"
_SUPPORTED_AUDIT_EVENT = "CASE_STATE_TRANSITION"
_SUPPORTED_NEW_STATE = "ACTIVE"
_SAFE_EVENT_TYPE = "STATUS_CHANGED"


class CoreEventDispatchRejected(ValueError):
    """Fail-closed dispatcher/configuration rejection."""


@dataclass(frozen=True)
class EphemeralNotificationRoute:
    telegram_principal: str
    telegram_chat_id: int
    support_session_id: str


@dataclass(frozen=True)
class PendingCoreNotification:
    event_id: str
    core_rowid: int
    case_id: str
    case_version: int
    event_type: str


@dataclass(frozen=True)
class DispatchCycleResult:
    ingested_events: int
    pending_events: int
    delivered_events: int


def _clean_text(value: str, *, max_len: int = 256) -> str:
    if not isinstance(value, str):
        raise CoreEventDispatchRejected("support_event_dispatch_failed")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > max_len:
        raise CoreEventDispatchRejected("support_event_dispatch_failed")
    return cleaned


class EphemeralNotificationRouteRegistry:
    """Memory-only direct-chat routes established by the existing /link flow."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._routes: dict[str, EphemeralNotificationRoute] = {}

    def register(
        self,
        *,
        telegram_principal: str,
        telegram_chat_id: int,
        support_session_id: str,
    ) -> EphemeralNotificationRoute:
        principal = _clean_text(telegram_principal, max_len=128)
        token = _clean_text(support_session_id)
        if (
            isinstance(telegram_chat_id, bool)
            or not isinstance(telegram_chat_id, int)
            or telegram_chat_id <= 0
            or principal != f"telegram:{telegram_chat_id}"
        ):
            raise CoreEventDispatchRejected("support_event_dispatch_failed")
        route = EphemeralNotificationRoute(
            telegram_principal=principal,
            telegram_chat_id=telegram_chat_id,
            support_session_id=token,
        )
        with self._lock:
            self._routes[principal] = route
        return route

    def remove(self, telegram_principal: str) -> None:
        try:
            principal = _clean_text(telegram_principal, max_len=128)
        except CoreEventDispatchRejected:
            return
        with self._lock:
            self._routes.pop(principal, None)

    def snapshot(self) -> tuple[EphemeralNotificationRoute, ...]:
        with self._lock:
            return tuple(self._routes.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._routes)


class CoreEventNotificationDispatcher:
    """Read canonical Core events and dispatch only authorized safe notifications."""

    def __init__(
        self,
        *,
        core_db_path: str | Path,
        durable_runtime: TelegramDurableSupportRuntime,
    ):
        if not isinstance(durable_runtime, TelegramDurableSupportRuntime):
            raise CoreEventDispatchRejected("support_event_dispatch_unavailable")
        self.core_db_path = Path(core_db_path).expanduser()
        if not self.core_db_path.exists() or not self.core_db_path.is_file():
            raise CoreEventDispatchRejected("support_event_dispatch_unavailable")
        if "public_html" in {part.lower() for part in self.core_db_path.resolve().parts}:
            raise CoreEventDispatchRejected("support_event_dispatch_unavailable")
        self.runtime = durable_runtime
        self._init_private_schema()

    def _support_conn(self) -> sqlite3.Connection:
        # Reuse the transport owner's symlink/reparse/public_html checks on every
        # open rather than creating a second private-storage policy.
        connection = self.runtime.transport._connect()
        connection.row_factory = sqlite3.Row
        return connection

    def _core_conn(self) -> sqlite3.Connection:
        try:
            resolved = self.core_db_path.resolve(strict=True)
            connection = sqlite3.connect(
                f"{resolved.as_uri()}?mode=ro",
                uri=True,
                timeout=30,
                isolation_level=None,
            )
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise CoreEventDispatchRejected("support_event_dispatch_unavailable") from exc
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init_private_schema(self) -> None:
        with self._support_conn() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS core_event_dispatch_cursor(
                  cursor_name TEXT PRIMARY KEY,
                  last_core_rowid INTEGER NOT NULL CHECK(last_core_rowid>=0),
                  updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS core_event_dispatch_receipts(
                  event_id TEXT PRIMARY KEY,
                  core_rowid INTEGER NOT NULL UNIQUE,
                  case_id TEXT NOT NULL,
                  case_version INTEGER NOT NULL CHECK(case_version>=1),
                  event_type TEXT NOT NULL CHECK(event_type='STATUS_CHANGED'),
                  state TEXT NOT NULL CHECK(state IN ('PENDING','DELIVERED')),
                  delivery_id TEXT,
                  observed_at REAL NOT NULL,
                  delivered_at REAL
                );
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO core_event_dispatch_cursor"
                "(cursor_name,last_core_rowid,updated_at) VALUES('core_case_events',0,?)",
                (time.time(),),
            )

    @staticmethod
    def _validate_core_row(row: sqlite3.Row) -> None:
        if (
            isinstance(row["core_rowid"], bool)
            or not isinstance(row["core_rowid"], int)
            or row["core_rowid"] < 1
        ):
            raise CoreEventDispatchRejected("support_event_dispatch_failed")
        _clean_text(row["event_id"], max_len=128)
        _clean_text(row["case_id"], max_len=128)
        _clean_text(row["audit_event"], max_len=128)
        _clean_text(row["new_state"], max_len=128)
        if (
            isinstance(row["case_version"], bool)
            or not isinstance(row["case_version"], int)
            or row["case_version"] < 1
        ):
            raise CoreEventDispatchRejected("support_event_dispatch_failed")

    def ingest(self, *, limit: int = 100) -> int:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise CoreEventDispatchRejected("support_event_dispatch_failed")
        with self._support_conn() as support:
            cursor_row = support.execute(
                "SELECT last_core_rowid FROM core_event_dispatch_cursor "
                "WHERE cursor_name='core_case_events'"
            ).fetchone()
        if cursor_row is None:
            raise CoreEventDispatchRejected("support_event_dispatch_unavailable")
        last_rowid = int(cursor_row["last_core_rowid"])

        try:
            with self._core_conn() as core:
                rows = core.execute(
                    "SELECT rowid AS core_rowid,event_id,case_id,audit_event,new_state,case_version "
                    "FROM core_case_events WHERE rowid>? ORDER BY rowid LIMIT ?",
                    (last_rowid, limit),
                ).fetchall()
        except sqlite3.Error as exc:
            raise CoreEventDispatchRejected("support_event_dispatch_unavailable") from exc

        ingested = 0
        for row in rows:
            self._validate_core_row(row)
            observed_at = time.time()
            with self._support_conn() as support:
                support.execute("BEGIN IMMEDIATE")
                current_cursor = support.execute(
                    "SELECT last_core_rowid FROM core_event_dispatch_cursor "
                    "WHERE cursor_name='core_case_events'"
                ).fetchone()
                if current_cursor is None:
                    support.rollback()
                    raise CoreEventDispatchRejected("support_event_dispatch_unavailable")
                if int(row["core_rowid"]) <= int(current_cursor["last_core_rowid"]):
                    support.commit()
                    continue

                if (
                    row["audit_event"] == _SUPPORTED_AUDIT_EVENT
                    and row["new_state"] == _SUPPORTED_NEW_STATE
                ):
                    existing = support.execute(
                        "SELECT core_rowid,case_id,case_version,event_type "
                        "FROM core_event_dispatch_receipts WHERE event_id=?",
                        (row["event_id"],),
                    ).fetchone()
                    if existing is not None and (
                        int(existing["core_rowid"]) != int(row["core_rowid"])
                        or existing["case_id"] != row["case_id"]
                        or int(existing["case_version"]) != int(row["case_version"])
                        or existing["event_type"] != _SAFE_EVENT_TYPE
                    ):
                        support.rollback()
                        raise CoreEventDispatchRejected("support_event_dispatch_failed")
                    if existing is None:
                        support.execute(
                            "INSERT INTO core_event_dispatch_receipts("
                            "event_id,core_rowid,case_id,case_version,event_type,state,"
                            "delivery_id,observed_at,delivered_at"
                            ") VALUES(?,?,?,?,?,'PENDING',NULL,?,NULL)",
                            (
                                row["event_id"],
                                int(row["core_rowid"]),
                                row["case_id"],
                                int(row["case_version"]),
                                _SAFE_EVENT_TYPE,
                                observed_at,
                            ),
                        )
                        ingested += 1

                support.execute(
                    "UPDATE core_event_dispatch_cursor SET last_core_rowid=?,updated_at=? "
                    "WHERE cursor_name='core_case_events'",
                    (int(row["core_rowid"]), observed_at),
                )
                support.commit()
        return ingested

    def pending(self, *, limit: int = 100) -> tuple[PendingCoreNotification, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise CoreEventDispatchRejected("support_event_dispatch_failed")
        with self._support_conn() as connection:
            rows = connection.execute(
                "SELECT event_id,core_rowid,case_id,case_version,event_type "
                "FROM core_event_dispatch_receipts WHERE state='PENDING' "
                "ORDER BY core_rowid LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(
            PendingCoreNotification(
                event_id=row["event_id"],
                core_rowid=int(row["core_rowid"]),
                case_id=row["case_id"],
                case_version=int(row["case_version"]),
                event_type=row["event_type"],
            )
            for row in rows
        )

    def mark_delivered(self, *, event_id: str, delivery_id: str, now: float | None = None) -> None:
        event = _clean_text(event_id, max_len=128)
        delivery = _clean_text(delivery_id, max_len=128)
        delivered_at = time.time() if now is None else float(now)
        with self._support_conn() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state,delivery_id FROM core_event_dispatch_receipts WHERE event_id=?",
                (event,),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise CoreEventDispatchRejected("support_event_dispatch_failed")
            if row["state"] == "DELIVERED":
                if row["delivery_id"] != delivery:
                    connection.rollback()
                    raise CoreEventDispatchRejected("support_event_dispatch_failed")
                connection.commit()
                return
            updated = connection.execute(
                "UPDATE core_event_dispatch_receipts "
                "SET state='DELIVERED',delivery_id=?,delivered_at=? "
                "WHERE event_id=? AND state='PENDING'",
                (delivery, delivered_at, event),
            ).rowcount
            if updated != 1:
                connection.rollback()
                raise CoreEventDispatchRejected("support_event_dispatch_failed")
            connection.commit()

    def receipt_state(self, event_id: str) -> dict[str, object] | None:
        event = _clean_text(event_id, max_len=128)
        with self._support_conn() as connection:
            row = connection.execute(
                "SELECT event_id,case_id,case_version,event_type,state,delivery_id "
                "FROM core_event_dispatch_receipts WHERE event_id=?",
                (event,),
            ).fetchone()
        return dict(row) if row is not None else None

    async def dispatch_once(
        self,
        *,
        sender: TelegramNotificationSender,
        routes: EphemeralNotificationRouteRegistry,
        ingest_limit: int = 100,
        pending_limit: int = 100,
    ) -> DispatchCycleResult:
        if not isinstance(sender, TelegramNotificationSender) or not isinstance(
            routes, EphemeralNotificationRouteRegistry
        ):
            raise CoreEventDispatchRejected("support_event_dispatch_unavailable")

        ingested = self.ingest(limit=ingest_limit)
        pending = self.pending(limit=pending_limit)
        delivered = 0
        route_snapshot: Iterable[EphemeralNotificationRoute] = routes.snapshot()

        for event in pending:
            for route in route_snapshot:
                try:
                    delivery = await sender.deliver(
                        telegram_principal=route.telegram_principal,
                        telegram_chat_id=route.telegram_chat_id,
                        support_session_id=route.support_session_id,
                        case_id=event.case_id,
                        event_type=event.event_type,
                    )
                except TelegramNotificationSendRejected:
                    # Wrong owner, revoked/expired link, network failure or an
                    # in-flight durable lease all fail closed. Keep the Core
                    # event pending for a future authorized route/retry.
                    continue
                if delivery.state == "DELIVERED":
                    self.mark_delivered(
                        event_id=event.event_id,
                        delivery_id=delivery.delivery_id,
                    )
                    delivered += 1
                    break

        return DispatchCycleResult(
            ingested_events=ingested,
            pending_events=len(pending),
            delivered_events=delivered,
        )


log = logging.getLogger("cryptoaid.support_dispatch")
_GLOBAL_ROUTES = EphemeralNotificationRouteRegistry()
_DAEMON_LOCK = threading.Lock()
_DAEMON_THREAD: threading.Thread | None = None


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _poll_interval() -> float:
    raw = os.getenv("CRYPTOAID_SUPPORT_EVENT_POLL_SECONDS", "5").strip()
    try:
        value = float(raw)
    except ValueError:
        return 5.0
    return min(60.0, max(1.0, value))


async def _dispatch_daemon(
    *,
    core_db_path: Path,
    binding_db_path: Path,
    transport_db_path: Path,
    telegram_bot_token: str,
    interval: float,
) -> None:
    # Imports stay lazy so the SupportBindingStore -> registration hook cannot
    # create an import cycle while the binding module itself is loading.
    from telegram import Bot

    try:
        from .telegram_private_support import TelegramPrivateSupportRuntime
    except ImportError:  # pragma: no cover
        from telegram_private_support import TelegramPrivateSupportRuntime

    private_runtime = TelegramPrivateSupportRuntime(binding_db_path, core_db_path)
    durable_runtime = TelegramDurableSupportRuntime(
        private_runtime=private_runtime,
        transport_db_path=transport_db_path,
    )
    dispatcher = CoreEventNotificationDispatcher(
        core_db_path=core_db_path,
        durable_runtime=durable_runtime,
    )
    async with Bot(telegram_bot_token) as bot:
        sender = TelegramNotificationSender(durable_runtime=durable_runtime, bot=bot)
        while True:
            try:
                cycle = await dispatcher.dispatch_once(
                    sender=sender,
                    routes=_GLOBAL_ROUTES,
                )
                if cycle.ingested_events or cycle.delivered_events:
                    log.info(
                        "support_event_dispatch ingested=%d pending=%d delivered=%d routes=%d",
                        cycle.ingested_events,
                        cycle.pending_events,
                        cycle.delivered_events,
                        len(_GLOBAL_ROUTES),
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                # A target/network/runtime failure cannot mutate Core truth and
                # cannot advance a PENDING event to DELIVERED. Retry later.
                log.exception("support_event_dispatch_cycle_failed")
            await asyncio.sleep(interval)


def _daemon_entry(
    core_db_path: Path,
    binding_db_path: Path,
    transport_db_path: Path,
    telegram_bot_token: str,
    interval: float,
) -> None:
    try:
        asyncio.run(
            _dispatch_daemon(
                core_db_path=core_db_path,
                binding_db_path=binding_db_path,
                transport_db_path=transport_db_path,
                telegram_bot_token=telegram_bot_token,
                interval=interval,
            )
        )
    except Exception:
        log.exception("support_event_dispatch_daemon_stopped")


def register_linked_route(
    *,
    telegram_principal: str,
    support_session_id: str,
    core_db_path: str | Path,
    binding_db_path: str | Path,
) -> None:
    """Register one freshly authorized /link route in memory and start dispatcher.

    The raw principal/chat ID and opaque support token are never written by this
    function. If proactive dispatch is disabled or its private runtime settings
    are incomplete, normal private Support remains available and no thread starts.
    """
    principal = _clean_text(telegram_principal, max_len=128)
    if not principal.startswith("telegram:"):
        raise CoreEventDispatchRejected("support_event_dispatch_failed")
    try:
        chat_id = int(principal.split(":", 1)[1])
    except (TypeError, ValueError) as exc:
        raise CoreEventDispatchRejected("support_event_dispatch_failed") from exc
    _GLOBAL_ROUTES.register(
        telegram_principal=principal,
        telegram_chat_id=chat_id,
        support_session_id=support_session_id,
    )

    if not _env_enabled("CRYPTOAID_SUPPORT_EVENT_DISPATCH"):
        return
    transport_raw = os.getenv("CRYPTOAID_SUPPORT_TRANSPORT_DB", "").strip()
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not transport_raw or not bot_token:
        log.warning("support_event_dispatch_unavailable")
        return

    core_path = Path(core_db_path).expanduser()
    binding_path = Path(binding_db_path).expanduser()
    transport_path = Path(transport_raw).expanduser()
    global _DAEMON_THREAD
    with _DAEMON_LOCK:
        if _DAEMON_THREAD is not None and _DAEMON_THREAD.is_alive():
            return
        _DAEMON_THREAD = threading.Thread(
            target=_daemon_entry,
            args=(
                core_path,
                binding_path,
                transport_path,
                bot_token,
                _poll_interval(),
            ),
            name="cryptoaid-support-event-dispatch",
            daemon=True,
        )
        _DAEMON_THREAD.start()


def unregister_linked_route(telegram_principal: str) -> None:
    _GLOBAL_ROUTES.remove(telegram_principal)


__all__ = [
    "CORE_EVENT_DISPATCHER_VERSION",
    "CoreEventDispatchRejected",
    "CoreEventNotificationDispatcher",
    "DispatchCycleResult",
    "EphemeralNotificationRoute",
    "EphemeralNotificationRouteRegistry",
    "PendingCoreNotification",
    "register_linked_route",
    "unregister_linked_route",
]
