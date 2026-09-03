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


class CanonicalBlockRPC:
    def __init__(self, intent, *, canonical_block_hash="0xblock100"):
        self.intent = intent
        self.canonical_block_hash = canonical_block_hash
        self.calls = []

    def __call__(self, provider_id, method, params):
        self.calls.append((provider_id, method, tuple(params)))
        if method == "eth_chainId":
            return "0x89"
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
        if method == "eth_getBlockByNumber":
            if params == ["finalized", False]:
                return {"number": "0x6e", "hash": "0xfinalized110"}
            if params == ["0x64", False]:
                return {"number": "0x64", "hash": self.canonical_block_hash}
        raise AssertionError((provider_id, method, params))


def test_reorged_transaction_block_cannot_become_settlement_truth():
    e = engine()
    intent = new_intent(e, "orphan")
    rpc = CanonicalBlockRPC(intent, canonical_block_hash="0xreplacement100")

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


def test_finality_rechecks_transaction_block_on_current_canonical_chain():
    e = engine()
    intent = new_intent(e, "canonical")
    rpc = CanonicalBlockRPC(intent)

    result = TrustedPolygonRPCAdapter(e, rpc).settle_from_tx_hash(
        intent_id=intent["intent_id"],
        tx_hash="0xabc",
        provider_ids=["rpc_a", "rpc_b"],
    )

    assert result["verdict"] == "SETTLED"
    canonical_reads = [
        call for call in rpc.calls
        if call[1] == "eth_getBlockByNumber" and call[2] == ("0x64", False)
    ]
    assert {call[0] for call in canonical_reads} == {"rpc_a", "rpc_b"}
