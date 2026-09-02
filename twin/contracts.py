from __future__ import annotations

POLYGON_CHAIN_ID = 137
TWIN_SCHEMA_VERSION = "1.1.0"
DAPPMAP_CONTRACT_VERSION = "1.1.0"
WALLET_MATRIX_VERSION = "1.1.0"
CORE_CONSUMER_CONTRACT_VERSION = "0.3.13"

# CHAT03 consumes Core; it never creates a second principal or identity registry.
CORE_BOUNDARY = {
    "durable_principal": "SIC-ID",
    "wallet_role": "REVOCABLE_ACTION_PAYMENT_RESOURCE",
    "consumer_mode": "READ_DERIVED_INPUT_ONLY_NO_CORE_TRUTH_WRITE",
    "unknown_project_status": "USER_SUBMITTED_TO_VERIFY",
    "chain_id": POLYGON_CHAIN_ID,
}

TRUTH_LABELS = ("LIVE", "CACHED", "HISTORICAL", "DERIVED", "TO_VERIFY", "UNKNOWN")
TWIN_STATES = ("KNOWN", "VERIFIED", "SUPPORTED", "TO_VERIFY", "UNKNOWN")
CACHE_STATES = ("MISS", "FRESH", "STALE", "BYPASS", "NOT_APPLICABLE")

WALLET_MATRIX = {
    "version": WALLET_MATRIX_VERSION,
    "eip6963": {
        "target": True,
        "mode": "injected-discovery",
        "selection": "EXPLICIT_USER_SELECTION",
        "metadata_trust": "UNTRUSTED_DISPLAY_METADATA",
        "duplicate_policy": "DEDUPE_PROVIDER_IDENTITY_WITHOUT_AUTO_PICK",
    },
    "metamask": {"target": True, "mode": "eip6963/injected/mobile", "real_device": "HUMAN_GATE"},
    "tokenpocket": {"target": True, "mode": "eip6963/injected/mobile-inapp", "real_device": "HUMAN_GATE"},
    "walletconnect_reown": {
        "target": True,
        "mode": "external-wallet-qr-deeplink",
        "project_config": "NON_SECRET_CLIENT_CONFIG_ONLY",
        "real_device": "HUMAN_GATE",
    },
    "chain_id": POLYGON_CHAIN_ID,
    "custody": "NON_CUSTODIAL",
    "durable_identity": "SIC-ID_NOT_WALLET",
    "forbidden_storage": ["seed", "mnemonic", "private_key", "raw_signing_material"],
    "allowed_user_actions": {
        "personal_sign": "READABLE_CHALLENGE_AND_EXPLICIT_USER_CONFIRMATION",
        "eth_sendTransaction": "PERSISTED_INTENT_AND_EXPLICIT_USER_CONFIRMATION",
    },
    "forbidden_rpc_actions": ["eth_sendRawTransaction", "wallet_importRawKey"],
    "session_events": ["accountsChanged", "chainChanged", "disconnect", "connect"],
    "event_policy": "FAIL_CLOSED_AND_REVALIDATE_SESSION",
    "chain_switch_policy": "POST_VERIFY_ETH_CHAINID_EQUALS_0x89",
    "connect_is_authentication": False,
    "signing_policy": "USER_CONFIRMED_ONLY",
}

RPC_HEALTH_CONTRACT = {
    "owner": "CHAT10",
    "consumer": "CHAT03",
    "chain_id": POLYGON_CHAIN_ID,
    "required_observation": ["provider_id", "observed_at", "latency_ms", "chain_id", "result", "source"],
    "live_rule": "RPC data is LIVE only after current request-time health evidence; otherwise CACHED/TO_VERIFY/UNKNOWN.",
    "no_secret_config": True,
}

KNOWLEDGE_CONTEXT_CONTRACT = {
    "owner": "CHAT06",
    "consumer": "CHAT03",
    "required": ["pack_id", "version", "status", "provenance", "generated_at"],
    "allowed_status": ["VERIFIED", "SUPPORTED", "CANDIDATE", "UNVERIFIED", "TO_VERIFY"],
    "promotion_rule": "CHAT03_NEVER_PROMOTES_CANDIDATE_OR_UNVERIFIED_TO_VERIFIED",
    "authority": "DERIVED_CONTEXT_ONLY_NOT_FINANCIAL_OR_CORE_AUTHORITY",
}

DAPPMAP_CONTRACT = {
    "version": DAPPMAP_CONTRACT_VERSION,
    "node_types": ["project", "chain", "contract", "asset", "wallet", "evidence", "case"],
    "edge_types": [
        "deployed_on", "uses_contract", "holds_asset", "migrated_to", "successor_of",
        "evidence_for", "relevant_to_case", "transacted_with",
    ],
    "required_epistemic_fields": [
        "source", "source_date", "observed_at", "confidence", "cache_state", "truth_label", "status", "version",
    ],
    "numeric_fact_rule": "Every numeric fact requires source, source_date, confidence, cache_state and truth_label.",
    "live_rule": "Never label data LIVE unless runtime freshness/health is actually verified.",
}
