"""Protected same-origin transport adapter for CHAT02 Evidence/Payment authority.

Transport only: this module does not create a second Evidence/payment/settlement
truth. It exposes the already-canonical TrustedEvidencePaymentRuntimeFacade to
the sandbox/test HTTP bridge. Browser-controlled authority fields are rejected,
MIME type is detected server-side from bytes, RPC provider identities/endpoints
are server configuration, and no signing or transaction submission exists here.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

import httpx

from evidence_payment import (
    EvidencePaymentEngine,
    EvidencePaymentError,
    TrustedEvidencePaymentRuntimeFacade,
    TrustedPolygonRPCAdapter,
)

CHAT02_HTTP_TRANSPORT_VERSION = "1.0"
MAX_EVIDENCE_BYTES = 25_000_000

_FORBIDDEN_AUTHORITY_KEYS = frozenset(
    {
        "chain_id", "chainId", "asset", "expected_value", "expectedValue",
        "treasury", "treasury_address", "treasuryAddress", "provider_ids",
        "providerIds", "providers", "authorization", "consent_id", "consentId",
        "mime_detected", "mimeDetected", "uploader", "entitlement_ref",
        "entitlementRef", "receipt_status", "receiptStatus", "block_hash",
        "blockHash", "finalized_block_number", "finalizedBlockNumber",
    }
)
_FORBIDDEN_EVIDENCE_HEADERS = frozenset(
    {
        "x-caid-authorization", "x-caid-consent-id", "x-caid-uploader",
        "x-caid-mime-detected", "x-caid-entitlement-ref", "x-caid-provider-ids",
    }
)


def detect_evidence_mime(content: bytes) -> str:
    """Detect the only three MVP Evidence MIME types from file signatures."""
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    raise EvidencePaymentError("MIME_REJECTED", "Evidence bytes are not an allowed MIME type")


def _declared_mime(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidencePaymentError("MIME_REJECTED", "Declared Evidence MIME type is required")
    return value.split(";", 1)[0].strip().lower()


def _filename(value: Any) -> str:
    if not isinstance(value, str):
        raise EvidencePaymentError("EVIDENCE_FILENAME_REQUIRED", "Evidence filename is required")
    name = value.strip()
    if not name or len(name) > 255 or "/" in name or "\\" in name or name in {".", ".."}:
        raise EvidencePaymentError("EVIDENCE_FILENAME_INVALID", "Evidence filename is invalid")
    return name


def _reject_authority_fields(payload: Mapping[str, Any]) -> None:
    forbidden = sorted(key for key in payload if key in _FORBIDDEN_AUTHORITY_KEYS)
    if forbidden:
        raise EvidencePaymentError(
            "CALLER_AUTHORITY_FORBIDDEN",
            "Browser payload attempted to supply server-owned Evidence/payment authority fields",
        )


def _safe_rpc_url(value: str) -> str:
    text = str(value).strip()
    parsed = urlparse(text)
    if parsed.scheme == "https" and parsed.hostname:
        return text
    if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        return text
    raise EvidencePaymentError(
        "RPC_PROVIDER_CONFIG_INVALID",
        "RPC endpoints must use HTTPS, except explicit loopback sandbox endpoints",
    )


@dataclass(frozen=True)
class Chat02TransportConfig:
    private_root: Path
    evidence_consent_id: str
    rpc_provider_urls: Mapping[str, str]

    @classmethod
    def build(
        cls,
        *,
        private_root: str | Path,
        static_root: str | Path,
        evidence_consent_id: str,
        rpc_provider_urls: Mapping[str, str],
    ) -> "Chat02TransportConfig":
        private = Path(private_root).expanduser().resolve()
        static = Path(static_root).expanduser().resolve()
        if not str(evidence_consent_id).strip():
            raise EvidencePaymentError("CONSENT_REQUIRED", "Server Evidence consent binding is required")
        try:
            private.relative_to(static)
        except ValueError:
            pass
        else:
            raise EvidencePaymentError("PUBLIC_STORAGE_FORBIDDEN", "Evidence root must be outside static webroot")
        urls = {str(k).strip(): _safe_rpc_url(str(v)) for k, v in dict(rpc_provider_urls).items()}
        if len(urls) < 2 or any(not key for key in urls) or len(set(urls.values())) != len(urls):
            raise EvidencePaymentError(
                "RUNTIME_PROVIDER_QUORUM",
                "At least two distinct server-configured RPC endpoints are required",
            )
        return cls(private_root=private, evidence_consent_id=str(evidence_consent_id).strip(), rpc_provider_urls=urls)


class Chat02HTTPTransport:
    """Transport-only wrapper around the canonical CHAT02 runtime facade."""

    def __init__(
        self,
        *,
        master_db: str | Path,
        static_root: str | Path,
        private_root: str | Path,
        evidence_consent_id: str,
        rpc_provider_urls: Mapping[str, str],
        core_runtime: Any,
        rpc_call: Callable[[str, str, list[Any]], Any] | None = None,
    ):
        self.config = Chat02TransportConfig.build(
            private_root=private_root,
            static_root=static_root,
            evidence_consent_id=evidence_consent_id,
            rpc_provider_urls=rpc_provider_urls,
        )
        self.core_runtime = core_runtime
        self.engine = EvidencePaymentEngine(master_db, self.config.private_root)
        self._http_client: httpx.Client | None = None
        self.rpc_call = rpc_call or self._rpc_call
        self.rpc_adapter = TrustedPolygonRPCAdapter(self.engine, self.rpc_call)
        self.facade = TrustedEvidencePaymentRuntimeFacade(
            engine=self.engine,
            rpc_adapter=self.rpc_adapter,
            resolve_principal=self._resolve_principal,
            authorize_case=self._authorize_case,
            resolve_evidence_grant=self._resolve_evidence_grant,
            provider_ids=tuple(self.config.rpc_provider_urls.keys()),
        )

    def close(self) -> None:
        if self._http_client is not None:
            self._http_client.close()
            self._http_client = None

    def _resolve_principal(self, session_id: str) -> Mapping[str, Any]:
        principal = self.core_runtime._principal(session_id)
        return {
            **dict(principal),
            "principal_id": principal.get("sic_id") or principal.get("principal_id"),
            "session_id": principal.get("session_id") or session_id,
        }

    def _authorize_case(self, principal: Mapping[str, Any], case_id: str) -> bool:
        try:
            self.core_runtime.core.resume_case(
                session_id=str(principal["session_id"]),
                sic_id=str(principal.get("sic_id") or principal["principal_id"]),
                case_id=case_id,
            )
            return True
        except Exception:
            return False

    def _resolve_evidence_grant(self, principal: Mapping[str, Any], case_id: str) -> Mapping[str, Any]:
        # Sandbox/test consent is explicit server configuration. The browser may
        # never send or override authorization/consent/uploader truth.
        return {
            "uploader": str(principal["principal_id"]),
            "consent_id": self.config.evidence_consent_id,
            "authorization": "OWNER",
            "case_id": case_id,
        }

    def _rpc_call(self, provider_id: str, method: str, params: list[Any]) -> Any:
        url = self.config.rpc_provider_urls.get(provider_id)
        if not url:
            raise EvidencePaymentError("RPC_PROVIDER_CONFIG_INVALID", "Unknown server RPC provider")
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=httpx.Timeout(8.0, connect=4.0), follow_redirects=False)
        try:
            response = self._http_client.post(
                url,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise EvidencePaymentError("RPC_UNAVAILABLE", "RPC provider call failed") from exc
        if not isinstance(payload, Mapping):
            raise EvidencePaymentError("RPC_MALFORMED", "RPC provider returned malformed JSON")
        return dict(payload)

    @staticmethod
    def _payload(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise EvidencePaymentError("INVALID_JSON", "JSON object required")
        result = dict(payload)
        _reject_authority_fields(result)
        return result

    @staticmethod
    def _required(payload: Mapping[str, Any], key: str, code: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise EvidencePaymentError(code, f"{key} is required")
        return value.strip()

    def quote(self, *, session_id: str) -> dict[str, Any]:
        return self.facade.quote(session_id=session_id)

    def payment_status(self, *, session_id: str, intent_id: str) -> dict[str, Any]:
        return self.facade.payment_status(session_id=session_id, intent_id=intent_id)

    def create_activation_intent(self, *, session_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = self._payload(payload)
        return self.facade.create_activation_intent(
            session_id=session_id,
            payer=self._required(body, "payer", "PAYER_INVALID"),
            request_id=self._required(body, "requestId", "REQUEST_ID_REQUIRED"),
            idempotency_key=self._required(body, "idempotencyKey", "IDEMPOTENCY_KEY_REQUIRED"),
            ttl_seconds=900,
        )

    def create_case_intent(self, *, session_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = self._payload(payload)
        return self.facade.create_case_intent(
            session_id=session_id,
            case_id=self._required(body, "caseId", "CASE_REQUIRED"),
            payer=self._required(body, "payer", "PAYER_INVALID"),
            request_id=self._required(body, "requestId", "REQUEST_ID_REQUIRED"),
            idempotency_key=self._required(body, "idempotencyKey", "IDEMPOTENCY_KEY_REQUIRED"),
            ttl_seconds=900,
        )

    def settle(self, *, session_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = self._payload(payload)
        return self.facade.settle_tx_hash(
            session_id=session_id,
            intent_id=self._required(body, "intentId", "INTENT_REQUIRED"),
            tx_hash=self._required(body, "txHash", "TX_HASH_INVALID"),
        )

    def store_evidence(
        self,
        *,
        session_id: str,
        headers: Mapping[str, Any],
        content: bytes,
    ) -> dict[str, Any]:
        lowered = {str(k).lower(): v for k, v in headers.items()}
        if any(name in lowered for name in _FORBIDDEN_EVIDENCE_HEADERS):
            raise EvidencePaymentError(
                "CALLER_AUTHORITY_FORBIDDEN",
                "Browser headers attempted to supply server-owned Evidence authority fields",
            )
        if not isinstance(content, bytes) or not content:
            raise EvidencePaymentError("EVIDENCE_EMPTY", "Evidence bytes are required")
        if len(content) > MAX_EVIDENCE_BYTES:
            raise EvidencePaymentError("OVERSIZED", "Evidence exceeds size limit")
        case_id = self._required(lowered, "x-caid-case-id", "CASE_REQUIRED")
        original_name = _filename(lowered.get("x-caid-filename"))
        declared = _declared_mime(lowered.get("content-type"))
        detected = detect_evidence_mime(content)
        parent = lowered.get("x-caid-parent-evidence-id")
        reason = str(lowered.get("x-caid-reason") or "UPLOAD").strip() or "UPLOAD"
        return self.facade.store_private_evidence(
            session_id=session_id,
            case_id=case_id,
            content=content,
            original_name=original_name,
            mime_declared=declared,
            mime_detected=detected,
            parent_evidence_id=str(parent).strip() if parent else None,
            reason=reason[:100],
        )


def parse_rpc_provider_json(value: str) -> dict[str, str]:
    try:
        parsed = json.loads(value)
    except Exception as exc:
        raise EvidencePaymentError("RPC_PROVIDER_CONFIG_INVALID", "RPC provider configuration is invalid") from exc
    if not isinstance(parsed, Mapping):
        raise EvidencePaymentError("RPC_PROVIDER_CONFIG_INVALID", "RPC provider configuration is invalid")
    return {str(k): str(v) for k, v in parsed.items()}


__all__ = [
    "CHAT02_HTTP_TRANSPORT_VERSION",
    "MAX_EVIDENCE_BYTES",
    "Chat02HTTPTransport",
    "Chat02TransportConfig",
    "detect_evidence_mime",
    "parse_rpc_provider_json",
]
