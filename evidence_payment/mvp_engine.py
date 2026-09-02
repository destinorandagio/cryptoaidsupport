"""CHAT02 48h-MVP Evidence/Payment economics extension.

This module layers the frozen activation50 -> credit50 -> first-case450 -> later500
contract and durable payment-intent expiry onto the canonical CHAT02 engine.
It never initiates a transaction. All settlement truth still comes from the base
verifier/certificate path and the same SQLite authority.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from .engine import (
    CHAIN_ID,
    EvidencePaymentEngine as _BaseEvidencePaymentEngine,
    EvidencePaymentError,
    PAYMENT_TRANSITIONS,
    _id,
    _now,
)

DEFAULT_INTENT_TTL_SECONDS = 900
MAX_INTENT_TTL_SECONDS = 86_400
ACTIVATION_VALUE = "50"
CASE_NOMINAL_VALUE = "500"
FIRST_CASE_CREDIT = "50"
FIRST_CASE_PAYABLE = "450"
SUBSEQUENT_CASE_PAYABLE = "500"
_PRE_TX_STATES = {"INTENT_CREATED", "USER_ACTION_REQUIRED"}


def _parse_ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class EvidencePaymentEngine(_BaseEvidencePaymentEngine):
    """Canonical CHAT02 engine with the frozen MVP economics contract."""

    def __init__(self, db_path, private_root):
        super().__init__(db_path, private_root)
        self._init_mvp_schema()

    def _init_mvp_schema(self) -> None:
        """Apply an additive, fail-closed schema extension to the same authority."""
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            columns = {row[1] for row in c.execute("PRAGMA table_info(payment_intents)").fetchall()}
            if "expires_at" not in columns:
                c.execute("ALTER TABLE payment_intents ADD COLUMN expires_at TEXT")
            # Existing non-terminal intents from a pre-expiry schema become expired on
            # next read. This is deliberately fail-closed rather than granting an
            # unbounded payment window.
            c.execute("UPDATE payment_intents SET expires_at=updated_at WHERE expires_at IS NULL")
            c.executescript("""
            CREATE TABLE IF NOT EXISTS economic_intents(
              intent_id TEXT PRIMARY KEY,
              principal_id TEXT NOT NULL,
              purpose TEXT NOT NULL CHECK(purpose IN ('ACTIVATION','CASE')),
              case_id TEXT NOT NULL,
              nominal_value TEXT NOT NULL,
              credit_applied TEXT NOT NULL,
              payable_value TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(principal_id,purpose,case_id));

            CREATE TABLE IF NOT EXISTS activation_credits(
              principal_id TEXT PRIMARY KEY,
              activation_intent_id TEXT NOT NULL UNIQUE,
              amount TEXT NOT NULL,
              state TEXT NOT NULL CHECK(state IN ('AVAILABLE','RESERVED','CONSUMED')),
              reserved_case_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL);

            CREATE INDEX IF NOT EXISTS idx_payment_intents_expires_at
              ON payment_intents(state,expires_at);
            CREATE INDEX IF NOT EXISTS idx_economic_intents_principal
              ON economic_intents(principal_id,purpose,case_id);

            CREATE TRIGGER IF NOT EXISTS trg_activation_credit_after_entitlement
            AFTER INSERT ON entitlement_ledger
            WHEN EXISTS(
              SELECT 1 FROM economic_intents ei
              WHERE ei.intent_id=NEW.intent_id AND ei.purpose='ACTIVATION'
            )
            BEGIN
              INSERT OR IGNORE INTO activation_credits(
                principal_id,activation_intent_id,amount,state,reserved_case_id,created_at,updated_at
              )
              SELECT ei.principal_id,NEW.intent_id,'50','AVAILABLE',NULL,NEW.created_at,NEW.created_at
              FROM economic_intents ei WHERE ei.intent_id=NEW.intent_id;
            END;

            CREATE TRIGGER IF NOT EXISTS trg_case_credit_guard_before_entitlement
            BEFORE INSERT ON entitlement_ledger
            WHEN EXISTS(
              SELECT 1 FROM economic_intents ei
              WHERE ei.intent_id=NEW.intent_id AND ei.purpose='CASE' AND ei.credit_applied='50'
            )
            AND NOT EXISTS(
              SELECT 1
              FROM economic_intents ei
              JOIN activation_credits ac ON ac.principal_id=ei.principal_id
              WHERE ei.intent_id=NEW.intent_id
                AND ac.state='RESERVED'
                AND ac.reserved_case_id=NEW.case_id
            )
            BEGIN
              SELECT RAISE(ABORT,'CREDIT_RESERVATION_MISSING');
            END;

            CREATE TRIGGER IF NOT EXISTS trg_case_credit_consume_after_entitlement
            AFTER INSERT ON entitlement_ledger
            WHEN EXISTS(
              SELECT 1 FROM economic_intents ei
              WHERE ei.intent_id=NEW.intent_id AND ei.purpose='CASE' AND ei.credit_applied='50'
            )
            BEGIN
              UPDATE activation_credits
              SET state='CONSUMED', updated_at=NEW.created_at
              WHERE principal_id=(SELECT principal_id FROM economic_intents WHERE intent_id=NEW.intent_id)
                AND state='RESERVED'
                AND reserved_case_id=NEW.case_id;
            END;

            CREATE TRIGGER IF NOT EXISTS trg_case_credit_release_on_expiry
            AFTER UPDATE OF state ON payment_intents
            WHEN NEW.state='EXPIRED' AND OLD.state<>NEW.state
            BEGIN
              UPDATE activation_credits
              SET state='AVAILABLE', reserved_case_id=NULL, updated_at=NEW.updated_at
              WHERE principal_id=(SELECT principal_id FROM economic_intents WHERE intent_id=NEW.intent_id AND purpose='CASE')
                AND state='RESERVED'
                AND reserved_case_id=(SELECT case_id FROM economic_intents WHERE intent_id=NEW.intent_id AND purpose='CASE');
            END;
            """)
            c.execute("COMMIT")

    @staticmethod
    def _expiry(ttl_seconds: int) -> tuple[str, str]:
        try:
            ttl = int(ttl_seconds)
        except (TypeError, ValueError) as exc:
            raise EvidencePaymentError("BAD_INTENT_TTL", "Payment intent TTL must be an integer") from exc
        if ttl <= 0 or ttl > MAX_INTENT_TTL_SECONDS:
            raise EvidencePaymentError("BAD_INTENT_TTL", "Payment intent TTL must be between 1 and 86400 seconds")
        created = datetime.now(timezone.utc)
        return created.isoformat(), (created + timedelta(seconds=ttl)).isoformat()

    def _expire_if_needed(self, intent_id: str) -> dict[str, Any]:
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM payment_intents WHERE intent_id=?", (intent_id,)).fetchone()
            if not row:
                c.execute("ROLLBACK")
                raise EvidencePaymentError("NOT_FOUND", "Payment intent not found")
            state = row["state"]
            expires_at = row["expires_at"]
            if state in _PRE_TX_STATES and expires_at and datetime.now(timezone.utc) >= _parse_ts(expires_at):
                now = _now()
                c.execute(
                    "UPDATE payment_intents SET state='EXPIRED',updated_at=? WHERE intent_id=? AND state=?",
                    (now, intent_id, state),
                )
                if c.total_changes:
                    c.execute(
                        "INSERT INTO payment_events VALUES(?,?,?,?,?,?,?)",
                        (_id("pe"), intent_id, state, "EXPIRED", "payment intent expired", None, now),
                    )
                row = c.execute("SELECT * FROM payment_intents WHERE intent_id=?", (intent_id,)).fetchone()
            c.execute("COMMIT")
        return dict(row)

    def get_intent(self, intent_id: str) -> dict[str, Any]:
        return self._expire_if_needed(intent_id)

    def create_payment_intent(
        self,
        *,
        case_id: str,
        entitlement_ref: str,
        payer: str,
        asset: str,
        expected_value: str,
        request_id: str,
        idempotency_key: str,
        ttl_seconds: int = DEFAULT_INTENT_TTL_SECONDS,
        _economic: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        created_at, expires_at = self._expiry(ttl_seconds)
        treasury = self._route_treasury(asset)
        intent_id = _id("pi")
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            existing = c.execute("SELECT * FROM payment_intents WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if existing:
                c.execute("COMMIT")
                return self.get_intent(existing["intent_id"])
            if _economic:
                existing_economic = c.execute(
                    "SELECT intent_id FROM economic_intents WHERE principal_id=? AND purpose=? AND case_id=?",
                    (_economic["principal_id"], _economic["purpose"], _economic["case_id"]),
                ).fetchone()
                if existing_economic:
                    c.execute("COMMIT")
                    return self.get_intent(existing_economic["intent_id"])
            c.execute(
                "INSERT INTO payment_intents("
                "intent_id,case_id,entitlement_ref,payer,chain_id,asset,expected_value,treasury_id,treasury_address,"
                "state,tx_hash,request_id,idempotency_key,created_at,updated_at,expires_at"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    intent_id,
                    case_id,
                    entitlement_ref,
                    payer,
                    CHAIN_ID,
                    asset,
                    str(expected_value),
                    treasury["treasury_id"],
                    treasury["address"],
                    "INTENT_CREATED",
                    None,
                    request_id,
                    idempotency_key,
                    created_at,
                    created_at,
                    expires_at,
                ),
            )
            c.execute(
                "INSERT INTO payment_events VALUES(?,?,?,?,?,?,?)",
                (_id("pe"), intent_id, None, "INTENT_CREATED", "intent created", None, created_at),
            )
            if _economic:
                c.execute(
                    "INSERT INTO economic_intents VALUES(?,?,?,?,?,?,?,?)",
                    (
                        intent_id,
                        _economic["principal_id"],
                        _economic["purpose"],
                        _economic["case_id"],
                        _economic["nominal_value"],
                        _economic["credit_applied"],
                        _economic["payable_value"],
                        created_at,
                    ),
                )
            c.execute("COMMIT")
        return self.get_intent(intent_id)

    def transition_payment(self, intent_id: str, new_state: str, reason: str, provider_data: dict | None = None) -> dict[str, Any]:
        current = self._expire_if_needed(intent_id)
        if current["state"] == "EXPIRED" and new_state != "EXPIRED":
            raise EvidencePaymentError("INTENT_EXPIRED", "Expired payment intent cannot advance")
        if new_state == "EXPIRED" and current["state"] == "EXPIRED":
            return current
        return super().transition_payment(intent_id, new_state, reason, provider_data)

    def verify_observation(self, intent_id: str, observation: dict[str, Any], provider_observations: list[dict[str, Any]]) -> str:
        if self.get_intent(intent_id)["state"] == "EXPIRED":
            return "MANUAL_REVIEW"
        return super().verify_observation(intent_id, observation, provider_observations)

    def create_activation_intent(
        self,
        *,
        principal_id: str,
        payer: str,
        request_id: str,
        idempotency_key: str,
        ttl_seconds: int = DEFAULT_INTENT_TTL_SECONDS,
    ) -> dict[str, Any]:
        if not principal_id:
            raise EvidencePaymentError("PRINCIPAL_REQUIRED", "SIC-ID principal is required")
        with self._connect() as c:
            granted = c.execute("SELECT state FROM activation_credits WHERE principal_id=?", (principal_id,)).fetchone()
        if granted:
            raise EvidencePaymentError("ACTIVATION_ALREADY_GRANTED", "Activation50 is one-time per principal")
        activation_case = f"activation:{principal_id}"
        return self.create_payment_intent(
            case_id=activation_case,
            entitlement_ref=f"activation_credit50:{principal_id}",
            payer=payer,
            asset="POL",
            expected_value=ACTIVATION_VALUE,
            request_id=request_id,
            idempotency_key=idempotency_key,
            ttl_seconds=ttl_seconds,
            _economic={
                "principal_id": principal_id,
                "purpose": "ACTIVATION",
                "case_id": activation_case,
                "nominal_value": ACTIVATION_VALUE,
                "credit_applied": "0",
                "payable_value": ACTIVATION_VALUE,
            },
        )

    def create_case_payment_intent(
        self,
        *,
        principal_id: str,
        case_id: str,
        payer: str,
        request_id: str,
        idempotency_key: str,
        ttl_seconds: int = DEFAULT_INTENT_TTL_SECONDS,
    ) -> dict[str, Any]:
        if not principal_id or not case_id:
            raise EvidencePaymentError("CASE_PRINCIPAL_REQUIRED", "Principal and Case are required")
        created_at, expires_at = self._expiry(ttl_seconds)
        treasury = self._route_treasury("POL")
        intent_id = _id("pi")
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            existing = c.execute("SELECT * FROM payment_intents WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if existing:
                c.execute("COMMIT")
                return self.get_intent(existing["intent_id"])
            existing_case = c.execute(
                "SELECT intent_id FROM economic_intents WHERE principal_id=? AND purpose='CASE' AND case_id=?",
                (principal_id, case_id),
            ).fetchone()
            if existing_case:
                c.execute("COMMIT")
                return self.get_intent(existing_case["intent_id"])

            credit = c.execute("SELECT * FROM activation_credits WHERE principal_id=?", (principal_id,)).fetchone()
            if not credit:
                c.execute("ROLLBACK")
                raise EvidencePaymentError("ACTIVATION_REQUIRED", "Activation50 settlement is required before first Case")
            if credit["state"] == "RESERVED":
                c.execute("ROLLBACK")
                raise EvidencePaymentError("FIRST_CASE_PENDING", "First-case credit is reserved by another unsettled Case")
            if credit["state"] == "AVAILABLE":
                credit_applied = FIRST_CASE_CREDIT
                payable = FIRST_CASE_PAYABLE
                updated = c.execute(
                    "UPDATE activation_credits SET state='RESERVED',reserved_case_id=?,updated_at=? "
                    "WHERE principal_id=? AND state='AVAILABLE'",
                    (case_id, created_at, principal_id),
                )
                if updated.rowcount != 1:
                    c.execute("ROLLBACK")
                    raise EvidencePaymentError("CREDIT_RACE", "First-case credit reservation lost a race")
            else:
                credit_applied = "0"
                payable = SUBSEQUENT_CASE_PAYABLE

            c.execute(
                "INSERT INTO payment_intents("
                "intent_id,case_id,entitlement_ref,payer,chain_id,asset,expected_value,treasury_id,treasury_address,"
                "state,tx_hash,request_id,idempotency_key,created_at,updated_at,expires_at"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    intent_id,
                    case_id,
                    f"case_active:{case_id}",
                    payer,
                    CHAIN_ID,
                    "POL",
                    payable,
                    treasury["treasury_id"],
                    treasury["address"],
                    "INTENT_CREATED",
                    None,
                    request_id,
                    idempotency_key,
                    created_at,
                    created_at,
                    expires_at,
                ),
            )
            c.execute(
                "INSERT INTO payment_events VALUES(?,?,?,?,?,?,?)",
                (_id("pe"), intent_id, None, "INTENT_CREATED", "case payment intent created", None, created_at),
            )
            c.execute(
                "INSERT INTO economic_intents VALUES(?,?,?,?,?,?,?,?)",
                (intent_id, principal_id, "CASE", case_id, CASE_NOMINAL_VALUE, credit_applied, payable, created_at),
            )
            c.execute("COMMIT")
        return self.get_intent(intent_id)

    def get_activation_credit(self, principal_id: str) -> dict[str, Any] | None:
        with self._connect() as c:
            row = c.execute("SELECT * FROM activation_credits WHERE principal_id=?", (principal_id,)).fetchone()
        return dict(row) if row else None

    def get_economic_intent(self, intent_id: str) -> dict[str, Any] | None:
        with self._connect() as c:
            row = c.execute("SELECT * FROM economic_intents WHERE intent_id=?", (intent_id,)).fetchone()
        return dict(row) if row else None

    def quote_next_case(self, principal_id: str) -> dict[str, str]:
        credit = self.get_activation_credit(principal_id)
        if credit is None:
            return {"stage": "ACTIVATION_REQUIRED", "activation_payable": ACTIVATION_VALUE}
        if credit["state"] == "AVAILABLE":
            return {"stage": "FIRST_CASE", "nominal": CASE_NOMINAL_VALUE, "credit": FIRST_CASE_CREDIT, "payable": FIRST_CASE_PAYABLE}
        if credit["state"] == "RESERVED":
            return {"stage": "FIRST_CASE_PENDING", "payable": FIRST_CASE_PAYABLE}
        return {"stage": "SUBSEQUENT_CASE", "nominal": CASE_NOMINAL_VALUE, "credit": "0", "payable": SUBSEQUENT_CASE_PAYABLE}
