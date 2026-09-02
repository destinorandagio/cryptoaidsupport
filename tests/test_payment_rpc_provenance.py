import inspect
import tempfile
from pathlib import Path

import pytest

from evidence_payment import EvidencePaymentEngine, TrustedPolygonRPCAdapter


WEI = 10**18


def engine():
    root = Path(tempfile.mkdtemp())
    return EvidencePaymentEngine(root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence")


class FakeRPC:
    def __init__(self, intent, tx_hash="0xabc", block_number=100, finalized=(110, 111), overrides=None):
        self.intent = intent
        self.tx_hash = tx_hash
        self.block_number = block_number
        self.finalized = finalized
        self.overrides = overrides or {}
        self.calls = []

    def _snapshot(self, provider_id):
        idx = 0 if provider_id == "rpc_a" else 1
        base = {
            "chain_id": "0x89",
            "from": self.intent["payer"],
            "to": self.intent["treasury_address"],
            "value": hex(int(self.intent["expected_value"]) * WEI),
            "tx_hash": self.tx_hash,
            "block_hash": "0xblock100",
            "block_number": hex(self.block_number),
            "receipt_status": "0x1",
            "finalized_block_number": hex(self.finalized[idx]),
        }
        base.update(self.overrides.get(provider_id, {}))
        return base

    def __call__(self, provider_id, method, params):
        self.calls.append((provider_id, method, tuple(params)))
        s = self._snapshot(provider_id)
        if method == "eth_chainId":
            return s["chain_id"]
        if method == "eth_getTransactionByHash":
            return {"hash":s["tx_hash"],"from":s["from"],"to":s["to"],"value":s["value"],"blockHash":s["block_hash"],"blockNumber":s["block_number"]}
        if method == "eth_getTransactionReceipt":
            return {"transactionHash":s["tx_hash"],"status":s["receipt_status"],"blockHash":s["block_hash"],"blockNumber":s["block_number"]}
        if method == "eth_getBlockByNumber":
            assert params == ["finalized", False]
            return {"number": s["finalized_block_number"], "hash": "0xfinalized"}
        raise AssertionError(method)


def new_intent(e, expected="450", key="rpc", case_id="case-rpc"):
    return e.create_payment_intent(case_id=case_id,entitlement_ref=f"case_active:{case_id}",payer="0xsender",asset="POL",expected_value=expected,request_id=f"req-{key}",idempotency_key=f"idem-{key}")


def test_adapter_api_has_no_client_authored_economic_fields():
    params = list(inspect.signature(TrustedPolygonRPCAdapter.settle_from_tx_hash).parameters)
    assert params == ["self", "intent_id", "tx_hash", "provider_ids"]


def test_server_rpc_provenance_settles_and_binds_certificate():
    e=engine(); intent=new_intent(e); rpc=FakeRPC(intent); adapter=TrustedPolygonRPCAdapter(e,rpc)
    result=adapter.settle_from_tx_hash(intent_id=intent["intent_id"],tx_hash="0xabc",provider_ids=["rpc_a","rpc_b"])
    assert result["verdict"]=="SETTLED" and result["entitlement_granted"] is True
    assert e.get_intent(intent["intent_id"])["state"]=="SETTLED"
    cert=e.get_settlement_certificate(intent["intent_id"]); assert cert["provider_ids"]==["rpc_a","rpc_b"]; assert cert["settled_value"]=="450"
    assert len(rpc.calls)==8
    assert {call[1] for call in rpc.calls}=={"eth_chainId","eth_getTransactionByHash","eth_getTransactionReceipt","eth_getBlockByNumber"}


@pytest.mark.parametrize("overrides",[
    {"rpc_a":{"chain_id":"0x1"},"rpc_b":{"chain_id":"0x1"}},
    {"rpc_a":{"from":"0xattacker"},"rpc_b":{"from":"0xattacker"}},
    {"rpc_a":{"to":"0xattacker"},"rpc_b":{"to":"0xattacker"}},
    {"rpc_a":{"value":hex(449*WEI)},"rpc_b":{"value":hex(449*WEI)}},
    {"rpc_a":{"receipt_status":"0x0"},"rpc_b":{"receipt_status":"0x0"}},
])
def test_wrong_chain_sender_treasury_value_or_receipt_never_settles(overrides):
    e=engine(); intent=new_intent(e); adapter=TrustedPolygonRPCAdapter(e,FakeRPC(intent,overrides=overrides))
    result=adapter.settle_from_tx_hash(intent_id=intent["intent_id"],tx_hash="0xabc",provider_ids=["rpc_a","rpc_b"])
    assert result["verdict"]=="MANUAL_REVIEW" and result["entitlement_granted"] is False
    assert e.get_intent(intent["intent_id"])["state"]=="MANUAL_REVIEW"
    with e._connect() as c:
        assert c.execute("SELECT COUNT(*) FROM settlement_certificates").fetchone()[0]==0
        assert c.execute("SELECT COUNT(*) FROM entitlement_ledger").fetchone()[0]==0


def test_provider_economic_disagreement_is_manual_review():
    e=engine(); intent=new_intent(e); rpc=FakeRPC(intent,overrides={"rpc_b":{"value":hex(451*WEI)}})
    result=TrustedPolygonRPCAdapter(e,rpc).settle_from_tx_hash(intent_id=intent["intent_id"],tx_hash="0xabc",provider_ids=["rpc_a","rpc_b"])
    assert result["verdict"]=="MANUAL_REVIEW"; assert e.get_intent(intent["intent_id"])["state"]=="MANUAL_REVIEW"


def test_tx_receipt_block_or_hash_disagreement_fails_closed():
    e=engine(); intent=new_intent(e); rpc=FakeRPC(intent,overrides={"rpc_b":{"block_hash":"0xdifferent"}})
    result=TrustedPolygonRPCAdapter(e,rpc).settle_from_tx_hash(intent_id=intent["intent_id"],tx_hash="0xabc",provider_ids=["rpc_a","rpc_b"])
    assert result["verdict"]=="MANUAL_REVIEW"


def test_duplicate_provider_identity_fails_closed_without_entitlement():
    e=engine(); intent=new_intent(e); rpc=FakeRPC(intent)
    result=TrustedPolygonRPCAdapter(e,rpc).settle_from_tx_hash(intent_id=intent["intent_id"],tx_hash="0xabc",provider_ids=["rpc_a","rpc_a"])
    assert result["verdict"]=="MANUAL_REVIEW"
    with e._connect() as c: assert c.execute("SELECT COUNT(*) FROM entitlement_ledger").fetchone()[0]==0


def test_finality_pending_and_mixed_finality_are_distinct_fail_closed_states():
    pending_engine=engine(); pending_intent=new_intent(pending_engine,key="pending")
    pending=TrustedPolygonRPCAdapter(pending_engine,FakeRPC(pending_intent,finalized=(100,99))).settle_from_tx_hash(intent_id=pending_intent["intent_id"],tx_hash="0xabc",provider_ids=["rpc_a","rpc_b"])
    assert pending["verdict"]=="FINALITY_PENDING"; assert pending_engine.get_intent(pending_intent["intent_id"])["state"]=="FINALITY_PENDING"
    mixed_engine=engine(); mixed_intent=new_intent(mixed_engine,key="mixed")
    mixed=TrustedPolygonRPCAdapter(mixed_engine,FakeRPC(mixed_intent,finalized=(101,100))).settle_from_tx_hash(intent_id=mixed_intent["intent_id"],tx_hash="0xabc",provider_ids=["rpc_a","rpc_b"])
    assert mixed["verdict"]=="MANUAL_REVIEW"; assert mixed_engine.get_intent(mixed_intent["intent_id"])["state"]=="MANUAL_REVIEW"


def test_rpc_adapter_preserves_activation50_first450_then500_model():
    e=engine()
    activation=e.create_activation_intent(principal_id="sic-rpc",payer="0xsender",request_id="req-activation-rpc",idempotency_key="idem-activation-rpc")
    assert activation["expected_value"]=="50"
    activation_result=TrustedPolygonRPCAdapter(e,FakeRPC(activation,tx_hash="0xactivation")).settle_from_tx_hash(intent_id=activation["intent_id"],tx_hash="0xactivation",provider_ids=["rpc_a","rpc_b"])
    assert activation_result["verdict"]=="SETTLED"; assert e.get_activation_credit("sic-rpc")["state"]=="AVAILABLE"
    first=e.create_case_payment_intent(principal_id="sic-rpc",case_id="case-first",payer="0xsender",request_id="req-first-rpc",idempotency_key="idem-first-rpc")
    assert first["expected_value"]=="450"
    first_result=TrustedPolygonRPCAdapter(e,FakeRPC(first,tx_hash="0xfirst")).settle_from_tx_hash(intent_id=first["intent_id"],tx_hash="0xfirst",provider_ids=["rpc_a","rpc_b"])
    assert first_result["verdict"]=="SETTLED"; assert e.get_activation_credit("sic-rpc")["state"]=="CONSUMED"
    later=e.create_case_payment_intent(principal_id="sic-rpc",case_id="case-later",payer="0xsender",request_id="req-later-rpc",idempotency_key="idem-later-rpc")
    assert later["expected_value"]=="500"


def test_same_rpc_tx_cannot_settle_two_intents():
    e=engine(); first=new_intent(e,key="first",case_id="case-first")
    assert TrustedPolygonRPCAdapter(e,FakeRPC(first)).settle_from_tx_hash(intent_id=first["intent_id"],tx_hash="0xabc",provider_ids=["rpc_a","rpc_b"])["verdict"]=="SETTLED"
    second=new_intent(e,key="second",case_id="case-second")
    result=TrustedPolygonRPCAdapter(e,FakeRPC(second)).settle_from_tx_hash(intent_id=second["intent_id"],tx_hash="0xabc",provider_ids=["rpc_a","rpc_b"])
    assert result["verdict"]=="MANUAL_REVIEW" and result["entitlement_granted"] is False
