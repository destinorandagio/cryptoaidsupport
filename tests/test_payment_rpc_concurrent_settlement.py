from concurrent.futures import ThreadPoolExecutor
import tempfile
import threading
from pathlib import Path

from evidence_payment import EvidencePaymentEngine, TrustedPolygonRPCAdapter


WEI = 10**18
WORKERS = 20


def engine():
    root = Path(tempfile.mkdtemp())
    return EvidencePaymentEngine(root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence")


def new_intent(e):
    return e.create_payment_intent(
        case_id="case-concurrent-settle",
        entitlement_ref="case_active:case-concurrent-settle",
        payer="0xsender",
        asset="POL",
        expected_value="450",
        request_id="req-concurrent-settle",
        idempotency_key="idem-concurrent-settle",
    )


class ReadyRPC:
    def __init__(self, intent):
        self.intent = intent
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
            c.execute("SELECT COUNT(*) FROM payment_events WHERE intent_id=? AND new_state='SETTLED'", (e._race_intent_id,)).fetchone()[0],
        )


def test_twenty_concurrent_same_tx_settlement_retries_converge_idempotently():
    e = engine()
    intent = new_intent(e)
    e._race_intent_id = intent["intent_id"]
    adapter = TrustedPolygonRPCAdapter(e, ReadyRPC(intent))
    start = threading.Barrier(WORKERS)

    def settle_once(_):
        start.wait(timeout=10)
        return adapter.settle_from_tx_hash(
            intent_id=intent["intent_id"],
            tx_hash="0xabc",
            provider_ids=["rpc_a", "rpc_b"],
        )

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(settle_once, range(WORKERS)))

    assert all(result["verdict"] == "SETTLED" for result in results)
    assert all(result["entitlement_granted"] is True for result in results)
    assert e.get_intent(intent["intent_id"])["state"] == "SETTLED"
    assert e.get_intent(intent["intent_id"])["tx_hash"] == "0xabc"
    assert effect_counts(e) == (1, 1, 1)
