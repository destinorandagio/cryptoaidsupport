"""CHAT01 canonical Core/User/SIC-ID/Case authority.

Uses the runtime canonical BLOCKCHAINPLUS-MASTER.sqlite path. This module owns
Case workflow state but never payment/evidence/entitlement truth.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

VERSION = "1.2"
SCHEMA_VERSION = "chat01-core-1"
API_CONTRACT_VERSION = "v1"
CASE_STATE_VERSION = "1.0"

PRODUCT_KINDS = {
    "FREE",
    "ACTIVATION",
    "ONE_SHOT",
    "CASE",
    "MEMBERSHIP",
    "RECURRING",
    "UPGRADE",
    "DOWNGRADE",
    "RENEWAL",
    "CANCELLATION",
}
STATES = (
    "DRAFT",
    "TRIAGE",
    "PRODUCT_SELECTED",
    "EVIDENCE_REQUIRED",
    "CONSENT_REQUIRED",
    "PAYMENT_REQUIRED",
    "PAYMENT_VERIFYING",
    "ACTIVE",
    "ANALYSIS",
    "ACTION_REQUIRED",
    "RESULT_READY",
    "FOLLOW_UP",
    "CLOSED",
)
TRANSITIONS = {
    "DRAFT": {"TRIAGE"},
    "TRIAGE": {"PRODUCT_SELECTED"},
    "PRODUCT_SELECTED": {"EVIDENCE_REQUIRED", "CONSENT_REQUIRED", "PAYMENT_REQUIRED", "ACTIVE"},
    "EVIDENCE_REQUIRED": {"CONSENT_REQUIRED"},
    "CONSENT_REQUIRED": {"PAYMENT_REQUIRED", "ACTIVE"},
    "PAYMENT_REQUIRED": {"PAYMENT_VERIFYING"},
    "PAYMENT_VERIFYING": {"ACTIVE"},
    "ACTIVE": {"ANALYSIS", "ACTION_REQUIRED"},
    "ANALYSIS": {"ACTION_REQUIRED", "RESULT_READY"},
    "ACTION_REQUIRED": {"ANALYSIS", "RESULT_READY"},
    "RESULT_READY": {"FOLLOW_UP", "CLOSED"},
    "FOLLOW_UP": {"ACTION_REQUIRED", "CLOSED"},
    "CLOSED": set(),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ident(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class CoreError(RuntimeError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


# Stable public error name used by downstream Core consumers.
CaseError = CoreError


class CaseEngine:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if "public_html" in {part.lower() for part in self.db_path.resolve().parts}:
            raise CoreError("DB_PUBLIC_FORBIDDEN", "Canonical DB must not be under public_html", 500)
        self._schema()

    def conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _schema(self) -> None:
        with self.conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS core_users(user_id TEXT PRIMARY KEY,sic_id TEXT NOT NULL UNIQUE,profile_json TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS core_wallet_bindings(binding_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,wallet TEXT NOT NULL UNIQUE,chain_id INTEGER NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS core_sessions(session_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT);
                CREATE TABLE IF NOT EXISTS core_cases(case_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,sic_id TEXT NOT NULL,wallet TEXT,project_ref TEXT,project_truth TEXT NOT NULL,state TEXT NOT NULL,product_code TEXT,product_kind TEXT,version INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,closed_at TEXT);
                CREATE TABLE IF NOT EXISTS core_case_events(event_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,actor TEXT NOT NULL,previous_state TEXT,new_state TEXT NOT NULL,reason TEXT NOT NULL,timestamp TEXT NOT NULL,request_id TEXT NOT NULL,idempotency_key TEXT NOT NULL UNIQUE,authorization TEXT NOT NULL,audit_event TEXT NOT NULL,case_version INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS core_case_tasks(task_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,next_action TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS core_products(product_code TEXT PRIMARY KEY,kind TEXT NOT NULL,status TEXT NOT NULL,eligibility_json TEXT NOT NULL,config_json TEXT NOT NULL,version INTEGER NOT NULL,updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS core_requests(idempotency_key TEXT PRIMARY KEY,request_id TEXT NOT NULL,operation TEXT NOT NULL,response_json TEXT NOT NULL,created_at TEXT NOT NULL);
                """
            )

    @staticmethod
    def _request_replay(
        conn: sqlite3.Connection, idempotency_key: str, operation: str
    ) -> dict[str, Any] | None:
        """Return the recorded response or fail closed on cross-operation key reuse.

        Callers acquire ``BEGIN IMMEDIATE`` before invoking this helper. That makes
        the read-and-side-effect sequence deterministic under concurrent retries:
        the second writer observes the first committed request and replays it rather
        than producing a duplicate side effect or a late UNIQUE-constraint error.
        """
        row = conn.execute(
            "SELECT response_json,operation FROM core_requests WHERE idempotency_key=?",
            (idempotency_key,),
        ).fetchone()
        if not row:
            return None
        if row["operation"] != operation:
            raise CoreError(
                "IDEMPOTENCY_CONFLICT",
                "idempotency key already used by another operation",
                409,
            )
        return json.loads(row["response_json"])

    @staticmethod
    def _record_request(
        conn: sqlite3.Connection,
        *,
        idempotency_key: str,
        request_id: str,
        operation: str,
        result: dict[str, Any],
        created_at: str,
    ) -> None:
        conn.execute(
            "INSERT INTO core_requests VALUES(?,?,?,?,?)",
            (idempotency_key, request_id, operation, json.dumps(result, sort_keys=True), created_at),
        )

    def register_user(
        self,
        sic_id: str,
        profile: dict[str, Any],
        idempotency_key: str,
        request_id: str,
    ) -> dict:
        if not sic_id:
            raise CoreError("INVALID_SIC_ID", "sic_id required")
        with self.conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            replay = self._request_replay(conn, idempotency_key, "register_user")
            if replay is not None:
                conn.execute("COMMIT")
                return replay
            row = conn.execute("SELECT * FROM core_users WHERE sic_id=?", (sic_id,)).fetchone()
            if row:
                result = {"user_id": row["user_id"], "sic_id": sic_id, "returning": True}
            else:
                user_id = ident("usr")
                timestamp = now()
                conn.execute(
                    "INSERT INTO core_users VALUES(?,?,?,?,?)",
                    (user_id, sic_id, json.dumps(profile, sort_keys=True), timestamp, timestamp),
                )
                result = {"user_id": user_id, "sic_id": sic_id, "returning": False}
            self._record_request(
                conn,
                idempotency_key=idempotency_key,
                request_id=request_id,
                operation="register_user",
                result=result,
                created_at=now(),
            )
            conn.execute("COMMIT")
            return result

    def create_session(
        self,
        user_id: str,
        sic_id: str,
        request_id: str,
        idempotency_key: str,
        ttl_seconds: int = 3600,
    ) -> dict:
        if ttl_seconds < 60 or ttl_seconds > 86400:
            raise CoreError("INVALID_SESSION_TTL", "session ttl out of range")
        with self.conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            replay = self._request_replay(conn, idempotency_key, "create_session")
            if replay is not None:
                conn.execute("COMMIT")
                return replay
            user = conn.execute("SELECT * FROM core_users WHERE user_id=?", (user_id,)).fetchone()
            if not user:
                raise CoreError("USER_NOT_FOUND", "user not found", 404)
            if user["sic_id"] != sic_id:
                raise CoreError("SIC_ID_MISMATCH", "SIC-ID mismatch", 403)
            created = datetime.now(timezone.utc)
            expires = created + timedelta(seconds=int(ttl_seconds))
            session_id = ident("ses")
            conn.execute(
                "INSERT INTO core_sessions VALUES(?,?,?,?,?)",
                (session_id, user_id, "ACTIVE", created.isoformat(), expires.isoformat()),
            )
            result = {
                "session_id": session_id,
                "user_id": user_id,
                "sic_id": sic_id,
                "status": "ACTIVE",
                "expires_at": expires.isoformat(),
            }
            self._record_request(
                conn,
                idempotency_key=idempotency_key,
                request_id=request_id,
                operation="create_session",
                result=result,
                created_at=created.isoformat(),
            )
            conn.execute("COMMIT")
            return result

    def resume_session(self, session_id: str, sic_id: str) -> dict:
        with self.conn() as conn:
            row = conn.execute(
                "SELECT s.*,u.sic_id FROM core_sessions s JOIN core_users u ON u.user_id=s.user_id WHERE s.session_id=?",
                (session_id,),
            ).fetchone()
            if not row:
                raise CoreError("SESSION_NOT_FOUND", "session not found", 404)
            if row["sic_id"] != sic_id:
                raise CoreError("SIC_ID_MISMATCH", "SIC-ID mismatch", 403)
            if row["status"] != "ACTIVE":
                raise CoreError("SESSION_INACTIVE", "session is not active", 401)
            if row["expires_at"] and datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
                conn.execute("UPDATE core_sessions SET status='EXPIRED' WHERE session_id=?", (session_id,))
                raise CoreError("SESSION_EXPIRED", "session expired", 401)
            return {
                "session_id": session_id,
                "user_id": row["user_id"],
                "sic_id": row["sic_id"],
                "status": "ACTIVE",
                "expires_at": row["expires_at"],
            }

    def revoke_session(self, session_id: str, user_id: str) -> dict:
        with self.conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM core_sessions WHERE session_id=? AND user_id=?",
                (session_id, user_id),
            ).fetchone()
            if not row:
                raise CoreError("SESSION_NOT_FOUND", "session not found", 404)
            if row["status"] != "REVOKED":
                conn.execute("UPDATE core_sessions SET status='REVOKED' WHERE session_id=?", (session_id,))
            conn.execute("COMMIT")
            return {"session_id": session_id, "user_id": user_id, "status": "REVOKED"}

    def bind_wallet(
        self,
        user_id: str,
        sic_id: str,
        wallet: str,
        request_id: str,
        idempotency_key: str,
    ) -> dict:
        with self.conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            replay = self._request_replay(conn, idempotency_key, "bind_wallet")
            if replay is not None:
                conn.execute("COMMIT")
                return replay
            user = conn.execute("SELECT * FROM core_users WHERE user_id=?", (user_id,)).fetchone()
            if not user:
                raise CoreError("USER_NOT_FOUND", "user not found", 404)
            if user["sic_id"] != sic_id:
                raise CoreError("SIC_ID_MISMATCH", "SIC-ID mismatch", 403)
            normalized_wallet = wallet.lower()
            existing = conn.execute(
                "SELECT * FROM core_wallet_bindings WHERE wallet=?",
                (normalized_wallet,),
            ).fetchone()
            if existing and existing["user_id"] != user_id:
                raise CoreError("WALLET_MISMATCH", "wallet belongs to another user", 409)
            if not existing:
                conn.execute(
                    "INSERT INTO core_wallet_bindings VALUES(?,?,?,?,?,?)",
                    (ident("wb"), user_id, normalized_wallet, 137, "ACTIVE", now()),
                )
            result = {
                "user_id": user_id,
                "wallet": normalized_wallet,
                "chain_id": 137,
                "status": "ACTIVE",
            }
            self._record_request(
                conn,
                idempotency_key=idempotency_key,
                request_id=request_id,
                operation="bind_wallet",
                result=result,
                created_at=now(),
            )
            conn.execute("COMMIT")
            return result

    def open_case(
        self,
        user_id: str,
        sic_id: str,
        wallet: str | None,
        project_ref: str | None,
        search_hit: bool,
        actor: str,
        request_id: str,
        idempotency_key: str,
    ) -> dict:
        with self.conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            replay = self._request_replay(conn, idempotency_key, "open_case")
            if replay is not None:
                conn.execute("COMMIT")
                return replay
            user = conn.execute("SELECT * FROM core_users WHERE user_id=?", (user_id,)).fetchone()
            if not user or user["sic_id"] != sic_id:
                raise CoreError("UNAUTHORIZED_USER", "user/SIC-ID mismatch", 403)
            normalized_wallet = wallet.lower() if wallet else None
            if normalized_wallet:
                binding = conn.execute(
                    "SELECT * FROM core_wallet_bindings WHERE wallet=? AND user_id=? AND status='ACTIVE'",
                    (normalized_wallet, user_id),
                ).fetchone()
                if not binding:
                    raise CoreError("WALLET_MISMATCH", "wallet is not bound to user", 403)
            case_id = ident("case")
            project_truth = "VERIFIED_REFERENCE" if search_hit else "TO_VERIFY"
            timestamp = now()
            conn.execute(
                "INSERT INTO core_cases VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    case_id,
                    user_id,
                    sic_id,
                    normalized_wallet,
                    project_ref,
                    project_truth,
                    "DRAFT",
                    None,
                    None,
                    1,
                    timestamp,
                    timestamp,
                    None,
                ),
            )
            event = {
                "event_id": ident("ce"),
                "case_id": case_id,
                "actor": actor,
                "previous_state": None,
                "new_state": "DRAFT",
                "reason": "case opened",
                "timestamp": timestamp,
                "request_id": request_id,
                "idempotency_key": idempotency_key,
                "authorization": "OWNER",
                "audit_event": "CASE_CREATED",
                "case_version": 1,
            }
            conn.execute(
                "INSERT INTO core_case_events VALUES(:event_id,:case_id,:actor,:previous_state,:new_state,:reason,:timestamp,:request_id,:idempotency_key,:authorization,:audit_event,:case_version)",
                event,
            )
            result = {
                "case_id": case_id,
                "state": "DRAFT",
                "project_truth": project_truth,
                "version": 1,
            }
            self._record_request(
                conn,
                idempotency_key=idempotency_key,
                request_id=request_id,
                operation="open_case",
                result=result,
                created_at=timestamp,
            )
            conn.execute("COMMIT")
            return result

    def get_case(self, case_id: str, user_id: str) -> dict:
        with self.conn() as conn:
            row = conn.execute(
                "SELECT * FROM core_cases WHERE case_id=? AND user_id=?",
                (case_id, user_id),
            ).fetchone()
        if not row:
            raise CoreError("CASE_NOT_FOUND", "case not found or unauthorized", 404)
        return dict(row)

    @staticmethod
    def _paid_entitlement_authorized(conn: sqlite3.Connection, case_id: str) -> bool:
        required = ("entitlement_ledger", "payment_intents")
        if any(
            not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (name,),
            ).fetchone()
            for name in required
        ):
            return False
        row = conn.execute(
            """
            SELECT 1
            FROM entitlement_ledger e
            JOIN payment_intents p ON p.intent_id=e.intent_id
            WHERE e.case_id=? AND p.case_id=? AND e.delta>0
              AND p.state='SETTLED' AND p.entitlement_ref=e.entitlement_ref
            LIMIT 1
            """,
            (case_id, case_id),
        ).fetchone()
        return bool(row)

    def transition(
        self,
        case_id: str,
        user_id: str,
        new_state: str,
        actor: str,
        reason: str,
        request_id: str,
        idempotency_key: str,
        authorization: str,
        expected_version: int,
    ) -> dict:
        if new_state not in STATES:
            raise CoreError("INVALID_STATE", "unknown state")
        with self.conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            replay = self._request_replay(conn, idempotency_key, "transition")
            if replay is not None:
                conn.execute("COMMIT")
                return replay
            case = conn.execute(
                "SELECT * FROM core_cases WHERE case_id=? AND user_id=?",
                (case_id, user_id),
            ).fetchone()
            if not case:
                raise CoreError("CASE_NOT_FOUND", "case not found or unauthorized", 404)
            if case["version"] != expected_version:
                raise CoreError("STALE_STATE", "case version is stale", 409)
            if new_state not in TRANSITIONS[case["state"]]:
                raise CoreError("INVALID_TRANSITION", f"{case['state']} -> {new_state}", 409)
            if new_state == "ACTIVE":
                if authorization == "ENTITLEMENT_GRANTED":
                    if not self._paid_entitlement_authorized(conn, case_id):
                        raise CoreError(
                            "MISSING_ENTITLEMENT",
                            "paid activation requires a settled CHAT02 entitlement effect",
                            403,
                        )
                elif authorization != "FREE_PRODUCT_AUTHORIZED":
                    raise CoreError(
                        "MISSING_ENTITLEMENT",
                        "activation requires external entitlement authorization",
                        403,
                    )
            version = case["version"] + 1
            timestamp = now()
            conn.execute(
                "UPDATE core_cases SET state=?,version=?,updated_at=?,closed_at=? WHERE case_id=?",
                (
                    new_state,
                    version,
                    timestamp,
                    timestamp if new_state == "CLOSED" else None,
                    case_id,
                ),
            )
            conn.execute(
                "INSERT INTO core_case_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ident("ce"),
                    case_id,
                    actor,
                    case["state"],
                    new_state,
                    reason,
                    timestamp,
                    request_id,
                    idempotency_key,
                    authorization,
                    "CASE_STATE_TRANSITION",
                    version,
                ),
            )
            result = {
                "case_id": case_id,
                "previous_state": case["state"],
                "state": new_state,
                "version": version,
            }
            self._record_request(
                conn,
                idempotency_key=idempotency_key,
                request_id=request_id,
                operation="transition",
                result=result,
                created_at=timestamp,
            )
            conn.execute("COMMIT")
            return result

    def upsert_product(
        self,
        product_code: str,
        kind: str,
        status: str,
        eligibility: dict,
        config: dict,
        version: int,
    ) -> dict:
        if kind not in PRODUCT_KINDS:
            raise CoreError("INVALID_PRODUCT_KIND", "unsupported product kind")
        with self.conn() as conn:
            conn.execute(
                "INSERT INTO core_products VALUES(?,?,?,?,?,?,?) ON CONFLICT(product_code) DO UPDATE SET kind=excluded.kind,status=excluded.status,eligibility_json=excluded.eligibility_json,config_json=excluded.config_json,version=excluded.version,updated_at=excluded.updated_at",
                (
                    product_code,
                    kind,
                    status,
                    json.dumps(eligibility, sort_keys=True),
                    json.dumps(config, sort_keys=True),
                    version,
                    now(),
                ),
            )
        return {"product_code": product_code, "kind": kind, "status": status, "version": version}

    def select_product(self, case_id: str, user_id: str, product_code: str) -> dict:
        with self.conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            case = conn.execute(
                "SELECT * FROM core_cases WHERE case_id=? AND user_id=?",
                (case_id, user_id),
            ).fetchone()
            product = conn.execute(
                "SELECT * FROM core_products WHERE product_code=? AND status='ACTIVE'",
                (product_code,),
            ).fetchone()
            if not case:
                raise CoreError("CASE_NOT_FOUND", "case not found", 404)
            if not product:
                raise CoreError("PRODUCT_NOT_ELIGIBLE", "product unavailable", 403)
            conn.execute(
                "UPDATE core_cases SET product_code=?,product_kind=?,updated_at=? WHERE case_id=?",
                (product_code, product["kind"], now(), case_id),
            )
            conn.execute("COMMIT")
            return {"case_id": case_id, "product_code": product_code, "kind": product["kind"]}

    def add_task(
        self,
        case_id: str,
        user_id: str,
        title: str,
        next_action: str | None = None,
    ) -> dict:
        self.get_case(case_id, user_id)
        task_id = ident("task")
        timestamp = now()
        with self.conn() as conn:
            conn.execute(
                "INSERT INTO core_case_tasks VALUES(?,?,?,?,?,?,?)",
                (task_id, case_id, title, "OPEN", next_action, timestamp, timestamp),
            )
        return {
            "task_id": task_id,
            "case_id": case_id,
            "status": "OPEN",
            "next_action": next_action,
        }

    def timeline(self, case_id: str, user_id: str) -> list[dict]:
        self.get_case(case_id, user_id)
        with self.conn() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM core_case_events WHERE case_id=? ORDER BY timestamp,event_id",
                    (case_id,),
                ).fetchall()
            ]
