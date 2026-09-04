from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CONTEXT_PACK_VERSION = "1.0.0"

STATUS_MAP = {
    "VERIFIED": "VERIFIED",
    "SUPPORTED": "SUPPORTED",
    "UNVERIFIED": "TO_VERIFY",
    "CANDIDATE": "TO_VERIFY",
    "ANALYSIS": "TO_VERIFY",
    "COMMUNITY_REPORT": "TO_VERIFY",
    "CONTRADICTED": "TO_VERIFY",
    "UNKNOWN": "UNKNOWN",
    "TO_VERIFY": "TO_VERIFY",
    "VERIFIED_PRIMARY_SOURCE": "VERIFIED",
    "HIGH_CONFIDENCE": "SUPPORTED",
    "DRAFT": "TO_VERIFY",
    "UNRESOLVED": "TO_VERIFY",
    "CONFLICT": "TO_VERIFY",
    "OBSOLETE": "UNKNOWN",
}

PUBLIC_ALLOW = {"VERIFIED_PRIMARY_SOURCE", "VERIFIED", "HIGH_CONFIDENCE"}
PUBLIC_WITH_LABEL = {"ANALYSIS"}
PUBLIC_DENY = {"DRAFT", "UNRESOLVED", "CONFLICT", "OBSOLETE"}

KNOWLEDGE_CONTEXT_CONTRACT = {
    "version": CONTEXT_PACK_VERSION,
    "owner": "CHAT06",
    "consumers": ["CHAT03", "CHAT01", "CHAT07", "CHAT08", "CHAT09"],
    "required": ["pack_id", "version", "status", "provenance", "generated_at"],
    "allowed_status": sorted(STATUS_MAP),
    "status_map": STATUS_MAP,
    "promotion_rule": "CONSUMERS_NEVER_PROMOTE_DERIVED_CONTEXT_TO_DOMAIN_AUTHORITY",
    "candidate_rule": "UNVERIFIED_CANDIDATE_ANALYSIS_COMMUNITY_CONTRADICTED_CONFLICT_TO_TO_VERIFY",
    "private_evidence_rule": "PRIVATE_USER_EVIDENCE_NEVER_ENTERS_PUBLIC_CONTEXT_PACK",
    "authority": "DERIVED_CONTEXT_ONLY_NOT_FINANCIAL_CORE_OR_TWIN_AUTHORITY",
}


def validate_context_pack(pack: Mapping[str, Any]) -> dict[str, Any]:
    missing = set(KNOWLEDGE_CONTEXT_CONTRACT["required"]) - set(pack)
    if missing:
        raise ValueError(f"context pack missing fields: {sorted(missing)}")
    pack_id = str(pack["pack_id"]).strip()
    version = str(pack["version"]).strip()
    generated_at = str(pack["generated_at"]).strip()
    incoming_status = str(pack["status"])
    provenance = pack["provenance"]
    if not pack_id or not version or not generated_at:
        raise ValueError("context pack id/version/generated_at required")
    if incoming_status not in STATUS_MAP:
        raise ValueError("unsupported context pack status")
    if not isinstance(provenance, Mapping):
        raise ValueError("context pack provenance must be an object")
    source = str(provenance.get("source", "")).strip()
    if not source:
        raise ValueError("context pack provenance source required")
    if provenance.get("private_evidence") is True:
        raise ValueError("private evidence cannot enter a public/derived context pack")
    safe_status = STATUS_MAP[incoming_status]
    if safe_status == "TO_VERIFY":
        truth_label = "TO_VERIFY"
    elif safe_status == "UNKNOWN":
        truth_label = "UNKNOWN"
    else:
        truth_label = "DERIVED"
    return {
        "pack_id": pack_id,
        "version": version,
        "source_status": incoming_status,
        "status": safe_status,
        "truth_label": truth_label,
        "generated_at": generated_at,
        "provenance": dict(provenance),
        "payload": pack.get("payload", {}),
    }


def publishability(status: str) -> str:
    if status in PUBLIC_ALLOW:
        return "ALLOW"
    if status in PUBLIC_WITH_LABEL:
        return "ALLOW_WITH_ANALYSIS_LABEL"
    if status in PUBLIC_DENY:
        return "DENY"
    return "TO_VERIFY"
