"""Trusted CHAT01 consumer for CHAT02 settlement activation claims.

CHAT02 owns Evidence/payment/settlement/entitlement truth and emits a hash-bound,
read-only activation claim after a Case payment is durably SETTLED. This module
validates that exact claim against the durable CHAT02 rows in the canonical
BLOCKCHAINPLUS-MASTER.sqlite and then asks the canonical CaseEngine to perform
the same-Case ACTIVE transition.

This is deliberately a server-internal boundary. Browser/Admin callers must not
supply entitlement authorization, payment truth, Case ownership, or economic
values through this consumer.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .case_engine import CoreError
from .case_engine_mvp import CaseEngine

CORE_ACTIVATION_CLAIM_CONSUMER_VERSION = "1.0.0"
ACCEPTED_ACTIVATION_CLAIM_VERSION = "1.0"
_ACTIVATION_ACTOR = "CORE_SETTLEMENT_EFFECT"
_ACTIVATION_REASON = "CHAT02 settled Case payment activation claim"
_CLAIM_FIELDS = frozenset(
    {
        "contract_version",
        "case_id",
        "intent_id",
        "entitlement_ref",
        "settlement_certificate_id",
        "payment_state",
        "case_state_authority",
        "sha256",
    }
)
_HASHED_FIELDS = (
    "contract_version",
    "case_id",
    "intent_id",
    "entitlement_ref",
    "settlement_certificate_id",
    "payment_state",
    "case_state_authority",
)


def _required_token(value: Any, code: str = "ACTIVATION_CLAIM_INVALID") -> str:
    if not isinstance(value, str) or not value.strip():
        raise CoreError(code, "activation claim contains an invalid required token", 403)
    return value.strip()


def _canonical_claim_payload(claim: Mapping[str, Any]) -> dict[str, str]:
    if set(claim) != _CLAIM_FIELDS:
        raise CoreError(
            "ACTIVATION_CLAIM_INVALID",
            "activation claim shape does not match the accepted contract",
            403,
        )
    payload = {field: _required_token(claim.get(field)) for field in _HASHED_FIELDS}
    if payload["contract_version"] != ACCEPTED_ACTIVATION_CLAIM_VERSION:
        raise CoreError("ACTIVATION_CLAIM_INVALID", "activation claim version is not accepted", 403)
    if payload["payment_state"] != "SETTLED":
        raise CoreError("ACTIVATION_CLAIM_INVALID", "activation claim is not settled", 403)
    if payload["case_state_authority"] != "CORE":
        raise CoreError("ACTIVATION_CLAIM_INVALID", "activation claim does not preserve Core authority", 403)
    supplied_digest = _required_token(claim.get("sha256")).lower()
    if len(supplied_digest) != 64 or any(ch not in "0123456789abcdef" for ch in supplied_digest):
        raise CoreError("ACTIVATION_CLAIM_INVALID", "activation claim digest is malformed", 403)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected_digest = hashlib.sha256(encoded).hexdigest()
    if not hmac.compare_digest(supplied_digest, expected_digest):
        raise CoreError("ACTIVATION_CLAIM_HASH_MISMATCH", "activation claim digest mismatch", 403)
    return {**payload, "sha256": supplied_digest}


class TrustedActivationClaimConsumer:
    """Validate a CHAT02 settlement claim and activate the canonical existing Case."""

    def __init__(self, db_path: str | Path):
        self.engine = CaseEngine(db_path)

    @staticmethod
    def _activation_idempotency_key(digest: str) -> str:
        return f"core-activation-claim:{digest}"

    @staticmethod
    def _validate_effect_rows(conn, claim: Mapping[str, str], case) -> None:
        required_tables = (
            "payment_intents",
            "entitlement_ledger",
            "settlement_certificates",
            "economic_intents",
        )
        for table in required_tables:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                raise CoreError(
                    "ACTIVATION_EFFECT_NOT_FOUND",
                    "required CHAT02 settlement effect is unavailable",
                    409,
                )

        intent = conn.execute(
            "SELECT * FROM payment_intents WHERE intent_id=?",
            (claim["intent_id"],),
        ).fetchone()
        if (
            not intent
            or intent["case_id"] != claim["case_id"]
            or intent["entitlement_ref"] != claim["entitlement_ref"]
            or intent["state"] != "SETTLED"
            or not intent["tx_hash"]
        ):
            raise CoreError(
                "ACTIVATION_EFFECT_MISMATCH",
                "activation claim does not match the settled payment intent",
                409,
            )

        economic = conn.execute(
            "SELECT * FROM economic_intents WHERE intent_id=?",
            (claim["intent_id"],),
        ).fetchone()
        if (
            not economic
            or economic["purpose"] != "CASE"
            or economic["case_id"] != claim["case_id"]
            or economic["principal_id"] != case["sic_id"]
        ):
            raise CoreError(
                "ACTIVATION_EFFECT_MISMATCH",
                "activation claim is not backed by the Case owner's economic intent",
                409,
            )

        entitlement = conn.execute(
            "SELECT * FROM entitlement_ledger WHERE intent_id=?",
            (claim["intent_id"],),
        ).fetchone()
        if (
            not entitlement
            or entitlement["case_id"] != claim["case_id"]
            or entitlement["entitlement_ref"] != claim["entitlement_ref"]
            or int(entitlement["delta"]) <= 0
        ):
            raise CoreError(
                "ACTIVATION_EFFECT_MISMATCH",
                "activation claim does not match a positive entitlement effect",
                409,
            )

        certificate = conn.execute(
            "SELECT * FROM settlement_certificates WHERE certificate_id=?",
            (claim["settlement_certificate_id"],),
        ).fetchone()
        if (
            not certificate
            or certificate["intent_id"] != claim["intent_id"]
            or certificate["case_id"] != claim["case_id"]
            or certificate["entitlement_ref"] != claim["entitlement_ref"]
            or certificate["tx_hash"] != intent["tx_hash"]
        ):
            raise CoreError(
                "ACTIVATION_EFFECT_MISMATCH",
                "activation claim does not match the settlement certificate",
                409,
            )

        try:
            lineage = json.loads(entitlement["lineage"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise CoreError(
                "ACTIVATION_EFFECT_MISMATCH",
                "entitlement lineage is invalid",
                409,
            ) from exc
        if (
            not isinstance(lineage, dict)
            or lineage.get("intent_id") != claim["intent_id"]
            or lineage.get("settlement_certificate_id") != claim["settlement_certificate_id"]
            or lineage.get("tx_hash") != certificate["tx_hash"]
        ):
            raise CoreError(
                "ACTIVATION_EFFECT_MISMATCH",
                "activation claim does not match entitlement lineage",
                409,
            )

    def consume(self, *, claim: Mapping[str, Any], request_id: str) -> dict[str, Any]:
        if not isinstance(claim, Mapping):
            raise CoreError("ACTIVATION_CLAIM_REQUIRED", "activation claim is required", 400)
        request = _required_token(request_id, "REQUEST_ID_REQUIRED")
        canonical = _canonical_claim_payload(claim)
        idem = self._activation_idempotency_key(canonical["sha256"])

        with self.engine.conn() as conn:
            case = conn.execute(
                "SELECT * FROM core_cases WHERE case_id=?", (canonical["case_id"],)
            ).fetchone()
            if not case:
                raise CoreError("CASE_NOT_FOUND", "activation Case does not exist", 404)
            self._validate_effect_rows(conn, canonical, case)

            prior = conn.execute(
                "SELECT * FROM core_case_events WHERE idempotency_key=?", (idem,)
            ).fetchone()
            if prior:
                if (
                    prior["case_id"] != canonical["case_id"]
                    or prior["new_state"] != "ACTIVE"
                    or prior["authorization"] != "ENTITLEMENT_GRANTED"
                    or prior["audit_event"] != "CASE_STATE_TRANSITION"
                ):
                    raise CoreError(
                        "IDEMPOTENCY_CONFLICT",
                        "activation claim key is bound to another Core effect",
                        409,
                    )
                return {
                    "case_id": prior["case_id"],
                    "previous_state": prior["previous_state"],
                    "state": prior["new_state"],
                    "version": int(prior["case_version"]),
                    "intent_id": canonical["intent_id"],
                    "settlement_certificate_id": canonical["settlement_certificate_id"],
                    "activation_claim_sha256": canonical["sha256"],
                    "idempotent": True,
                }

            if case["state"] != "PAYMENT_VERIFYING":
                raise CoreError(
                    "ACTIVATION_STATE_INVALID",
                    "settled Case activation is allowed only from PAYMENT_VERIFYING",
                    409,
                )
            user_id = case["user_id"]
            expected_version = int(case["version"])

        result = self.engine.transition(
            canonical["case_id"],
            user_id,
            "ACTIVE",
            _ACTIVATION_ACTOR,
            _ACTIVATION_REASON,
            request,
            idem,
            "ENTITLEMENT_GRANTED",
            expected_version,
        )
        return {
            **result,
            "intent_id": canonical["intent_id"],
            "settlement_certificate_id": canonical["settlement_certificate_id"],
            "activation_claim_sha256": canonical["sha256"],
            "idempotent": False,
        }


__all__ = [
    "ACCEPTED_ACTIVATION_CLAIM_VERSION",
    "CORE_ACTIVATION_CLAIM_CONSUMER_VERSION",
    "TrustedActivationClaimConsumer",
]
