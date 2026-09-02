"""CHAT02 trusted runtime facade for the 48H MVP Golden Path.

This is the only browser/runtime-facing adapter allowed to invoke CHAT02
Evidence/Payment/Entitlement authority. It deliberately owns no HTTP routes and
performs no signing or transaction submission. CHAT10 may wrap this facade in a
same-origin transport, while Core remains the SIC-ID/Case state authority.

Security boundary:
- principal and Case ownership are resolved by server callbacks;
- Evidence authorization/consent/uploader are resolved server-side;
- payment economics are created only by the canonical 50/450/500 engine;
- RPC provider identities are fixed at construction time and never supplied by
  the browser;
- settlement accepts only an opaque intent_id plus tx_hash and delegates all
  economic/finality truth to TrustedPolygonRPCAdapter;
- a settled Case produces a read-only Core activation claim. The facade never
  writes Core Case state, so SETTLED remains distinct from CASE_ACTIVE.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Callable, Iterable, Mapping

from .authorization_engine import EvidencePaymentEngine
from .engine import CHAIN_ID, EvidencePaymentError
from .rpc_adapter import TrustedPolygonRPCAdapter

RUNTIME_FACADE_VERSION = "1.0"
CORE_ACTIVATION_CLAIM_VERSION = "1.0"
_EVM_ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")
_TX_HASH = re.compile(r"^0x[a-fA-F0-9]{64}$")

PrincipalResolver = Callable[[str], Mapping[str, Any]]
CaseAuthorizer = Callable[[Mapping[str, Any], str], bool]
EvidenceGrantResolver = Callable[[Mapping[str, Any], str], Mapping[str, Any]]


@dataclass(frozen=True)
class RuntimeAuthorityConfig:
    """Server-owned dependencies for the CHAT02 runtime boundary."""

    provider_ids: tuple[str, ...]

    @classmethod
    def build(cls, provider_ids: Iterable[str]) -> "RuntimeAuthorityConfig":
        ids = tuple(str(value).strip() for value in provider_ids)
        if len(ids) < 2 or any(not value for value in ids) or len(set(ids)) != len(ids):
            raise EvidencePaymentError(
                "RUNTIME_PROVIDER_QUORUM",
                "At least two distinct server-configured RPC provider identities are required",
            )
        return cls(provider_ids=ids)


class TrustedEvidencePaymentRuntimeFacade:
    """Fail-closed CHAT02 facade for a same-origin sandbox/test runtime."""

    def __init__(
        self,
        *,
        engine: EvidencePaymentEngine,
        rpc_adapter: TrustedPolygonRPCAdapter,
        resolve_principal: PrincipalResolver,
        authorize_case: CaseAuthorizer,
        resolve_evidence_grant: EvidenceGrantResolver,
        provider_ids: Iterable[str],
    ):
        if rpc_adapter.engine is not engine:
            raise EvidencePaymentError(
                "RUNTIME_ENGINE_MISMATCH",
                "RPC adapter and runtime facade must share the canonical CHAT02 engine",
            )
        self.engine = engine
        self.rpc_adapter = rpc_adapter
        self.resolve_principal = resolve_principal
        self.authorize_case = authorize_case
        self.resolve_evidence_grant = resolve_evidence_grant
        self.authority = RuntimeAuthorityConfig.build(provider_ids)

    @staticmethod
    def _token(value: Any, code: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise EvidencePaymentError(code, "Required trusted runtime token is missing")
        return value.strip()

    @staticmethod
    def _payer(value: Any) -> str:
        if not isinstance(value, str) or not _EVM_ADDRESS.fullmatch(value.strip()):
            raise EvidencePaymentError("PAYER_INVALID", "Payer must be a canonical EVM address")
        return value.strip().lower()

    @staticmethod
    def _tx_hash(value: Any) -> str:
        if not isinstance(value, str) or not _TX_HASH.fullmatch(value.strip()):
            raise EvidencePaymentError("TX_HASH_INVALID", "Transaction hash is malformed")
        return value.strip().lower()

    def _principal(self, session_id: str) -> dict[str, Any]:
        session = self._token(session_id, "SESSION_REQUIRED")
        try:
            value = self.resolve_principal(session)
        except EvidencePaymentError:
            raise
        except Exception as exc:
            raise EvidencePaymentError("SESSION_REQUIRED", "Trusted principal resolution failed") from exc
        if not isinstance(value, Mapping):
            raise EvidencePaymentError("SESSION_REQUIRED", "Trusted principal resolution failed")
        principal_id = str(value.get("principal_id") or value.get("sic_id") or "").strip()
        if not principal_id:
            raise EvidencePaymentError("SESSION_REQUIRED", "Trusted principal resolution failed")
        result = dict(value)
        result["principal_id"] = principal_id
        result["session_id"] = session
        return result

    def _case(self, principal: Mapping[str, Any], case_id: str) -> str:
        case = self._token(case_id, "CASE_REQUIRED")
        try:
            allowed = bool(self.authorize_case(principal, case))
        except EvidencePaymentError:
            raise
        except Exception as exc:
            raise EvidencePaymentError("CASE_FORBIDDEN", "Case authorization failed closed") from exc
        if not allowed:
            raise EvidencePaymentError("CASE_FORBIDDEN", "Case does not belong to the trusted principal")
        return case

    def _economic_owner(self, principal: Mapping[str, Any], intent_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        intent_key = self._token(intent_id, "INTENT_REQUIRED")
        intent = self.engine.get_intent(intent_key)
        economic = self.engine.get_economic_intent(intent_key)
        if not economic or str(economic.get("principal_id")) != str(principal["principal_id"]):
            raise EvidencePaymentError("INTENT_FORBIDDEN", "Payment intent does not belong to trusted principal")
        if economic.get("purpose") == "CASE":
            self._case(principal, str(economic.get("case_id") or ""))
        elif economic.get("purpose") != "ACTIVATION":
            raise EvidencePaymentError("INTENT_FORBIDDEN", "Generic payment intent is not exposed by the MVP runtime facade")
        return intent, economic

    @staticmethod
    def _intent_projection(intent: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "contract_version": RUNTIME_FACADE_VERSION,
            "intent_id": intent["intent_id"],
            "case_id": intent["case_id"],
            "chain_id": int(intent["chain_id"]),
            "asset": intent["asset"],
            "expected_value": str(intent["expected_value"]),
            "treasury_address": intent["treasury_address"],
            "state": intent["state"],
            "expires_at": intent.get("expires_at"),
            "tx_hash": intent.get("tx_hash"),
            "payment_authority": "CHAT02_EVIDENCE_PAYMENT_ENTITLEMENT",
        }

    def quote(self, *, session_id: str) -> dict[str, Any]:
        principal = self._principal(session_id)
        return {
            "contract_version": RUNTIME_FACADE_VERSION,
            "chain_id": CHAIN_ID,
            "asset": "POL",
            **self.engine.quote_next_case(principal["principal_id"]),
        }

    def store_private_evidence(
        self,
        *,
        session_id: str,
        case_id: str,
        content: bytes,
        original_name: str,
        mime_declared: str,
        mime_detected: str,
        parent_evidence_id: str | None = None,
        reason: str = "UPLOAD",
    ) -> dict[str, Any]:
        principal = self._principal(session_id)
        case = self._case(principal, case_id)
        try:
            grant = self.resolve_evidence_grant(principal, case)
        except EvidencePaymentError:
            raise
        except Exception as exc:
            raise EvidencePaymentError("UNAUTHORIZED", "Evidence grant resolution failed closed") from exc
        if not isinstance(grant, Mapping):
            raise EvidencePaymentError("UNAUTHORIZED", "Evidence grant resolution failed closed")
        uploader = str(grant.get("uploader") or principal["principal_id"]).strip()
        consent_id = grant.get("consent_id")
        authorization = grant.get("authorization")
        result = self.engine.store_evidence(
            case_id=case,
            content=content,
            original_name=original_name,
            mime_declared=mime_declared,
            mime_detected=mime_detected,
            uploader=uploader,
            consent_id=consent_id,
            authorization=authorization,
            parent_evidence_id=parent_evidence_id,
            reason=reason,
        )
        return {
            "contract_version": RUNTIME_FACADE_VERSION,
            "case_id": result["case_id"],
            "evidence_id": result["evidence_id"],
            "version": result["version"],
            "sha256": result["sha256"],
            "status": result["status"],
            "private_storage": True,
        }

    def create_activation_intent(
        self,
        *,
        session_id: str,
        payer: str,
        request_id: str,
        idempotency_key: str,
        ttl_seconds: int = 900,
    ) -> dict[str, Any]:
        principal = self._principal(session_id)
        intent = self.engine.create_activation_intent(
            principal_id=principal["principal_id"],
            payer=self._payer(payer),
            request_id=self._token(request_id, "REQUEST_ID_REQUIRED"),
            idempotency_key=self._token(idempotency_key, "IDEMPOTENCY_KEY_REQUIRED"),
            ttl_seconds=ttl_seconds,
        )
        return self._intent_projection(intent)

    def create_case_intent(
        self,
        *,
        session_id: str,
        case_id: str,
        payer: str,
        request_id: str,
        idempotency_key: str,
        ttl_seconds: int = 900,
    ) -> dict[str, Any]:
        principal = self._principal(session_id)
        case = self._case(principal, case_id)
        intent = self.engine.create_case_payment_intent(
            principal_id=principal["principal_id"],
            case_id=case,
            payer=self._payer(payer),
            request_id=self._token(request_id, "REQUEST_ID_REQUIRED"),
            idempotency_key=self._token(idempotency_key, "IDEMPOTENCY_KEY_REQUIRED"),
            ttl_seconds=ttl_seconds,
        )
        return self._intent_projection(intent)

    def payment_status(self, *, session_id: str, intent_id: str) -> dict[str, Any]:
        principal = self._principal(session_id)
        intent, economic = self._economic_owner(principal, intent_id)
        projection = self._intent_projection(intent)
        projection["purpose"] = economic["purpose"]
        projection["nominal_value"] = economic["nominal_value"]
        projection["credit_applied"] = economic["credit_applied"]
        projection["payable_value"] = economic["payable_value"]
        if intent["state"] == "SETTLED":
            projection["settlement_certificate_id"] = self.engine.get_settlement_certificate(intent["intent_id"])["certificate_id"]
        return projection

    def settle_tx_hash(self, *, session_id: str, intent_id: str, tx_hash: str) -> dict[str, Any]:
        principal = self._principal(session_id)
        intent, economic = self._economic_owner(principal, intent_id)
        result = self.rpc_adapter.settle_from_tx_hash(
            intent_id=intent["intent_id"],
            tx_hash=self._tx_hash(tx_hash),
            provider_ids=self.authority.provider_ids,
        )
        current = self.engine.get_intent(intent["intent_id"])
        response: dict[str, Any] = {
            "contract_version": RUNTIME_FACADE_VERSION,
            "intent_id": current["intent_id"],
            "case_id": current["case_id"],
            "payment_state": current["state"],
            "verdict": result.get("verdict"),
            "entitlement_granted": bool(result.get("entitlement_granted")),
            "case_active": False,
            "core_activation_ready": False,
        }
        if current["state"] != "SETTLED":
            return response

        certificate = self.engine.get_settlement_certificate(current["intent_id"])
        response["settlement_certificate_id"] = certificate["certificate_id"]
        if economic["purpose"] == "ACTIVATION":
            credit = self.engine.get_activation_credit(principal["principal_id"])
            response["credit_effect"] = {
                "amount": credit["amount"] if credit else None,
                "state": credit["state"] if credit else None,
            }
            return response

        claim = {
            "contract_version": CORE_ACTIVATION_CLAIM_VERSION,
            "case_id": current["case_id"],
            "intent_id": current["intent_id"],
            "entitlement_ref": current["entitlement_ref"],
            "settlement_certificate_id": certificate["certificate_id"],
            "payment_state": "SETTLED",
            "case_state_authority": "CORE",
        }
        claim_bytes = json.dumps(claim, sort_keys=True, separators=(",", ":")).encode("utf-8")
        response["core_activation_claim"] = {
            **claim,
            "sha256": hashlib.sha256(claim_bytes).hexdigest(),
        }
        response["core_activation_ready"] = True
        return response


__all__ = [
    "TrustedEvidencePaymentRuntimeFacade",
    "RuntimeAuthorityConfig",
    "RUNTIME_FACADE_VERSION",
    "CORE_ACTIVATION_CLAIM_VERSION",
]
