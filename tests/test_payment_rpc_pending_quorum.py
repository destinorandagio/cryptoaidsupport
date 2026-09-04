import tempfile
from pathlib import Path

from evidence_payment import EvidencePaymentEngine, TrustedPolygonRPCAdapter


WEI = 10**18
TX_HASH = "0xabc"
BLOCK_NUMBER = 100
BLOCK_HASH = "0xblock100"


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


class PerProviderRPC:
    def __init__(self, intent, states):
        self.intent = intent
        self.states = dict(states)
        self.seen = []

    def __call__(self, provider_id, method, params):
        self.seen.append((provider_id, method, tuple(params)))
        state = self.states[provider_id]
        if method == "eth_chainId":
            return "0x89"
        if method == "eth_getBlockByNumber":
            if params == ["finalized", False]:
                return {"number": "0x6f", "hash": "0xfinalized"}
            if params == [hex(BLOCK_NUMBER), False]:
                return {"number": hex(BLOCK_NUMBER), "hash": BLOCK_HASH}
        if method == "eth_getTransactionByHash":
            if state == "missing":
                return None
            if state == "pending":
                return {
                    "hash": TX_HASH,
                    "from": self.intent["payer"],
                    "to": self.intent["treasury_address"],
                    "value": hex(int(self.intent["expected_value"]) * WEI),
                    "blockHash": None,
                    "blockNumber": None,
                }
            if state == "mined":
                return {
                    "hash": TX_HASH,
                    "from": self.intent["payer"],
                    "to": self.intent["treasury_address"],
                    "value": hex(int(self.intent["expected_value"]) * WEI),
                    "blockHash": BLOCK_HASH,
                    "blockNumber": hex(BLOCK_NUMBER),
                }
        if method == "eth_getTransactionReceipt":
            if state in {"pending", "missing"}:
                return None
            if state == "mined":
                return {
                    "transactionHash": TX_HASH,
                    "status": "0x1",
                    "blockHash": BLOCK_HASH,
                    "blockNumber": hex(BLOCK_NUMBER),
                }
        raise AssertionError((provider_id, method, params, state))


def effect_counts(e):
    with e._connect() as c:
        return (
            c.execute("SELECT COUNT(*) FROM settlement_certificates").fetchone()[0],
            c.execute("SELECT COUNT(*) FROM entitlement_ledger").fetchone()[0],
        )


def providers_sampled(rpc):
    return {provider_id for provider_id, _, _ in rpc.seen}


def test_pending_vs_mined_provider_disagreement_is_manual_review_not_retryable():
    e = engine()
    intent = new_intent(e, "pending-vs-mined")
    rpc = PerProviderRPC(intent, {"rpc_pending": "pending", "rpc_mined": "mined"})

    result = TrustedPolygonRPCAdapter(e, rpc).settle_from_tx_hash(
        intent_id=intent["intent_id"],
        tx_hash=TX_HASH,
        provider_ids=["rpc_pending", "rpc_mined"],
    )

    assert result["verdict"] == "MANUAL_REVIEW"
    assert e.get_intent(intent["intent_id"])["state"] == "MANUAL_REVIEW"
    assert providers_sampled(rpc) == {"rpc_pending", "rpc_mined"}
    assert effect_counts(e) == (0, 0)


def test_pending_vs_missing_provider_is_manual_review_and_samples_both():
    e = engine()
    intent = new_intent(e, "pending-vs-missing")
    rpc = PerProviderRPC(intent, {"rpc_pending": "pending", "rpc_missing": "missing"})

    result = TrustedPolygonRPCAdapter(e, rpc).settle_from_tx_hash(
        intent_id=intent["intent_id"],
        tx_hash=TX_HASH,
        provider_ids=["rpc_pending", "rpc_missing"],
    )

    assert result["verdict"] == "MANUAL_REVIEW"
    assert e.get_intent(intent["intent_id"])["state"] == "MANUAL_REVIEW"
    assert providers_sampled(rpc) == {"rpc_pending", "rpc_missing"}
    assert effect_counts(e) == (0, 0)


def test_all_pending_providers_remain_retryable_only_after_full_quorum_sampling():
    e = engine()
    intent = new_intent(e, "all-pending")
    rpc = PerProviderRPC(intent, {"rpc_a": "pending", "rpc_b": "pending"})

    result = TrustedPolygonRPCAdapter(e, rpc).settle_from_tx_hash(
        intent_id=intent["intent_id"],
        tx_hash=TX_HASH,
        provider_ids=["rpc_a", "rpc_b"],
    )

    assert result["verdict"] == "FINALITY_PENDING"
    assert e.get_intent(intent["intent_id"])["state"] == "FINALITY_PENDING"
    assert providers_sampled(rpc) == {"rpc_a", "rpc_b"}
    assert effect_counts(e) == (0, 0)
