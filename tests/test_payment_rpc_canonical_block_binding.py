import tempfile
from pathlib import Path

from evidence_payment import EvidencePaymentEngine, TrustedPolygonRPCAdapter


WEI = 10**18


def engine():
    root = Path(tempfile.mkdtemp())
    return EvidencePaymentEngine(root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence")


def new_intent(e):
    return e.create_payment_intent(
        case_id="case-canonical-block",
        entitlement_ref="case_active:case-canonical-block",
        payer="0xsender",
        asset="POL",
        expected_value="450",
        request_id="req-canonical-block",
        idempotency_key="idem-canonical-block",
    )


class CanonicalBlockMismatchRPC:
    """Return mutually-consistent tx/receipt bytes from a stale orphaned block."""

    def __init__(self, intent):
        self.intent = intent
        self.calls = []

    def __call__(self, provider_id, method, params):
        self.calls.append((provider_id, method, tuple(params)))
        if method == "eth_chainId":
            return "0x89"
        if method == "eth_getBlockByNumber" and params == ["finalized", False]:
            return {"number": "0x6e", "hash": "0xfinalized110"}
        if method == "eth_getTransactionByHash":
            return {
                "hash": "0xabc",
                "from": self.intent["payer"],
                "to": self.intent["treasury_address"],
                "value": hex(450 * WEI),
                "blockHash": "0xorphan100",
                "blockNumber": "0x64",
            }
        if method == "eth_getTransactionReceipt":
            return {
                "transactionHash": "0xabc",
                "status": "0x1",
                "blockHash": "0xorphan100",
                "blockNumber": "0x64",
            }
        if method == "eth_getBlockByNumber" and params == ["0x64", False]:
            return {"number": "0x64", "hash": "0xcanonical100"}
        raise AssertionError((provider_id, method, params))


def test_stale_tx_receipt_block_hash_cannot_settle_against_different_canonical_block():
    e = engine()
    intent = new_intent(e)
    rpc = CanonicalBlockMismatchRPC(intent)

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

    for provider in ("rpc_a", "rpc_b"):
        provider_calls = [call for call in rpc.calls if call[0] == provider]
        assert (provider, "eth_getBlockByNumber", ("0x64", False)) in provider_calls
