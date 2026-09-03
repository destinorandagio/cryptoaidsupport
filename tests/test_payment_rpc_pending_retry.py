import tempfile
from pathlib import Path

import pytest

from evidence_payment import EvidencePaymentEngine, TrustedPolygonRPCAdapter


WEI = 10**18


def engine():
    root = Path(tempfile.mkdtemp())
    return EvidencePaymentEngine(root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence")


def new_intent(e):
    return e.create_payment_intent(
        case_id="case-pending-rpc",
        entitlement_ref="case_active:case-pending-rpc",
        payer="0xsender",
        asset="POL",
        expected_value="450",
        request_id="req-pending-rpc",
        idempotency_key="idem-pending-rpc",
    )


class PendingThenReadyRPC:
    def __init__(self, intent, pending_kind):
        self.intent = intent
        self.pending_kind = pending_kind
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
            if self.pending and self.pending_kind == "tx":
                return None
            return {
                "hash": self.tx_hash,
                "from": self.intent["payer"],
                "to": self.intent["treasury_address"],
                "value": hex(int(self.intent["expected_value"]) * WEI),
                "blockHash": "0xblock100",
                "blockNumber": hex(self.block_number),
            }
        if method == "eth_getTransactionReceipt":
            if self.pending and self.pending_kind == "receipt":
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


@pytest.mark.parametrize("pending_kind", ["tx", "receipt"])
def test_pending_tx_or_receipt_is_retryable_without_settlement_effects(pending_kind):
    e = engine()
    intent = new_intent(e)
    rpc = PendingThenReadyRPC(intent, pending_kind)
    adapter = TrustedPolygonRPCAdapter(e, rpc)

    pending = adapter.settle_from_tx_hash(
        intent_id=intent["intent_id"],
        tx_hash="0xabc",
        provider_ids=["rpc_a", "rpc_b"],
    )

    assert pending["verdict"] == "FINALITY_PENDING"
    assert pending["entitlement_granted"] is False
    assert e.get_intent(intent["intent_id"])["state"] == "FINALITY_PENDING"
    assert effect_counts(e) == (0, 0)

    rpc.pending = False
    settled = adapter.settle_from_tx_hash(
        intent_id=intent["intent_id"],
        tx_hash="0xabc",
        provider_ids=["rpc_a", "rpc_b"],
    )

    assert settled["verdict"] == "SETTLED"
    assert settled["entitlement_granted"] is True
    assert e.get_intent(intent["intent_id"])["state"] == "SETTLED"
    assert effect_counts(e) == (1, 1)
