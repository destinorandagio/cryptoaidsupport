"""CHAT02 fail-closed Evidence consent/authorization gate for the 48H MVP.

This layer remains inside the single CHAT02 Evidence/Payment/Entitlement
authority. It rejects any Evidence upload whose authorization is not the exact,
versioned allow state or whose consent binding is blank, before private bytes or
Evidence rows can be created. Payment/finality/economics are inherited unchanged.
"""
from __future__ import annotations

from typing import Any

from .engine import EvidencePaymentError
from .idempotency_engine import EvidencePaymentEngine as _IdempotentEvidencePaymentEngine

EVIDENCE_AUTHORIZATION_CONTRACT_VERSION = "1.0"
EVIDENCE_AUTHORIZATION_ALLOWED_STATES = frozenset({"ALLOW"})


def validate_evidence_authorization(authorization: Any) -> str:
    if (
        not isinstance(authorization, str)
        or authorization not in EVIDENCE_AUTHORIZATION_ALLOWED_STATES
    ):
        raise EvidencePaymentError(
            "UNAUTHORIZED",
            "Evidence authorization must be an explicit allowed state",
        )
    return authorization


def validate_consent_binding(consent_id: Any) -> str:
    if not isinstance(consent_id, str) or not consent_id.strip():
        raise EvidencePaymentError("CONSENT_REQUIRED", "Consent binding required")
    return consent_id


class EvidencePaymentEngine(_IdempotentEvidencePaymentEngine):
    """Canonical CHAT02 engine with explicit Evidence authorization semantics."""

    def store_evidence(self, *, authorization: str, consent_id: str, **kwargs):
        authorization = validate_evidence_authorization(authorization)
        consent_id = validate_consent_binding(consent_id)
        return super().store_evidence(
            authorization=authorization,
            consent_id=consent_id,
            **kwargs,
        )
