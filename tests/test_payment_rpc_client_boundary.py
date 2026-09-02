import tempfile
from pathlib import Path

import pytest

from evidence_payment import EvidencePaymentEngine, TrustedPolygonRPCAdapter


def engine():
    root = Path(tempfile.mkdtemp())
    return EvidencePaymentEngine(root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence")


def test_client_authored_economic_payload_cannot_enter_rpc_settlement_api():
    e = engine()
    intent = e.create_payment_intent(
        case_id="case-client-forge",
        entitlement_ref="case_active:case-client-forge",
        payer="0xsender",
        asset="POL",
        expected_value="450",
        request_id="req-client-forge",
        idempotency_key="idem-client-forge",
    )
    adapter = TrustedPolygonRPCAdapter(e, lambda *_args: pytest.fail("RPC must not run for invalid API arguments"))
    forged_client_economics = {
        "chain_id": 137,
        "sender": intent["payer"],
        "treasury": intent["treasury_address"],
        "value": "450",
        "asset": "POL",
        "receipt_status": 1,
    }
    with pytest.raises(TypeError):
        adapter.settle_from_tx_hash(
            intent_id=intent["intent_id"],
            tx_hash="0xabc",
            provider_ids=["rpc_a", "rpc_b"],
            **forged_client_economics,
        )
    assert e.get_intent(intent["intent_id"])["state"] == "INTENT_CREATED"


def test_non_native_asset_fails_closed_before_rpc_economic_truth():
    e = engine()
    intent = e.create_payment_intent(
        case_id="case-usdt",
        entitlement_ref="case_active:case-usdt",
        payer="0xsender",
        asset="USDT",
        expected_value="450",
        request_id="req-usdt",
        idempotency_key="idem-usdt",
    )
    called = []

    def no_rpc(*args):
        called.append(args)
        return None

    result = TrustedPolygonRPCAdapter(e, no_rpc).settle_from_tx_hash(
        intent_id=intent["intent_id"], tx_hash="0xabc", provider_ids=["rpc_a", "rpc_b"]
    )
    assert result["verdict"] == "MANUAL_REVIEW"
    assert result["entitlement_granted"] is False
    assert called == []
