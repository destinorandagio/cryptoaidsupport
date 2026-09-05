import pytest
from twin.contracts import CORE_BOUNDARY,CORE_CONSUMER_CONTRACT_VERSION,DAPPMAP_CONTRACT,POLYGON_CHAIN_ID,WALLET_MATRIX
from twin.engine import DigitalTwinEngine,NumericFact,TwinRecord,TwinStatus
def verified_provenance(): return [DigitalTwinEngine.provenance("upstream-canon",0.99,"v1",source_date="2026-09-02",cache_state="FRESH",truth_label="LIVE")]
def test_alias_resolution_and_old_name():
    engine=DigitalTwinEngine([TwinRecord("p1","New Project",{"Old Project"},137,status=TwinStatus.VERIFIED,provenance=verified_provenance())]); assert engine.resolve_one("old-project").twin_id=="p1"
def test_ticker_and_family_resolution():
    engine=DigitalTwinEngine([TwinRecord("p1","Alpha Project",ticker="ALP",family_id="family-alpha",chain_id=137)]); assert engine.resolve_one("ALP").twin_id=="p1"; assert engine.resolve_one("family-alpha").twin_id=="p1"
def test_same_name_different_chain_requires_disambiguation():
    engine=DigitalTwinEngine([TwinRecord("p1","Alpha",chain_id=137),TwinRecord("p2","Alpha",chain_id=1)])
    with pytest.raises(ValueError): engine.resolve_one("Alpha")
    assert engine.resolve_one("Alpha",chain_id=137).twin_id=="p1"
def test_contract_resolution_is_case_insensitive():
    address="0x"+"aB"*20; engine=DigitalTwinEngine([TwinRecord("p1","Alpha",chain_id=137,contracts={address})]); assert engine.resolve_one(address.upper().replace("0X","0x")).twin_id=="p1"
def test_search_miss_is_to_verify_and_case_can_continue():
    r=DigitalTwinEngine().search_or_candidate("Unknown"); assert r["state"]=="TO_VERIFY"; assert r["candidate_status"]=="USER_SUBMITTED_TO_VERIFY"; assert r["truth_label"]=="TO_VERIFY"; assert r["case_available"] is True; assert r["promoted"] is False
def test_duplicate_twin_id_is_rejected():
    e=DigitalTwinEngine([TwinRecord("p1","Alpha")])
    with pytest.raises(ValueError): e.add(TwinRecord("p1","Different Alpha"))
def test_verified_record_requires_provenance():
    with pytest.raises(ValueError): DigitalTwinEngine([TwinRecord("p1","Alpha",status=TwinStatus.VERIFIED)])
def test_numeric_facts_require_source_date_confidence_and_cache_state():
    f=NumericFact(17604,"registry-snapshot","2026-09-01",0.95,"FRESH","CACHED","snapshot-1"); assert f.value==17604
    with pytest.raises(ValueError): NumericFact(17604,"registry-snapshot","",0.95,"FRESH","CACHED","snapshot-1")
def test_live_requires_fresh_request_time_evidence():
    with pytest.raises(ValueError): DigitalTwinEngine.provenance("rpc",1.0,"v1",source_date="2026-09-02",cache_state="STALE",truth_label="LIVE")
def _context(engine,status): return engine.consume_context_pack("p1",{"pack_id":f"kp-{status.lower()}","version":"1.0.0","status":status,"generated_at":"2026-09-02T10:30:00Z","provenance":{"source":"CHAT06/canonical","source_date":"2026-09-02"},"payload":{"summary":"derived context"}})
def test_chat06_candidate_context_cannot_promote_twin():
    e=DigitalTwinEngine([TwinRecord("p1","Alpha",status=TwinStatus.KNOWN)]); ctx=_context(e,"CANDIDATE"); assert ctx["status"]=="TO_VERIFY"; assert ctx["truth_label"]=="TO_VERIFY"; assert e.resolve_one("Alpha").status==TwinStatus.KNOWN
@pytest.mark.parametrize("source_status",["UNVERIFIED","ANALYSIS","COMMUNITY_REPORT","CONTRADICTED","DRAFT","UNRESOLVED","CONFLICT"])
def test_chat06_nonverified_states_fail_closed(source_status):
    e=DigitalTwinEngine([TwinRecord("p1","Alpha")]); assert _context(e,source_status)["status"]=="TO_VERIFY"; assert e.resolve_one("Alpha").status==TwinStatus.KNOWN
def test_chat06_verified_context_remains_derived_not_twin_promotion():
    e=DigitalTwinEngine([TwinRecord("p1","Alpha",status=TwinStatus.KNOWN)]); ctx=_context(e,"VERIFIED_PRIMARY_SOURCE"); assert ctx["status"]=="VERIFIED"; assert ctx["truth_label"]=="DERIVED"; assert e.resolve_one("Alpha").status==TwinStatus.KNOWN
def test_core_and_wallet_boundaries_are_fail_closed():
    assert POLYGON_CHAIN_ID==137; assert CORE_CONSUMER_CONTRACT_VERSION=="0.3.13"; assert CORE_BOUNDARY["durable_principal"]=="SIC-ID"; assert WALLET_MATRIX["custody"]=="NON_CUSTODIAL"; assert WALLET_MATRIX["connect_is_authentication"] is False; assert WALLET_MATRIX["eip6963"]["selection"]=="EXPLICIT_USER_SELECTION"; assert WALLET_MATRIX["event_policy"]=="FAIL_CLOSED_AND_REVALIDATE_SESSION"; assert WALLET_MATRIX["walletconnect_reown"]["real_device"]=="HUMAN_GATE"; assert "private_key" in WALLET_MATRIX["forbidden_storage"]
def test_dappmap_requires_epistemic_metadata():
    required=set(DAPPMAP_CONTRACT["required_epistemic_fields"]); assert {"source","source_date","observed_at","confidence","cache_state","truth_label","status","version"}<=required
