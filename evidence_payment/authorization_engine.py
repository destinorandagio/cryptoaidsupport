"""CHAT02 fail-closed Evidence consent/authorization gate for the 48H MVP.

This layer remains inside the single CHAT02 Evidence/Payment/Entitlement
authority. It rejects any Evidence upload whose authorization is not an exact,
versioned allowed state or whose consent binding is blank, before private bytes or
Evidence rows can be created. Payment economics are inherited unchanged; the
canonical finality boundary treats a transaction in the latest finalized block as
finalized, while provider disagreement remains fail-closed.
"""
from __future__ import annotations

from typing import Any

from .engine import EvidencePaymentError, _block_number
from .idempotency_alias_engine import EvidencePaymentEngine as _IdempotentEvidencePaymentEngine

EVIDENCE_AUTHORIZATION_CONTRACT_VERSION = "1.0"
FINALITY_CONTRACT_VERSION = "1.1"
# These are the only authorizing states used by the current CHAT02 contract and
# one-head Core/Admin golden fixture. The comparison is exact and case-sensitive.
EVIDENCE_AUTHORIZATION_ALLOWED_STATES = frozenset({"ALLOW", "OWNER"})


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

    @staticmethod
    def _provider_finality(observation, provider_observations):
        """Classify finality against each provider's latest finalized head.

        A transaction included in block N is finalized when the provider reports
        its latest finalized block as N or greater. Equality is therefore final,
        not pending. Mixed provider decisions remain MANUAL_REVIEW.
        """
        try:
            tx_block_number = _block_number(observation.get("block_number"))
        except (TypeError, ValueError):
            return "MANUAL_REVIEW", []

        records = []
        decisions = []
        for provider in provider_observations:
            try:
                provider_tx_block = _block_number(provider.get("tx_block_number"))
                finalized_block = _block_number(provider.get("finalized_block_number"))
            except (TypeError, ValueError):
                return "MANUAL_REVIEW", []
            if provider_tx_block != tx_block_number:
                return "MANUAL_REVIEW", []
            final = finalized_block >= tx_block_number
            decisions.append(final)
            records.append(
                {
                    "provider_id": str(provider["provider_id"]).strip(),
                    "tx_block_number": provider_tx_block,
                    "finalized_block_number": finalized_block,
                    "finalized": final,
                }
            )

        if all(decisions):
            return "SETTLED", records
        if not any(decisions):
            return "FINALITY_PENDING", records
        return "MANUAL_REVIEW", records

    def store_evidence(self, *, authorization: str, consent_id: str, **kwargs):
        authorization = validate_evidence_authorization(authorization)
        consent_id = validate_consent_binding(consent_id)
        return super().store_evidence(
            authorization=authorization,
            consent_id=consent_id,
            **kwargs,
        )
