"""CHAT07 durable support transport ledger for the 48H MVP.

This module is deliberately transport-only. It persists an already-authorized
support request and privacy-minimized notification delivery state, but it never
decides SIC-ID identity, Case ownership/state, Evidence, payment, entitlement or
Knowledge truth.

The database is private runtime state and is rejected under ``public_html``.
Raw Telegram principals are never stored; only SHA-256 digests are persisted.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sqlite3
import time
import uuid
from typing import Any

from bot.support_mvp import SafeCaseNotification, SupportRequest

SUPPORT_TRANSPORT_VERSION = "1.0.1"
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class SupportTransportRejected(ValueError):
    """Uniform fail-closed transport rejection."""


def _digest(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SupportTransportRejected("support_transport_failed")
    return sha256(value.strip().encode("utf-8")).hexdigest()


def _now() -> float:
    return time.time()


def _is_link_or_reparse(path: Path) -> bool:
    """Detect POSIX symlinks and Windows reparse points without following them."""
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise SupportTransportRejected("support_transport_unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = getattr(metadata, "st_file_attributes", 0)
    return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def _private_db_path(value: str | Path) -> Path:
    raw = Path(value).expanduser()
    if not raw.name:
        raise SupportTransportRejected("support_transport_unavailable")
    if "public_html" in {part.lower() for part in raw.parts}:
        raise SupportTransportRejected("support_transport_public_storage_forbidden")
    for candidate in (raw.parent, *raw.parent.parents):
        if candidate.exists() and _is_link_or_reparse(candidate):
            raise SupportTransportRejected("support_transport_symlink_storage_forbidden")
    try:
        parent = raw.parent.resolve()
    except OSError as exc:
        raise SupportTransportRejected("support_transport_unavailable") from exc
    if "public_html" in {part.lower() for part in parent.parts}:
        raise SupportTransportRejected("support_transport_public_storage_forbidden")
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SupportTransportRejected("support_transport_unavailable") from exc
    final_path = parent / raw.name
    # SQLite follows a pre-existing final symlink/reparse point. Reject it before
    # opening the database so an attacker cannot redirect private support state.
    if _is_link_or_reparse(final_path):
        raise SupportTransportRejected("support_transport_symlink_storage_forbidden")
    if final_path.exists() and not final_path.is_file():
        raise SupportTransportRejected("support_transport_unavailable")
    try:
        resolved = final_path.resolve(strict=False)
        resolved.relative_to(parent)
    except (OSError, ValueError) as exc:
        raise SupportTransportRejected("support_transport_unavailable") from exc
    if "public_html" in {part.lower() for part in resolved.parts}:
        raise SupportTransportRejected("support_transport_public_storage_forbidden")
    return final_path


@dataclass(frozen=True)
class TicketReceipt:
    ticket_id: str
    case_id: str
    category: str
    escalate: bool
    created_at: float
    idempotent: bool


@dataclass(frozen=True)
class NotificationClaim:
    delivery_id: str
    idempotency_key: str
    state: str
    attempt_count: int
    should_send: bool
    claim_token: str | None


class SupportTransportStore:
    """Private SQLite transport state with deterministic ticket/delivery dedupe."""

    def __init__(self, db_path: str | Path):
        self.db_path = _private_db_path(db_path)
        self._init_schema()
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass

    def _connect(self) -> sqlite3.Connection:
        # Re-check the final component on every open: a previously valid DB must
        # not become a symlink/reparse redirect between store construction and use.
        if _is_link_or_reparse(self.db_path):
            raise SupportTransportRejected("support_transport_symlink_storage_forbidden")
        connection = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS support_tickets(
                  ticket_id TEXT PRIMARY KEY,
                  request_fingerprint TEXT NOT NULL UNIQUE,
                  requester_principal_sha256 TEXT NOT NULL,
                  case_id TEXT NOT NULL,
                  category TEXT NOT NULL,
                  summary TEXT NOT NULL,
                  escalate INTEGER NOT NULL CHECK(escalate IN (0,1)),
                  created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notification_deliveries(
                  delivery_id TEXT PRIMARY KEY,
                  delivery_fingerprint TEXT NOT NULL UNIQUE,
                  source_idempotency_key TEXT NOT NULL,
                  requester_principal_sha256 TEXT NOT NULL,
                  case_id TEXT NOT NULL,
                  event_type TEXT NOT NULL,
                  case_version INTEGER NOT NULL,
                  message TEXT NOT NULL,
                  state TEXT NOT NULL CHECK(state IN ('CLAIMED','DELIVERED')),
                  claim_token_sha256 TEXT,
                  claim_expires_at REAL,
                  attempt_count INTEGER NOT NULL,
                  transport_message_id TEXT,
                  created_at REAL NOT NULL,
                  delivered_at REAL
                );
                """
            )

    @staticmethod
    def _ticket_fingerprint(request: SupportRequest, principal_digest: str) -> str:
        payload = {"case_id": request.case_id,"category": request.category,"summary": request.summary,"escalate": bool(request.escalate),"requester": principal_digest}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(canonical.encode("utf-8")).hexdigest()

    def create_ticket(self, *, request: SupportRequest, telegram_principal: str) -> TicketReceipt:
        if not isinstance(request, SupportRequest): raise SupportTransportRejected("authorized_support_request_required")
        principal_digest = _digest(telegram_principal); fingerprint = self._ticket_fingerprint(request, principal_digest); created_at = _now(); ticket_id = "st_" + uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing=connection.execute("SELECT * FROM support_tickets WHERE request_fingerprint=?",(fingerprint,)).fetchone()
            if existing:
                connection.execute("COMMIT")
                return TicketReceipt(existing["ticket_id"],existing["case_id"],existing["category"],bool(existing["escalate"]),float(existing["created_at"]),True)
            connection.execute("INSERT INTO support_tickets VALUES(?,?,?,?,?,?,?,?)",(ticket_id,fingerprint,principal_digest,request.case_id,request.category,request.summary,1 if request.escalate else 0,created_at)); connection.execute("COMMIT")
        return TicketReceipt(ticket_id,request.case_id,request.category,bool(request.escalate),created_at,False)

    @staticmethod
    def _delivery_fingerprint(notification: SafeCaseNotification, principal_digest: str) -> str:
        return sha256(f"{notification.idempotency_key}|{principal_digest}".encode("utf-8")).hexdigest()

    def claim_notification(self, *, notification: SafeCaseNotification, telegram_principal: str, lease_seconds: int = 60, now: float | None = None) -> NotificationClaim:
        if not isinstance(notification, SafeCaseNotification): raise SupportTransportRejected("authorized_notification_required")
        if isinstance(lease_seconds,bool) or not isinstance(lease_seconds,int) or lease_seconds<1 or lease_seconds>900: raise SupportTransportRejected("invalid_notification_lease")
        principal_digest=_digest(telegram_principal); fingerprint=self._delivery_fingerprint(notification,principal_digest); current_time=_now() if now is None else float(now)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE"); row=connection.execute("SELECT * FROM notification_deliveries WHERE delivery_fingerprint=?",(fingerprint,)).fetchone()
            if row and row["state"]=="DELIVERED": connection.execute("COMMIT"); return NotificationClaim(row["delivery_id"],notification.idempotency_key,"DELIVERED",int(row["attempt_count"]),False,None)
            if row and row["state"]=="CLAIMED" and float(row["claim_expires_at"] or 0)>current_time: connection.execute("COMMIT"); return NotificationClaim(row["delivery_id"],notification.idempotency_key,"CLAIMED",int(row["attempt_count"]),False,None)
            raw_claim=uuid.uuid4().hex; claim_digest=sha256(raw_claim.encode("utf-8")).hexdigest(); expires=current_time+lease_seconds
            if row:
                attempt_count=int(row["attempt_count"])+1; delivery_id=row["delivery_id"]
                connection.execute("UPDATE notification_deliveries SET state='CLAIMED',claim_token_sha256=?,claim_expires_at=?,attempt_count=? WHERE delivery_id=?",(claim_digest,expires,attempt_count,delivery_id))
            else:
                attempt_count=1; delivery_id="nd_"+uuid.uuid4().hex
                connection.execute("INSERT INTO notification_deliveries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(delivery_id,fingerprint,notification.idempotency_key,principal_digest,notification.case_id,notification.event_type,notification.case_version,notification.message,"CLAIMED",claim_digest,expires,attempt_count,None,current_time,None))
            connection.execute("COMMIT")
        return NotificationClaim(delivery_id,notification.idempotency_key,"CLAIMED",attempt_count,True,raw_claim)

    def mark_notification_delivered(self, *, delivery_id: str, claim_token: str, transport_message_id: str, now: float | None = None) -> dict[str, Any]:
        if not all(isinstance(value,str) and value.strip() for value in (delivery_id,claim_token,transport_message_id)): raise SupportTransportRejected("invalid_delivery_receipt")
        claim_digest=sha256(claim_token.strip().encode("utf-8")).hexdigest(); delivered_at=_now() if now is None else float(now)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE"); row=connection.execute("SELECT * FROM notification_deliveries WHERE delivery_id=?",(delivery_id.strip(),)).fetchone()
            if not row: raise SupportTransportRejected("delivery_not_found")
            if row["state"]=="DELIVERED":
                if row["transport_message_id"]!=transport_message_id.strip(): raise SupportTransportRejected("delivery_receipt_conflict")
                connection.execute("COMMIT"); return {"delivery_id":row["delivery_id"],"state":"DELIVERED","idempotent":True}
            if row["claim_token_sha256"]!=claim_digest: raise SupportTransportRejected("delivery_claim_invalid")
            connection.execute("UPDATE notification_deliveries SET state='DELIVERED',transport_message_id=?,delivered_at=?,claim_token_sha256=NULL,claim_expires_at=NULL WHERE delivery_id=?",(transport_message_id.strip(),delivered_at,row["delivery_id"])); connection.execute("COMMIT")
        return {"delivery_id":delivery_id.strip(),"state":"DELIVERED","idempotent":False}

    def integrity(self) -> str:
        with self._connect() as connection: return str(connection.execute("PRAGMA integrity_check").fetchone()[0])

__all__=["NotificationClaim","SUPPORT_TRANSPORT_VERSION","SupportTransportRejected","SupportTransportStore","TicketReceipt"]
