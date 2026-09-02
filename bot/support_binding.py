"""CHAT07 trusted transport binding for private Case support.

This module does not mint SIC-ID, Case, Evidence, payment, or ownership truth.
A user first proves an already-live canonical Core session in the DApp context.
CHAT07 then issues a short-lived, one-time link code whose plaintext is never
stored. Telegram consumes that code once and receives an opaque support-session
token, also stored only as a SHA-256 digest. A principal-scoped resolver can be
injected into ``core.TrustedSupportAPI``; Core re-validates the underlying
session/SIC-ID pair on every private Case authorization request.

The SQLite store is transport metadata only. It must live outside public_html.
It intentionally stores no Case IDs, Evidence, wallets, payment data, free-form
support text, or provider secrets.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import hashlib
from pathlib import Path
import secrets
import sqlite3
import time
from typing import Any

from core.api import CoreAPI
from core.case_engine import CoreError

SUPPORT_BINDING_CONTRACT_VERSION = "1.0.0"


class SupportBindingRejected(ValueError):
    """Uniform fail-closed transport-binding rejection."""


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SupportBindingStore:
    """One-time DApp→Telegram binding without parallel identity authority."""

    def __init__(
        self,
        db_path: str | Path,
        core_db_path: str | Path,
        *,
        link_ttl_seconds: int = 300,
        binding_ttl_seconds: int = 86400,
    ):
        if link_ttl_seconds < 30 or link_ttl_seconds > 900:
            raise ValueError("invalid_link_ttl")
        if binding_ttl_seconds < 300 or binding_ttl_seconds > 604800:
            raise ValueError("invalid_binding_ttl")
        self.db_path = Path(db_path)
        self.core_db_path = Path(core_db_path)
        if any(part.lower() == "public_html" for part in self.db_path.resolve(strict=False).parts):
            raise ValueError("support_binding_db_must_be_private")
        self.link_ttl_seconds = int(link_ttl_seconds)
        self.binding_ttl_seconds = int(binding_ttl_seconds)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS support_link_codes (
                    code_hash TEXT PRIMARY KEY,
                    core_session_id TEXT NOT NULL,
                    sic_id TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    consumed_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS support_principal_bindings (
                    telegram_principal TEXT PRIMARY KEY,
                    support_session_hash TEXT NOT NULL UNIQUE,
                    core_session_id TEXT NOT NULL,
                    sic_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    revoked_at INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_support_binding_expiry
                    ON support_principal_bindings(expires_at, revoked_at);
                """
            )

    @staticmethod
    def _now(now: int | float | None) -> int:
        return int(time.time() if now is None else now)

    @staticmethod
    def _clean(value: str, *, field: str, max_len: int = 256) -> str:
        if not isinstance(value, str):
            raise SupportBindingRejected("support_binding_failed")
        value = value.strip()
        if not value or len(value) > max_len:
            raise SupportBindingRejected("support_binding_failed")
        return value

    def issue_link_code(
        self,
        *,
        core_session_id: str,
        sic_id: str,
        now: int | float | None = None,
    ) -> str:
        """Issue a single-use code only after canonical Core session validation."""
        core_session_id = self._clean(core_session_id, field="core_session_id")
        sic_id = self._clean(sic_id, field="sic_id")
        try:
            principal = CoreAPI(self.core_db_path).resume_session(
                session_id=core_session_id,
                sic_id=sic_id,
            )
        except CoreError as exc:
            raise SupportBindingRejected("support_binding_failed") from exc

        code = secrets.token_urlsafe(18)
        created = self._now(now)
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO support_link_codes(code_hash,core_session_id,sic_id,expires_at,consumed_at) "
                "VALUES(?,?,?,?,NULL)",
                (
                    _digest(code),
                    principal["session_id"],
                    principal["sic_id"],
                    created + self.link_ttl_seconds,
                ),
            )
            conn.commit()
        return code

    def consume_link_code(
        self,
        *,
        telegram_principal: str,
        link_code: str,
        now: int | float | None = None,
    ) -> str:
        """Bind one authenticated Telegram principal to one live Core reference.

        Concurrent consumers of the same link code serialize under BEGIN IMMEDIATE;
        exactly one can mark the code consumed and receive the opaque support token.
        """
        telegram_principal = self._clean(
            telegram_principal, field="telegram_principal", max_len=128
        )
        link_code = self._clean(link_code, field="link_code", max_len=128)
        current = self._now(now)
        support_session = secrets.token_urlsafe(32)
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT core_session_id,sic_id,expires_at,consumed_at "
                "FROM support_link_codes WHERE code_hash=?",
                (_digest(link_code),),
            ).fetchone()
            if row is None or row["consumed_at"] is not None or row["expires_at"] < current:
                conn.rollback()
                raise SupportBindingRejected("support_binding_failed")

            updated = conn.execute(
                "UPDATE support_link_codes SET consumed_at=? "
                "WHERE code_hash=? AND consumed_at IS NULL AND expires_at>=?",
                (current, _digest(link_code), current),
            ).rowcount
            if updated != 1:
                conn.rollback()
                raise SupportBindingRejected("support_binding_failed")

            conn.execute(
                "INSERT INTO support_principal_bindings("
                "telegram_principal,support_session_hash,core_session_id,sic_id,created_at,expires_at,revoked_at"
                ") VALUES(?,?,?,?,?,?,NULL) "
                "ON CONFLICT(telegram_principal) DO UPDATE SET "
                "support_session_hash=excluded.support_session_hash,"
                "core_session_id=excluded.core_session_id,sic_id=excluded.sic_id,"
                "created_at=excluded.created_at,expires_at=excluded.expires_at,revoked_at=NULL",
                (
                    telegram_principal,
                    _digest(support_session),
                    row["core_session_id"],
                    row["sic_id"],
                    current,
                    current + self.binding_ttl_seconds,
                ),
            )
            conn.commit()
        return support_session

    def revoke_principal(self, telegram_principal: str, *, now: int | float | None = None) -> None:
        telegram_principal = self._clean(
            telegram_principal, field="telegram_principal", max_len=128
        )
        with self._conn() as conn:
            conn.execute(
                "UPDATE support_principal_bindings SET revoked_at=? WHERE telegram_principal=?",
                (self._now(now), telegram_principal),
            )

    def resolver_for_principal(
        self,
        telegram_principal: str,
        *,
        now: Callable[[], int | float] | None = None,
    ) -> Callable[[str], Mapping[str, Any] | None]:
        """Return a principal-scoped resolver suitable for TrustedSupportAPI."""
        telegram_principal = self._clean(
            telegram_principal, field="telegram_principal", max_len=128
        )
        clock = now or time.time

        def resolve(support_session_id: str) -> Mapping[str, Any] | None:
            try:
                support_session_id_clean = self._clean(
                    support_session_id, field="support_session_id", max_len=256
                )
            except SupportBindingRejected:
                return None
            current = int(clock())
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT core_session_id,sic_id,expires_at,revoked_at "
                    "FROM support_principal_bindings "
                    "WHERE telegram_principal=? AND support_session_hash=?",
                    (telegram_principal, _digest(support_session_id_clean)),
                ).fetchone()
            if row is None or row["revoked_at"] is not None or row["expires_at"] < current:
                return None
            return {
                "session_id": row["core_session_id"],
                "sic_id": row["sic_id"],
            }

        return resolve
