import pytest

from twin.contracts import (
    CHAT06_STATUS_MAP,
    CORE_BOUNDARY,
    CORE_CONSUMER_CONTRACT_VERSION,
    DAPPMAP_CONTRACT,
    POLYGON_CHAIN_ID,
    RPC_HEALTH_CONTRACT,
    WALLET_MATRIX,
)
from twin.engine import DigitalTwinEngine, NumericFact, TwinRecord, TwinStatus


def verified_provenance():
    return [DigitalTwinEngine.provenance(
        "upstream-canon", 0.99, "v1", source_date="2026-09-02",
        cache_state="FRESH", truth_label="LIVE",
    )]


def test_alias_resolution_and_old_name():
    engine = DigitalTwinEngine([
        TwinRecord("p1", "New Project", {"Old Project"}, 137, status=TwinStatus.VERIFIED, provenance=verified_provenance())
    ])
    assert engine.resolve_one("old-project").twin_id == "p1"


def test_ticker_and_family_resolution():
    engine = DigitalTwinEngine([
        TwinRecord("p1", "Alpha Project", ticker="ALP", family_id="family-alpha", chain_id=137)
    ])
    assert engine.resolve_one("ALP").twin_id == "p1"
    assert engine.resolve_one("family-alpha").twin_id == "p1"


def test_same_name_different_chain_requires_disambiguation():
    engine = DigitalTwinEngine([
        TwinRecord("p1", "Alpha", chain_id=137),
        TwinRecord("p2", "Alpha", chain_id=1),
    ])
    with pytest.raises(ValueError):
        engine.resolve_one("Alpha")
    assert engine.resolve_one("Alpha", chain_id=137).twin_id == "p1"


def test_contract_resolution_is_case_insensitive():
    address = "0x" + "aB" * 20
    engine = DigitalTwinEngine([TwinRecord("p1", "Alpha", chain_id=137, contracts={address})])
    assert engine.resolve_one(address.upper().replace("0X", "0x")).twin_id == "p1"


def test_search_miss_is_to_verify_not_verified_and_case_can_continue():
    result = DigitalTwinEngine().search_or_candidate("Unknown")
    assert result["state"] == "TO_VERIFY"
    assert result["candidate_status"] == "USER_SUBMITTED_TO_VERIFY"
    assert result["truth_label"] == "TO_VERIFY"
    assert result["case_available"] is True
    assert result["promoted"] is False


def test_verified_record_requires_provenance():
    with pytest.raises(ValueError):
        DigitalTwinEngine([TwinRecord("p1", "Alpha", status=TwinStatus.VERIFIED)])


def test_numeric_facts_require_source_date_confidence_and_cache_state():
    fact = NumericFact(17604, "registry-snapshot", "2026-09-01", 0.95, "FRESH", "CACHED", "snapshot-1")
    assert fact.value == 17604
    with pytest.raises(ValueError):
        NumericFact(17604, "registry-snapshot", "", 0.95, "FRESH", "CACHED", "snapshot-1")


def test_live_requires_fresh_request_time_evidence():
    with pytest.raises(ValueError):
        DigitalTwinEngine.provenance("rpc", 1.0, "v1", source_date="2026-09-02", cache_state="STALE", truth_label="LIVE")


def _context(engine, status):
    return engine.consume_context_pack("p1", {
        "pack_id": f"kp-{status.lower()}",
        "version": "0.1.0",
        "status": status,
        "generated_at": "2026-09-02T09:54:21Z",
        "provenance": {"source": "CHAT06/HANDOFF_07", "source_date": "2026-09-02"},
        "payload": {"summary": "derived context"},
    })


def test_chat06_candidate_context_cannot_promote_twin():
    engine = DigitalTwinEngine([TwinRecord("p1", "Alpha", status=TwinStatus.KNOWN)])
    ctx = _context(engine, "CANDIDATE")
    assert ctx["status"] == "TO_VERIFY"
    assert ctx["truth_label"] == "TO_VERIFY"
    assert engine.resolve_one("Alpha").status == TwinStatus.KNOWN


@pytest.mark.parametrize("source_status", [
    "UNVERIFIED", "ANALYSIS", "COMMUNITY_REPORT", "CONTRADICTED",
    "DRAFT", "UNRESOLVED", "CONFLICT",
])
def test_chat06_nonverified_or_conflicted_states_fail_closed(source_status):
    engine = DigitalTwinEngine([TwinRecord("p1", "Alpha", status=TwinStatus.KNOWN)])
    ctx = _context(engine, source_status)
    assert ctx["source_status"] == source_status
    assert ctx["status"] == "TO_VERIFY"
    assert ctx["truth_label"] == "TO_VERIFY"
    assert engine.resolve_one("Alpha").status == TwinStatus.KNOWN


def test_chat06_verified_supported_context_remains_derived_not_twin_promotion():
    engine = DigitalTwinEngine([TwinRecord("p1", "Alpha", status=TwinStatus.KNOWN)])
    verified = _context(engine, "VERIFIED")
    supported = _context(engine, "SUPPORTED")
    assert verified["status"] == "VERIFIED" and verified["truth_label"] == "DERIVED"
    assert supported["status"] == "SUPPORTED" and supported["truth_label"] == "DERIVED"
    assert engine.resolve_one("Alpha").status == TwinStatus.KNOWN


def test_legacy_manifest_verification_levels_are_compatibility_mapped():
    assert CHAT06_STATUS_MAP["VERIFIED_PRIMARY_SOURCE"] == "VERIFIED"
    assert CHAT06_STATUS_MAP["HIGH_CONFIDENCE"] == "SUPPORTED"
    assert CHAT06_STATUS_MAP["OBSOLETE"] == "UNKNOWN"


def test_chat06_pack_requires_version_status_and_provenance():
    engine = DigitalTwinEngine([TwinRecord("p1", "Alpha")])
    with pytest.raises(ValueError):
        engine.consume_context_pack("p1", {"pack_id": "x"})


def test_wallet_contract_is_non_custodial_polygon_user_confirmed():
    assert POLYGON_CHAIN_ID == 137
    assert CORE_CONSUMER_CONTRACT_VERSION == "0.3.13"
    assert CORE_BOUNDARY["durable_principal"] == "SIC-ID"
    assert WALLET_MATRIX["custody"] == "NON_CUSTODIAL"
    assert WALLET_MATRIX["connect_is_authentication"] is False
    assert "private_key" in WALLET_MATRIX["forbidden_storage"]
    assert WALLET_MATRIX["allowed_user_actions"]["personal_sign"].startswith("READABLE_CHALLENGE")
    assert WALLET_MATRIX["allowed_user_actions"]["eth_sendTransaction"].startswith("PERSISTED_INTENT")
    assert WALLET_MATRIX["signing_policy"] == "USER_CONFIRMED_ONLY"


def test_wallet_provider_selection_and_lifecycle_are_fail_closed():
    assert WALLET_MATRIX["eip6963"]["selection"] == "EXPLICIT_USER_SELECTION"
    assert WALLET_MATRIX["event_policy"] == "FAIL_CLOSED_AND_REVALIDATE_SESSION"
    assert WALLET_MATRIX["chain_switch_policy"] == "POST_VERIFY_ETH_CHAINID_EQUALS_0x89"
    assert {"accountsChanged", "chainChanged", "disconnect"} <= set(WALLET_MATRIX["session_events"])


def test_reown_is_external_wallet_path_and_human_gate():
    reown = WALLET_MATRIX["walletconnect_reown"]
    assert reown["mode"] == "external-wallet-qr-deeplink"
    assert reown["project_config"] == "NON_SECRET_CLIENT_CONFIG_ONLY"
    assert reown["real_device"] == "HUMAN_GATE"


def test_rpc_health_is_owned_by_chat10_and_never_invented_live():
    assert RPC_HEALTH_CONTRACT["owner"] == "CHAT10"
    assert RPC_HEALTH_CONTRACT["chain_id"] == 137
    assert "LIVE only" in RPC_HEALTH_CONTRACT["live_rule"]


def test_dappmap_requires_epistemic_metadata():
    required = set(DAPPMAP_CONTRACT["required_epistemic_fields"])
    assert {"source", "source_date", "confidence", "cache_state", "truth_label", "status", "version"} <= required
