"""CHAT02 fail-closed payment idempotency binding for the 48H MVP.

Idempotency keys are bound to an operation and a canonical security-critical
request fingerprint before the underlying intent creator can return an existing
row. This preserves one canonical CHAT02 ledger/verifier and adds no payment
initiation capability.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from .engine import CHAIN_ID, EvidencePaymentError, _now, _stable_json
from .mvp_engine import (
    ACTIVATION_VALUE,
    CASE_NOMINAL_VALUE,
    DEFAULT_INTENT_TTL_SECONDS,
    FIRST_CASE_CREDIT,
    FIRST_CASE_PAYABLE,
    MAX_INTENT_TTL_SECONDS,
    SUBSEQUENT_CASE_PAYABLE,
)
from .secure_engine import EvidencePaymentEngine as _SecureEvidencePaymentEngine

IDEMPOTENCY_CONTRACT_VERSION = "1.1"


class EvidencePaymentEngine(_SecureEvidencePaymentEngine):
    """Canonical CHAT02 engine with payload-bound, race-safe idempotency."""

    def __init__(self, db_path, private_root):
        super().__init__(db_path, private_root)
        self._init_idempotency_schema()

    def _init_idempotency_schema(self) -> None:
        with self._connect() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_idempotency_bindings(
                  idempotency_key TEXT PRIMARY KEY,
                  operation TEXT NOT NULL,
                  request_fingerprint TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _canonical_ttl(ttl_seconds: int) -> int:
        try:
            ttl = int(ttl_seconds)
        except (TypeError, ValueError) as exc:
            raise EvidencePaymentError(
                "BAD_INTENT_TTL", "Payment intent TTL must be an integer"
            ) from exc
        if ttl <= 0 or ttl > MAX_INTENT_TTL_SECONDS:
            raise EvidencePaymentError(
                "BAD_INTENT_TTL",
                "Payment intent TTL must be between 1 and 86400 seconds",
            )
        return ttl

    @staticmethod
    def _canonical_payer(payer: str) -> str:
        return str(payer).strip().lower()

    def _payment_payload(
        self,
        *,
        case_id: str,
        entitlement_ref: str,
        payer: str,
        asset: str,
        expected_value: str,
        request_id: str,
        ttl_seconds: int,
        economic: dict[str, str] | None,
    ) -> tuple[str, dict[str, Any]]:
        operation = "GENERIC"
        payload: dict[str, Any] = {
            "case_id": str(case_id),
            "entitlement_ref": str(entitlement_ref),
            "payer": self._canonical_payer(payer),
            "chain_id": CHAIN_ID,
            "asset": str(asset),
            "expected_value": str(expected_value),
            "request_id": str(request_id),
            "ttl_seconds": self._canonical_ttl(ttl_seconds),
        }
        if economic:
            operation = str(economic["purpose"])
            payload["economic"] = {
                "principal_id": str(economic["principal_id"]),
                "purpose": operation,
                "case_id": str(economic["case_id"]),
                "nominal_value": str(economic["nominal_value"]),
                "credit_applied": str(economic["credit_applied"]),
                "payable_value": str(economic["payable_value"]),
            }
        return operation, payload

    def _activation_payload(
        self,
        *,
        principal_id: str,
        payer: str,
        request_id: str,
        ttl_seconds: int,
    ) -> tuple[str, dict[str, Any]]:
        activation_case = f"activation:{principal_id}"
        economic = {
            "principal_id": str(principal_id),
            "purpose": "ACTIVATION",
            "case_id": activation_case,
            "nominal_value": ACTIVATION_VALUE,
            "credit_applied": "0",
            "payable_value": ACTIVATION_VALUE,
        }
        return self._payment_payload(
            case_id=activation_case,
            entitlement_ref=f"activation_credit50:{principal_id}",
            payer=payer,
            asset="POL",
            expected_value=ACTIVATION_VALUE,
            request_id=request_id,
            ttl_seconds=ttl_seconds,
            economic=economic,
        )

    def _case_payload(
        self,
        *,
        principal_id: str,
        case_id: str,
        payer: str,
        request_id: str,
        ttl_seconds: int,
    ) -> tuple[str, dict[str, Any]]:
        return "CASE", {
            "principal_id": str(principal_id),
            "case_id": str(case_id),
            "payer": self._canonical_payer(payer),
            "request_id": str(request_id),
            "ttl_seconds": self._canonical_ttl(ttl_seconds),
            "chain_id": CHAIN_ID,
            "asset": "POL",
            "nominal_value": CASE_NOMINAL_VALUE,
        }

    @staticmethod
    def _row_ttl_seconds(row) -> int | None:
        try:
            created = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
            expires = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
            return int(round((expires - created).total_seconds()))
        except (KeyError, TypeError, ValueError):
            return None

    def _legacy_existing_matches(self, c, *, operation: str, payload: dict[str, Any], row) -> bool:
        if self._canonical_payer(row["payer"]) != payload["payer"]:
            return False
        if int(row["chain_id"]) != CHAIN_ID:
            return False
        if str(row["request_id"]) != str(payload["request_id"]):
            return False
        if self._row_ttl_seconds(row) != int(payload["ttl_seconds"]):
            return False

        economic = c.execute(
            "SELECT * FROM economic_intents WHERE intent_id=?", (row["intent_id"],)
        ).fetchone()

        if operation == "GENERIC":
            return (
                economic is None
                and str(row["case_id"]) == payload["case_id"]
                and str(row["entitlement_ref"]) == payload["entitlement_ref"]
                and str(row["asset"]) == payload["asset"]
                and str(row["expected_value"]) == payload["expected_value"]
            )

        if operation == "ACTIVATION":
            expected = payload["economic"]
            return (
                economic is not None
                and str(row["case_id"]) == payload["case_id"]
                and str(row["entitlement_ref"]) == payload["entitlement_ref"]
                and str(row["asset"]) == "POL"
                and str(row["expected_value"]) == ACTIVATION_VALUE
                and str(economic["principal_id"]) == expected["principal_id"]
                and str(economic["purpose"]) == "ACTIVATION"
                and str(economic["case_id"]) == expected["case_id"]
                and str(economic["nominal_value"]) == ACTIVATION_VALUE
                and str(economic["credit_applied"]) == "0"
                and str(economic["payable_value"]) == ACTIVATION_VALUE
            )

        if operation == "CASE":
            if economic is None:
                return False
            expected = payload.get("economic") or payload
            payable = str(economic["payable_value"])
            credit = str(economic["credit_applied"])
            if (payable, credit) not in {
                (FIRST_CASE_PAYABLE, FIRST_CASE_CREDIT),
                (SUBSEQUENT_CASE_PAYABLE, "0"),
            }:
                return False
            return (
                str(row["case_id"]) == str(expected["case_id"])
                and str(row["entitlement_ref"]) == f"case_active:{expected['case_id']}"
                and str(row["asset"]) == "POL"
                and str(row["expected_value"]) == payable
                and str(economic["principal_id"]) == str(expected["principal_id"])
                and str(economic["purpose"]) == "CASE"
                and str(economic["case_id"]) == str(expected["case_id"])
                and str(economic["nominal_value"]) == CASE_NOMINAL_VALUE
            )

        return False

    def _bind_idempotency(
        self, *, idempotency_key: str, operation: str, payload: dict[str, Any]
    ) -> None:
        key = str(idempotency_key).strip()
        if not key:
            raise EvidencePaymentError(
                "IDEMPOTENCY_KEY_REQUIRED", "Payment idempotency key is required"
            )
        if not str(payload.get("request_id", "")).strip():
            raise EvidencePaymentError(
                "REQUEST_ID_REQUIRED", "Payment request_id is required"
            )

        fingerprint = hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                binding = c.execute(
                    "SELECT * FROM payment_idempotency_bindings WHERE idempotency_key=?",
                    (key,),
                ).fetchone()
                if binding:
                    if (
                        str(binding["operation"]) != operation
                        or str(binding["request_fingerprint"]) != fingerprint
                    ):
                        raise EvidencePaymentError(
                            "IDEMPOTENCY_CONFLICT",
                            "Idempotency key is already bound to a different payment request",
                        )
                    c.execute("COMMIT")
                    return

                existing = c.execute(
                    "SELECT * FROM payment_intents WHERE idempotency_key=?", (key,)
                ).fetchone()
                if existing and not self._legacy_existing_matches(
                    c, operation=operation, payload=payload, row=existing
                ):
                    raise EvidencePaymentError(
                        "IDEMPOTENCY_CONFLICT",
                        "Existing idempotency key does not match this payment request",
                    )

                c.execute(
                    "INSERT INTO payment_idempotency_bindings VALUES(?,?,?,?)",
                    (key, operation, fingerprint, _now()),
                )
                c.execute("COMMIT")
            except Exception:
                if c.in_transaction:
                    c.execute("ROLLBACK")
                raise

    def _existing_by_key(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM payment_intents WHERE idempotency_key=?",
                (str(idempotency_key).strip(),),
            ).fetchone()
        return dict(row) if row else None

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
        return super().create_payment_intent(
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
            raise EvidencePaymentError(
                "PRINCIPAL_REQUIRED", "SIC-ID principal is required"
            )
        operation, payload = self._activation_payload(
            principal_id=principal_id,
            payer=payer,
            request_id=request_id,
            ttl_seconds=ttl_seconds,
        )
        self._bind_idempotency(
            idempotency_key=idempotency_key, operation=operation, payload=payload
        )
        existing = self._existing_by_key(idempotency_key)
        if existing:
            return self.get_intent(existing["intent_id"])
        return super().create_activation_intent(
            principal_id=principal_id,
            payer=payer,
            request_id=request_id,
            idempotency_key=idempotency_key,
            ttl_seconds=ttl_seconds,
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
        existing = self._existing_by_key(idempotency_key)
        if existing:
            return self.get_intent(existing["intent_id"])
        return super().create_case_payment_intent(
            principal_id=principal_id,
            case_id=case_id,
            payer=payer,
            request_id=request_id,
            idempotency_key=idempotency_key,
            ttl_seconds=ttl_seconds,
        )

    def get_idempotency_binding(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._connect() as c:
            row = c.execute(
                "SELECT * FROM payment_idempotency_bindings WHERE idempotency_key=?",
                (str(idempotency_key).strip(),),
            ).fetchone()
        return dict(row) if row else None
