"""CHAT02 durable resolution for idempotency keys that coalesce to one intent.

The canonical MVP intentionally coalesces duplicate economic work for the same
principal/Case even when callers use different idempotency keys.  Every accepted
key must nevertheless stay bound to the exact intent it returned.  Otherwise a
later replay after that intent becomes REJECTED/EXPIRED could create a different
intent and, for the first Case, reserve the activation credit again.

This layer adds only an idempotency-resolution mapping inside the same CHAT02
SQLite authority.  It creates no payment verifier, entitlement ledger, or
transaction initiation path.
"""
from __future__ import annotations

from typing import Any

from .engine import EvidencePaymentError
from .idempotency_engine import EvidencePaymentEngine as _IdempotentEvidencePaymentEngine
from .mvp_engine import DEFAULT_INTENT_TTL_SECONDS

IDEMPOTENCY_ALIAS_CONTRACT_VERSION = "1.0"


class EvidencePaymentEngine(_IdempotentEvidencePaymentEngine):
    """Canonical CHAT02 engine with stable alias-to-intent idempotency results."""

    def __init__(self, db_path, private_root):
        super().__init__(db_path, private_root)
        self._init_idempotency_alias_schema()

    def _init_idempotency_alias_schema(self) -> None:
        with self._connect() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_idempotency_resolutions(
                  idempotency_key TEXT PRIMARY KEY,
                  intent_id TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(idempotency_key) REFERENCES payment_idempotency_bindings(idempotency_key),
                  FOREIGN KEY(intent_id) REFERENCES payment_intents(intent_id)
                )
                """
            )

    def _resolved_intent(self, idempotency_key: str) -> dict[str, Any] | None:
        key = str(idempotency_key).strip()
        with self._connect() as c:
            row = c.execute(
                "SELECT intent_id FROM payment_idempotency_resolutions WHERE idempotency_key=?",
                (key,),
            ).fetchone()
            if not row:
                return None
            intent = c.execute(
                "SELECT * FROM payment_intents WHERE intent_id=?", (row["intent_id"],)
            ).fetchone()
        if not intent:
            raise EvidencePaymentError(
                "IDEMPOTENCY_RESOLUTION_INVALID",
                "Idempotency resolution references a missing payment intent",
            )
        return self.get_intent(intent["intent_id"])

    def _bind_resolution(self, idempotency_key: str, intent_id: str) -> dict[str, Any]:
        key = str(idempotency_key).strip()
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                binding = c.execute(
                    "SELECT 1 FROM payment_idempotency_bindings WHERE idempotency_key=?",
                    (key,),
                ).fetchone()
                if not binding:
                    raise EvidencePaymentError(
                        "IDEMPOTENCY_RESOLUTION_INVALID",
                        "Idempotency resolution requires an existing request binding",
                    )
                intent = c.execute(
                    "SELECT intent_id FROM payment_intents WHERE intent_id=?", (intent_id,)
                ).fetchone()
                if not intent:
                    raise EvidencePaymentError(
                        "IDEMPOTENCY_RESOLUTION_INVALID",
                        "Idempotency resolution requires an existing payment intent",
                    )
                existing = c.execute(
                    "SELECT intent_id FROM payment_idempotency_resolutions WHERE idempotency_key=?",
                    (key,),
                ).fetchone()
                if existing and str(existing["intent_id"]) != str(intent_id):
                    raise EvidencePaymentError(
                        "IDEMPOTENCY_RESOLUTION_CONFLICT",
                        "Idempotency key is already resolved to a different payment intent",
                    )
                if not existing:
                    c.execute(
                        "INSERT INTO payment_idempotency_resolutions VALUES(?,?,datetime('now'))",
                        (key, intent_id),
                    )
                c.execute("COMMIT")
            except Exception:
                if c.in_transaction:
                    c.execute("ROLLBACK")
                raise
        return self.get_intent(intent_id)

    def _bind_active_economic_resolution(
        self,
        *,
        idempotency_key: str,
        principal_id: str,
        purpose: str,
        case_id: str,
    ) -> dict[str, Any] | None:
        """Atomically bind an alias when economic work is already in flight."""
        key = str(idempotency_key).strip()
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                existing_resolution = c.execute(
                    "SELECT intent_id FROM payment_idempotency_resolutions WHERE idempotency_key=?",
                    (key,),
                ).fetchone()
                if existing_resolution:
                    intent_id = str(existing_resolution["intent_id"])
                    c.execute("COMMIT")
                    return self.get_intent(intent_id)

                active = c.execute(
                    "SELECT p.intent_id FROM economic_intents ei "
                    "JOIN payment_intents p ON p.intent_id=ei.intent_id "
                    "WHERE ei.principal_id=? AND ei.purpose=? AND ei.case_id=? "
                    "AND p.state NOT IN ('EXPIRED','REJECTED') "
                    "ORDER BY ei.created_at DESC LIMIT 1",
                    (str(principal_id), str(purpose), str(case_id)),
                ).fetchone()
                if not active:
                    c.execute("COMMIT")
                    return None

                intent_id = str(active["intent_id"])
                c.execute(
                    "INSERT INTO payment_idempotency_resolutions(idempotency_key,intent_id,created_at) "
                    "VALUES(?,?,datetime('now'))",
                    (key, intent_id),
                )
                c.execute("COMMIT")
                return self.get_intent(intent_id)
            except Exception:
                if c.in_transaction:
                    c.execute("ROLLBACK")
                raise

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
        operation, payload = self._payment_payload(
            case_id=case_id,
            entitlement_ref=entitlement_ref,
            payer=payer,
            asset=asset,
            expected_value=expected_value,
            request_id=request_id,
            ttl_seconds=ttl_seconds,
            economic=_economic,
        )
        self._bind_idempotency(
            idempotency_key=idempotency_key, operation=operation, payload=payload
        )
        resolved = self._resolved_intent(idempotency_key)
        if resolved:
            return resolved
        if _economic:
            resolved = self._bind_active_economic_resolution(
                idempotency_key=idempotency_key,
                principal_id=_economic["principal_id"],
                purpose=_economic["purpose"],
                case_id=_economic["case_id"],
            )
            if resolved:
                return resolved
        result = super().create_payment_intent(
            case_id=case_id,
            entitlement_ref=entitlement_ref,
            payer=payer,
            asset=asset,
            expected_value=expected_value,
            request_id=request_id,
            idempotency_key=idempotency_key,
            ttl_seconds=ttl_seconds,
            _economic=_economic,
        )
        return self._bind_resolution(idempotency_key, result["intent_id"])

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
        operation, payload = self._activation_payload(
            principal_id=principal_id,
            payer=payer,
            request_id=request_id,
            ttl_seconds=ttl_seconds,
        )
        self._bind_idempotency(
            idempotency_key=idempotency_key, operation=operation, payload=payload
        )
        resolved = self._resolved_intent(idempotency_key)
        if resolved:
            return resolved
        resolved = self._bind_active_economic_resolution(
            idempotency_key=idempotency_key,
            principal_id=principal_id,
            purpose="ACTIVATION",
            case_id=f"activation:{principal_id}",
        )
        if resolved:
            return resolved
        result = super().create_activation_intent(
            principal_id=principal_id,
            payer=payer,
            request_id=request_id,
            idempotency_key=idempotency_key,
            ttl_seconds=ttl_seconds,
        )
        return self._bind_resolution(idempotency_key, result["intent_id"])

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
            raise EvidencePaymentError(
                "CASE_PRINCIPAL_REQUIRED", "Principal and Case are required"
            )
        operation, payload = self._case_payload(
            principal_id=principal_id,
            case_id=case_id,
            payer=payer,
            request_id=request_id,
            ttl_seconds=ttl_seconds,
        )
        self._bind_idempotency(
            idempotency_key=idempotency_key, operation=operation, payload=payload
        )
        resolved = self._resolved_intent(idempotency_key)
        if resolved:
            return resolved
        resolved = self._bind_active_economic_resolution(
            idempotency_key=idempotency_key,
            principal_id=principal_id,
            purpose="CASE",
            case_id=case_id,
        )
        if resolved:
            return resolved
        result = super().create_case_payment_intent(
            principal_id=principal_id,
            case_id=case_id,
            payer=payer,
            request_id=request_id,
            idempotency_key=idempotency_key,
            ttl_seconds=ttl_seconds,
        )
        return self._bind_resolution(idempotency_key, result["intent_id"])

    def get_idempotency_resolution(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM payment_idempotency_resolutions WHERE idempotency_key=?",
                (str(idempotency_key).strip(),),
            ).fetchone()
        return dict(row) if row else None
