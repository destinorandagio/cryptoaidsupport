import tempfile
from pathlib import Path

from evidence_payment import EvidencePaymentEngine, TrustedPolygonRPCAdapter


WEI = 10**18


def engine():
    root = Path(tempfile.mkdtemp())
    return EvidencePaymentEngine(root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence")


def new_intent(e, key="reorg-finality"):
    return e.create_payment_intent(
        case_id=f"case-{key}",
        entitlement_ref=f"case_active:case-{key}",
        payer="0xsender",
        asset="POL",
        expected_value="450",
        request_id=f"req-{key}",
        idempotency_key=f"idem-{key}",
    )


class ReorgWindowRPC:
    """Simulate an RPC whose old receipt becomes stale when finalized advances."""

    def __init__(self, intent, *, orphan_after_finalized=False):
        self.intent = intent
        self.orphan_after_finalized = orphan_after_finalized
        self.finalized_seen = set()
        self.calls = []

    def __call__(self, provider_id, method, params):
        self.calls.append((provider_id, method, tuple(params)))
        if method == "eth_chainId":
            return "0x89"
        if method == "eth_getBlockByNumber" and params == ["finalized", False]:
            self.finalized_seen.add(provider_id)
            return {"number": "0x6e", "hash": "0xfinalized110"}
        if self.orphan_after_finalized and provider_id in self.finalized_seen:
            if method in {"eth_getTransactionByHash", "eth_getTransactionReceipt"}:
                return None
        if method == "eth_getTransactionByHash":
            return {
                "hash": "0xabc",
                "from": self.intent["payer"],
                "to": self.intent["treasury_address"],
                "value": hex(450 * WEI),
                "blockHash": "0xblock100",
                "blockNumber": "0x64",
            }
        if method == "eth_getTransactionReceipt":
            return {
                "transactionHash": "0xabc",
                "status": "0x1",
                "blockHash": "0xblock100",
                "blockNumber": "0x64",
            }
        if method == "eth_getBlockByNumber" and params == ["0x64", False]:
            return {"number": "0x64", "hash": "0xblock100"}
        raise AssertionError((provider_id, method, params))


def test_stale_pre_finality_receipt_cannot_become_settlement_truth():
    e = engine()
    intent = new_intent(e, "orphan")
    rpc = ReorgWindowRPC(intent, orphan_after_finalized=True)

    result = TrustedPolygonRPCAdapter(e, rpc).settle_from_tx_hash(
        intent_id=intent["intent_id"],
        tx_hash="0xabc",
        provider_ids=["rpc_a", "rpc_b"],
    )

    assert result["verdict"] == "MANUAL_REVIEW"
    assert result["entitlement_granted"] is False
    assert e.get_intent(intent["intent_id"])["state"] == "MANUAL_REVIEW"
    with e._connect() as c:
        assert c.execute("SELECT COUNT(*) FROM settlement_certificates").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM entitlement_ledger").fetchone()[0] == 0


def test_each_provider_observes_finalized_before_transaction_and_receipt():
    e = engine()
    intent = new_intent(e, "ordered")
    rpc = ReorgWindowRPC(intent)

    result = TrustedPolygonRPCAdapter(e, rpc).settle_from_tx_hash(
        intent_id=intent["intent_id"],
        tx_hash="0xabc",
        provider_ids=["rpc_a", "rpc_b"],
    )

    assert result["verdict"] == "SETTLED"
    for provider in ("rpc_a", "rpc_b"):
        methods = [method for pid, method, _ in rpc.calls if pid == provider]
        assert methods == [
            "eth_chainId",
            "eth_getBlockByNumber",
            "eth_getTransactionByHash",
            "eth_getTransactionReceipt",
            "eth_getBlockByNumber",
        ]
