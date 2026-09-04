from datetime import datetime,timedelta,timezone
import pytest
from twin.wallet import ProviderCandidate,WalletSession,select_provider,validate_rpc_observation
def provider(uid,name="Wallet"): return ProviderCandidate(uid,name,"com.example.wallet",f"provider-{uid}")
def test_provider_selection_is_explicit_and_never_auto_picks():
    a=provider("550e8400-e29b-41d4-a716-446655440000","A"); b=provider("123e4567-e89b-42d3-a456-426614174000","B")
    with pytest.raises(ValueError): select_provider([a,b],"")
    assert select_provider([a,b],b.uuid).name=="B"
def test_duplicate_provider_uuid_is_rejected():
    uid="550e8400-e29b-41d4-a716-446655440000"
    with pytest.raises(ValueError): select_provider([provider(uid,"A"),provider(uid,"B")],uid)
def test_connect_is_not_authentication_and_polygon_bind_is_active():
    s=WalletSession("sic-1","550e8400-e29b-41d4-a716-446655440000","p1"); s.on_event("connect",{"chainId":"0x89"}); assert s.authenticated is False and s.needs_revalidation is True; s.bind("0x"+"ab"*20,"0x89"); assert s.active is True and s.chain_id==137 and s.authenticated is False
def test_reconnect_event_invalidates_previously_active_session_until_fresh_rebind():
    s=WalletSession("sic-1","550e8400-e29b-41d4-a716-446655440000","p1")
    s.bind("0x"+"ab"*20,137)
    assert s.active is True and s.needs_revalidation is False
    s.on_event("connect",{"chainId":"0x89"})
    assert s.active is False
    assert s.needs_revalidation is True
    assert s.authenticated is False
def test_wrong_chain_fails_closed():
    s=WalletSession("sic-1","550e8400-e29b-41d4-a716-446655440000","p1")
    with pytest.raises(ValueError): s.bind("0x"+"ab"*20,"0x1")
    assert s.active is False and s.needs_revalidation is True
def test_disconnect_and_account_change_invalidate_session():
    s=WalletSession("sic-1","550e8400-e29b-41d4-a716-446655440000","p1"); s.bind("0x"+"ab"*20,137); s.on_event("accountsChanged",["0x"+"cd"*20]); assert s.active is False and s.needs_revalidation is True; s.bind("0x"+"cd"*20,137); s.on_event("disconnect"); assert s.active is False and s.needs_revalidation is True
def test_chain_changed_even_to_polygon_requires_request_time_revalidation():
    s=WalletSession("sic-1","550e8400-e29b-41d4-a716-446655440000","p1"); s.bind("0x"+"ab"*20,137); s.on_event("chainChanged","0x89"); assert s.active is False and s.needs_revalidation is True
def test_fresh_polygon_rpc_observation_can_be_live():
    now=datetime(2026,9,2,10,30,tzinfo=timezone.utc); r=validate_rpc_observation({"provider_id":"rpc-1","observed_at":(now-timedelta(seconds=5)).isoformat(),"latency_ms":120,"chain_id":137,"result":True,"source":"request-time-health"},now=now); assert r["truth_label"]=="LIVE" and r["cache_state"]=="FRESH" and r["usable"] is True
def test_stale_rpc_observation_is_never_fake_live():
    now=datetime(2026,9,2,10,30,tzinfo=timezone.utc); r=validate_rpc_observation({"provider_id":"rpc-1","observed_at":(now-timedelta(minutes=5)).isoformat(),"latency_ms":120,"chain_id":137,"result":True,"source":"cached-health"},now=now,max_age_seconds=60); assert r["truth_label"]=="CACHED" and r["cache_state"]=="STALE" and r["usable"] is False
def test_wrong_chain_rpc_observation_is_to_verify_not_live():
    now=datetime(2026,9,2,10,30,tzinfo=timezone.utc); r=validate_rpc_observation({"provider_id":"rpc-1","observed_at":now.isoformat(),"latency_ms":10,"chain_id":1,"result":True,"source":"request-time-health"},now=now); assert r["truth_label"]=="TO_VERIFY" and r["usable"] is False and r["reason"]=="WRONG_CHAIN"
@pytest.mark.parametrize("bad_result",["false","true",1,0,None,{},[]])
def test_rpc_result_must_be_strict_boolean_and_never_truthy_coerced(bad_result):
    now=datetime(2026,9,2,10,30,tzinfo=timezone.utc)
    with pytest.raises(ValueError,match="rpc result must be boolean"):
        validate_rpc_observation({"provider_id":"rpc-1","observed_at":now.isoformat(),"latency_ms":10,"chain_id":137,"result":bad_result,"source":"request-time-health"},now=now)
@pytest.mark.parametrize("event,payload",[("chainChanged",{"chainId":"0x89"}),("accountsChanged",{"unexpected":"payload"})])
def test_malformed_wallet_event_invalidates_active_session_before_payload_parse(event,payload):
    s=WalletSession("sic-1","550e8400-e29b-41d4-a716-446655440000","p1")
    s.bind("0x"+"ab"*20,137)
    s.authenticated=True
    with pytest.raises((TypeError,ValueError)):
        s.on_event(event,payload)
    assert s.active is False
    assert s.needs_revalidation is True
    assert s.authenticated is False
    s.bind("0x"+"ab"*20,137)
    assert s.active is True and s.chain_id==137 and s.needs_revalidation is False

@pytest.mark.parametrize("bad_account,bad_chain",[("not-an-address",137),("0x"+"ab"*20,"0x89junk")])
def test_malformed_bind_invalidates_previously_active_authenticated_session_before_parse(bad_account,bad_chain):
    s=WalletSession("sic-1","550e8400-e29b-41d4-a716-446655440000","p1")
    s.bind("0x"+"ab"*20,137)
    s.authenticated=True
    with pytest.raises(ValueError):
        s.bind(bad_account,bad_chain)
    assert s.active is False
    assert s.authenticated is False
    assert s.needs_revalidation is True
    assert s.account is None
    assert s.chain_id is None

def test_wrong_chain_bind_clears_prior_authentication_and_never_preserves_active_session():
    s=WalletSession("sic-1","550e8400-e29b-41d4-a716-446655440000","p1")
    s.bind("0x"+"ab"*20,137)
    s.authenticated=True
    with pytest.raises(ValueError,match="Polygon 137 required"):
        s.bind("0x"+"cd"*20,"0x1")
    assert s.active is False
    assert s.authenticated is False
    assert s.needs_revalidation is True
    assert s.account=="0x"+"cd"*20
    assert s.chain_id==1
