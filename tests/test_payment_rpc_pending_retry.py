import tempfile
from pathlib import Path

from evidence_payment import EvidencePaymentEngine, TrustedPolygonRPCAdapter


WEI = 10**18


def engine():
    root = Path(tempfile.mkdtemp())
    return EvidencePaymentEngine(root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence")


def new_intent(e, key):
    return e.create_payment_intent(
        case_id=f"case-{key}",
        entitlement_ref=f"case_active:case-{key}",
        payer="0xsender",
        asset="POL",
        expected_value="450",
        request_id=f"req-{key}",
        idempotency_key=f"idem-{key}",
    )


class PendingThenReadyRPC:
    def __init__(self, intent, mode="pending_object"):
        self.intent = intent
        self.mode = mode
        self.pending = True
        self.tx_hash = "0xabc"
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
            if self.pending and self.mode == "missing_tx":
                return None
            if self.pending and self.mode == "pending_object":
                return {
                    "hash": self.tx_hash,
                    "from": self.intent["payer"],
                    "to": self.intent["treasury_address"],
                    "value": hex(int(self.intent["expected_value"]) * WEI),
                    "blockHash": None,
                    "blockNumber": None,
                }
            return {
                "hash": self.tx_hash,
                "from": self.intent["payer"],
                "to": self.intent["treasury_address"],
                "value": hex(int(self.intent["expected_value"]) * WEI),
                "blockHash": "0xblock100",
                "blockNumber": hex(self.block_number),
            }
        if method == "eth_getTransactionReceipt":
            if self.pending:
                return None
            return {
                "transactionHash": self.tx_hash,
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


def test_explicit_pending_tx_object_is_retryable_without_settlement_effects():
    e = engine()
    intent = new_intent(e, "pending-object")
    rpc = PendingThenReadyRPC(intent)
    adapter = TrustedPolygonRPCAdapter(e, rpc)

    pending = adapter.settle_from_tx_hash(
        intent_id=intent["intent_id"], tx_hash="0xabc", provider_ids=["rpc_a", "rpc_b"]
    )
    assert pending["verdict"] == "FINALITY_PENDING"
    assert pending["entitlement_granted"] is False
    assert e.get_intent(intent["intent_id"])["state"] == "FINALITY_PENDING"
    assert effect_counts(e) == (0, 0)

    rpc.pending = False
    settled = adapter.settle_from_tx_hash(
        intent_id=intent["intent_id"], tx_hash="0xabc", provider_ids=["rpc_a", "rpc_b"]
    )
    assert settled["verdict"] == "SETTLED"
    assert settled["entitlement_granted"] is True
    assert e.get_intent(intent["intent_id"])["state"] == "SETTLED"
    assert effect_counts(e) == (1, 1)


def test_missing_tx_remains_manual_review_because_propagation_and_orphan_are_ambiguous():
    e = engine()
    intent = new_intent(e, "missing-tx")
    rpc = PendingThenReadyRPC(intent, mode="missing_tx")
    result = TrustedPolygonRPCAdapter(e, rpc).settle_from_tx_hash(
        intent_id=intent["intent_id"], tx_hash="0xabc", provider_ids=["rpc_a", "rpc_b"]
    )
    assert result["verdict"] == "MANUAL_REVIEW"
    assert e.get_intent(intent["intent_id"])["state"] == "MANUAL_REVIEW"
    assert effect_counts(e) == (0, 0)


def test_mined_tx_without_receipt_remains_manual_review():
    e = engine()
    intent = new_intent(e, "missing-receipt")
    rpc = PendingThenReadyRPC(intent, mode="mined_missing_receipt")
    result = TrustedPolygonRPCAdapter(e, rpc).settle_from_tx_hash(
        intent_id=intent["intent_id"], tx_hash="0xabc", provider_ids=["rpc_a", "rpc_b"]
    )
    assert result["verdict"] == "MANUAL_REVIEW"
    assert e.get_intent(intent["intent_id"])["state"] == "MANUAL_REVIEW"
    assert effect_counts(e) == (0, 0)
