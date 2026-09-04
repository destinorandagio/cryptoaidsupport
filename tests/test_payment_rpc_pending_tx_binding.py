import tempfile
from pathlib import Path

import pytest

from evidence_payment import EvidencePaymentEngine, EvidencePaymentError, TrustedPolygonRPCAdapter


WEI = 10**18


def engine():
    root = Path(tempfile.mkdtemp())
    return EvidencePaymentEngine(root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence")


def new_intent(e):
    return e.create_payment_intent(
        case_id="case-pending-bind",
        entitlement_ref="case_active:case-pending-bind",
        payer="0xsender",
        asset="POL",
        expected_value="450",
        request_id="req-pending-bind",
        idempotency_key="idem-pending-bind",
    )


class PendingThenReadyRPC:
    def __init__(self, intent):
        self.intent = intent
        self.pending = True
        self.block_number = 100

    def __call__(self, provider_id, method, params):
        if method == "eth_chainId":
            return "0x89"
        if method == "eth_getBlockByNumber":
            if params == ["finalized", False]:
                return {"number": "0x6f", "hash": "0xfinalized"}
            if params == [hex(self.block_number), False]:
                return {"number": hex(self.block_number), "hash": "0xblock100"}
        if method == "eth_getTransactionByHash":
            tx_hash = params[0]
            if self.pending:
                return {
                    "hash": tx_hash,
                    "from": self.intent["payer"],
                    "to": self.intent["treasury_address"],
                    "value": hex(int(self.intent["expected_value"]) * WEI),
                    "blockHash": None,
                    "blockNumber": None,
                }
            return {
                "hash": tx_hash,
                "from": self.intent["payer"],
                "to": self.intent["treasury_address"],
                "value": hex(int(self.intent["expected_value"]) * WEI),
                "blockHash": "0xblock100",
                "blockNumber": hex(self.block_number),
            }
        if method == "eth_getTransactionReceipt":
            tx_hash = params[0]
            if self.pending:
                return None
            return {
                "transactionHash": tx_hash,
                "status": "0x1",
                "blockHash": "0xblock100",
                "blockNumber": hex(self.block_number),
            }
        raise AssertionError((provider_id, method, params))


def effect_counts(e):
    with e._connect() as c:
        return (
            c.execute("SELECT COUNT(*) FROM settlement_certificates").fetchone()[0],
            c.execute("SELECT COUNT(*) FROM entitlement_ledger").fetchone()[0],
        )


def test_first_explicit_pending_submission_binds_intent_to_that_tx_hash():
    e = engine()
    intent = new_intent(e)
    rpc = PendingThenReadyRPC(intent)
    adapter = TrustedPolygonRPCAdapter(e, rpc)

    pending = adapter.settle_from_tx_hash(
        intent_id=intent["intent_id"], tx_hash="0xaaa", provider_ids=["rpc_a", "rpc_b"]
    )

    assert pending["verdict"] == "FINALITY_PENDING"
    current = e.get_intent(intent["intent_id"])
    assert current["state"] == "FINALITY_PENDING"
    assert current["tx_hash"] == "0xaaa"
    assert effect_counts(e) == (0, 0)


def test_pending_intent_rejects_changed_tx_hash_before_rpc_or_settlement_effects():
    e = engine()
    intent = new_intent(e)
    rpc = PendingThenReadyRPC(intent)
    adapter = TrustedPolygonRPCAdapter(e, rpc)

    first = adapter.settle_from_tx_hash(
        intent_id=intent["intent_id"], tx_hash="0xaaa", provider_ids=["rpc_a", "rpc_b"]
    )
    assert first["verdict"] == "FINALITY_PENDING"

    rpc.pending = False
    with pytest.raises(EvidencePaymentError) as excinfo:
        adapter.settle_from_tx_hash(
            intent_id=intent["intent_id"], tx_hash="0xbbb", provider_ids=["rpc_a", "rpc_b"]
        )
    assert excinfo.value.code == "TX_REPLAY_CONFLICT"

    current = e.get_intent(intent["intent_id"])
    assert current["state"] == "FINALITY_PENDING"
    assert current["tx_hash"] == "0xaaa"
    assert effect_counts(e) == (0, 0)


def test_pending_intent_same_tx_hash_retry_can_still_settle():
    e = engine()
    intent = new_intent(e)
    rpc = PendingThenReadyRPC(intent)
    adapter = TrustedPolygonRPCAdapter(e, rpc)

    first = adapter.settle_from_tx_hash(
        intent_id=intent["intent_id"], tx_hash="0xaaa", provider_ids=["rpc_a", "rpc_b"]
    )
    assert first["verdict"] == "FINALITY_PENDING"

    rpc.pending = False
    settled = adapter.settle_from_tx_hash(
        intent_id=intent["intent_id"], tx_hash="0xaaa", provider_ids=["rpc_a", "rpc_b"]
    )
    assert settled["verdict"] == "SETTLED"
    assert settled["entitlement_granted"] is True
    assert e.get_intent(intent["intent_id"])["tx_hash"] == "0xaaa"
    assert effect_counts(e) == (1, 1)
