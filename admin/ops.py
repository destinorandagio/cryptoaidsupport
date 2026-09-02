"""CHAT08 minimum Admin/CRM operations for the 48h CryptoAID MVP.

This module is deliberately thin:
- it never owns Case, Evidence, Payment, Entitlement, Twin or Knowledge truth;
- it reads safe operational views from the canonical SQLite authority;
- Case mutations are routed through CHAT01 ``CaseEngine`` guards/audit;
- payment manual-review state is read-only here and remains CHAT02-owned.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from core.case_engine import CaseEngine, CoreError

ADMIN_VERSION = "0.1.0"
ADMIN_ROLE = "ADMIN_CASE_REVIEWER"


class AdminError(RuntimeError):
    def __init__(self, code: str, message: str, status: int = 403):
        super().__init__(message)
        self.code = code
        self.status = status


class AdminOps:
    """Fail-closed operational facade over CHAT01/CHAT02-owned state."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if "public_html" in {part.lower() for part in self.db_path.resolve().parts}:
            raise AdminError("DB_PUBLIC_FORBIDDEN", "Canonical DB must not be under public_html", 500)
        self.case_engine = CaseEngine(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def _require_role(roles: Iterable[str]) -> None:
        if ADMIN_ROLE not in set(roles):
            raise AdminError("ADMIN_FORBIDDEN", "Admin case-review role required")

    def case_queue(self, *, roles: Iterable[str], state: str | None = None, limit: int = 100) -> list[dict]:
        """Return a privacy-minimized Case operations queue."""
        self._require_role(roles)
        limit = max(1, min(int(limit), 500))
        sql = (
            "SELECT case_id,sic_id,project_ref,project_truth,state,product_code,product_kind,version,updated_at "
            "FROM core_cases"
        )
        params: list[object] = []
        if state:
            sql += " WHERE state=?"
            params.append(state)
        sql += " ORDER BY updated_at DESC,case_id LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def case_summary(self, *, roles: Iterable[str], case_id: str) -> dict:
        """Return safe Case/CRM operational metadata without private Evidence bytes."""
        self._require_role(roles)
        with self._connect() as conn:
            case = conn.execute(
                "SELECT case_id,sic_id,project_ref,project_truth,state,product_code,product_kind,version,created_at,updated_at,closed_at "
                "FROM core_cases WHERE case_id=?",
                (case_id,),
            ).fetchone()
            if not case:
                raise AdminError("CASE_NOT_FOUND", "Case not found", 404)
            event_count = conn.execute(
                "SELECT COUNT(*) FROM core_case_events WHERE case_id=?", (case_id,)
            ).fetchone()[0]
            open_tasks = conn.execute(
                "SELECT COUNT(*) FROM core_case_tasks WHERE case_id=? AND status='OPEN'", (case_id,)
            ).fetchone()[0]
        result = dict(case)
        result.update({"event_count": int(event_count), "open_tasks": int(open_tasks)})
        return result

    def manual_review_queue(self, *, roles: Iterable[str], limit: int = 100) -> list[dict]:
        """Expose CHAT02 MANUAL_REVIEW intents read-only, if the table exists."""
        self._require_role(roles)
        limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='payment_intents'"
            ).fetchone()
            if not exists:
                return []
            rows = conn.execute(
                "SELECT intent_id,case_id,entitlement_ref,chain_id,asset,expected_value,treasury_id,state,updated_at "
                "FROM payment_intents WHERE state='MANUAL_REVIEW' ORDER BY updated_at DESC,intent_id LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def transition_case(
        self,
        *,
        roles: Iterable[str],
        case_id: str,
        new_state: str,
        actor: str,
        reason: str,
        request_id: str,
        idempotency_key: str,
        expected_version: int,
    ) -> dict:
        """Route an admin Case command through CHAT01 guards and audit.

        ``ADMIN_REVIEW`` intentionally does not satisfy the Core entitlement guard,
        so an admin cannot force a Case ACTIVE without CHAT02/FREE authorization.
        """
        self._require_role(roles)
        with self._connect() as conn:
            row = conn.execute("SELECT user_id FROM core_cases WHERE case_id=?", (case_id,)).fetchone()
        if not row:
            raise AdminError("CASE_NOT_FOUND", "Case not found", 404)
        try:
            return self.case_engine.transition(
                case_id=case_id,
                user_id=row["user_id"],
                new_state=new_state,
                actor=actor,
                reason=reason,
                request_id=request_id,
                idempotency_key=idempotency_key,
                authorization="ADMIN_REVIEW",
                expected_version=expected_version,
            )
        except CoreError:
            raise
