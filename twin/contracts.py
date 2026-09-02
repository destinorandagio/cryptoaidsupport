from __future__ import annotations

POLYGON_CHAIN_ID = 137
TWIN_SCHEMA_VERSION = "1.0.0"
DAPPMAP_CONTRACT_VERSION = "1.0.0"
WALLET_MATRIX_VERSION = "1.0.0"

WALLET_MATRIX = {
    "eip6963": {"target": True, "mode": "injected-discovery"},
    "metamask": {"target": True, "mode": "eip6963/injected"},
    "tokenpocket": {"target": True, "mode": "eip6963/injected/mobile"},
    "walletconnect_reown": {"target": True, "mode": "qr/deeplink"},
    "chain_id": POLYGON_CHAIN_ID,
    "custody": "NON_CUSTODIAL",
    "forbidden_storage": ["seed", "private_key"],
    "signing_policy": "USER_CONFIRMED_ONLY",
}

DAPPMAP_CONTRACT = {
    "version": DAPPMAP_CONTRACT_VERSION,
    "node_types": ["project", "chain", "contract", "asset", "wallet", "evidence", "case"],
    "edge_types": ["deployed_on", "uses_contract", "holds_asset", "migrated_to", "successor_of", "evidence_for", "relevant_to_case", "transacted_with"],
    "required_epistemic_fields": ["source", "source_date", "observed_at", "confidence", "freshness", "status", "version"],
    "live_rule": "Never label data LIVE unless runtime freshness/health is actually verified.",
}
