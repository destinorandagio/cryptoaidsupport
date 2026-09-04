import tempfile
from pathlib import Path

import pytest

from evidence_payment import EvidencePaymentEngine, EvidencePaymentError


def engine():
    root = Path(tempfile.mkdtemp())
    return EvidencePaymentEngine(root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence")


def advance(e, intent):
    for state in ("USER_ACTION_REQUIRED", "TX_OBSERVED", "VERIFYING", "FINALITY_PENDING"):
        intent = e.transition_payment(intent["intent_id"], state, "test")
    return intent


def good_obs(intent, tx_hash="0xabc", block_number=100):
    return {
        "chain_id": 137,
        "from": intent["payer"],
        "to": intent["treasury_address"],
        "value": intent["expected_value"],
        "asset": intent["asset"],
        "receipt_status": 1,
        "case_id": intent["case_id"],
        "entitlement_ref": intent["entitlement_ref"],
        "tx_hash": tx_hash,
        "block_hash": f"block-{tx_hash}",
        "block_number": block_number,
        "confirmations": 999,
        "required_confirmations": 1,
    }


def providers(obs, finalized_a=110, finalized_b=111):
    return [
        {
            "provider_id": "rpc_a",
            "tx_hash": obs["tx_hash"],
            "block_hash": obs["block_hash"],
            "receipt_status": 1,
            "tx_block_number": obs["block_number"],
            "finalized_block_number": finalized_a,
        },
        {
            "provider_id": "rpc_b",
            "tx_hash": obs["tx_hash"],
            "block_hash": obs["block_hash"],
            "receipt_status": 1,
            "tx_block_number": obs["block_number"],
            "finalized_block_number": finalized_b,
        },
    ]


def new_intent(e, key="i", case_id="c", entitlement_ref="ent"):
    return e.create_payment_intent(
        case_id=case_id,
        entitlement_ref=entitlement_ref,
        payer="0xsender",
        asset="POL",
        expected_value="500",
        request_id=f"r-{key}",
        idempotency_key=key,
    )


def test_evidence_hash_private_versioning_and_tamper_guards():
    e = engine()
    a = e.store_evidence(
        case_id="c1", content=b"abc", original_name="a.pdf",
        mime_declared="application/pdf", mime_detected="application/pdf",
        uploader="u", consent_id="cons", authorization="ALLOW",
    )
    b = e.store_evidence(
        case_id="c1", content=b"abcd", original_name="a.pdf",
        mime_declared="application/pdf", mime_detected="application/pdf",
        uploader="u", consent_id="cons", authorization="ALLOW",
        parent_evidence_id=a["evidence_id"], reason="replace",
    )
    assert a["sha256"] != b["sha256"] and b["version"] == 2
    assert "public_html" not in str(e.private_root).lower()
    with pytest.raises(EvidencePaymentError):
        e.store_evidence(
            case_id="c", content=b"x", original_name="x",
            mime_declared="image/png", mime_detected="image/jpeg",
            uploader="u", consent_id="c", authorization="ALLOW",
        )
    with pytest.raises(EvidencePaymentError):
        e.store_evidence(
            case_id="c", content=b"xx", original_name="x",
            mime_declared="image/png", mime_detected="image/png",
            uploader="u", consent_id="c", authorization="ALLOW", max_bytes=1,
        )
    with pytest.raises(EvidencePaymentError):
        e.store_evidence(
            case_id="c", content=b"x", original_name="x",
            mime_declared="image/png", mime_detected="image/png",
            uploader="u", consent_id="c", authorization="DENIED",
        )


def test_payment_idempotency_wrong_chain_and_provider_disagreement_manual_review():
    e = engine()
    i = new_intent(e, "idem")
    assert new_intent(e, "idem")["intent_id"] == i["intent_id"]
    i = advance(e, i)

    o = good_obs(i)
    o["chain_id"] = 1
    assert e.verify_observation(i["intent_id"], o, providers(o)) == "MANUAL_REVIEW"

    o = good_obs(i)
    ps = providers(o)
    ps[1]["block_hash"] = "different"
    assert e.verify_observation(i["intent_id"], o, ps) == "MANUAL_REVIEW"


def test_provider_quorum_requires_independent_ids_exact_receipt_and_tx_block():
    e = engine()
    i = advance(e, new_intent(e, "q"))
    o = good_obs(i)

    duplicate_ids = providers(o)
    duplicate_ids[1]["provider_id"] = "rpc_a"
    assert e.verify_observation(i["intent_id"], o, duplicate_ids) == "MANUAL_REVIEW"

    wrong_tx = providers(o)
    for p in wrong_tx:
        p["tx_hash"] = "0xother"
    assert e.verify_observation(i["intent_id"], o, wrong_tx) == "MANUAL_REVIEW"

    wrong_height = providers(o)
    wrong_height[1]["tx_block_number"] = 101
    assert e.verify_observation(i["intent_id"], o, wrong_height) == "MANUAL_REVIEW"


def test_polygon_finalized_boundary_replaces_confirmation_count():
    e = engine()

    pending = advance(e, new_intent(e, "pending", "p", "ep"))
    op = good_obs(pending, "0xpending", 100)
    op["confirmations"] = 10_000
    op["required_confirmations"] = 1
    assert e.verify_observation(pending["intent_id"], op, providers(op, 99, 99)) == "FINALITY_PENDING"

    mixed = advance(e, new_intent(e, "mixed", "m", "em"))
    om = good_obs(mixed, "0xmixed", 100)
    assert e.verify_observation(mixed["intent_id"], om, providers(om, 100, 99)) == "MANUAL_REVIEW"

    final = advance(e, new_intent(e, "final", "f", "ef"))
    of = good_obs(final, "0xfinal", 100)
    of["confirmations"] = 0
    of["required_confirmations"] = 999
    assert e.verify_observation(final["intent_id"], of, providers(of, 101, 102)) == "SETTLED"


def test_missing_or_malformed_finalized_boundary_fails_closed():
    e = engine()
    i = advance(e, new_intent(e, "bad-final"))
    o = good_obs(i)
    ps = providers(o)
    del ps[0]["finalized_block_number"]
    assert e.verify_observation(i["intent_id"], o, ps) == "MANUAL_REVIEW"

    ps = providers(o)
    ps[0]["finalized_block_number"] = "not-a-block"
    assert e.verify_observation(i["intent_id"], o, ps) == "MANUAL_REVIEW"


def test_settlement_is_append_only_idempotent_and_has_finality_audit_certificate():
    e = engine()
    i = advance(e, new_intent(e, "settle"))
    o = good_obs(i)
    first = e.settle(i["intent_id"], o, providers(o))
    second = e.settle(i["intent_id"], o, providers(o))

    assert first["entitlement_granted"] is True and first["settlement_certificate_id"]
    assert second["idempotent"] is True
    assert second["settlement_certificate_id"] == first["settlement_certificate_id"]
    certificate = e.get_settlement_certificate(i["intent_id"])
    assert certificate["provider_ids"] == ["rpc_a", "rpc_b"]
    assert certificate["chain_id"] == 137
    assert certificate["tx_hash"] == o["tx_hash"]

    with e._connect() as c:
        assert c.execute("SELECT COUNT(*) FROM entitlement_ledger").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM settlement_certificates").fetchone()[0] == 1
        lineage = c.execute("SELECT lineage FROM entitlement_ledger").fetchone()[0]
        assert first["settlement_certificate_id"] in lineage
        event = c.execute(
            "SELECT provider_data FROM payment_events WHERE intent_id=? AND new_state='SETTLED'",
            (i["intent_id"],),
        ).fetchone()
        assert event is not None
        assert "finalized_block_number" in event[0]


def test_nonfinal_transaction_never_grants_certificate_or_entitlement():
    e = engine()
    i = advance(e, new_intent(e, "nf"))
    o = good_obs(i)
    result = e.settle(i["intent_id"], o, providers(o, 99, 99))
    assert result == {
        "intent_id": i["intent_id"],
        "verdict": "FINALITY_PENDING",
        "entitlement_granted": False,
    }
    with e._connect() as c:
        assert c.execute("SELECT COUNT(*) FROM entitlement_ledger").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM settlement_certificates").fetchone()[0] == 0


def test_duplicate_tx_different_case_goes_manual_review():
    e = engine()
    a = advance(e, new_intent(e, "a", "a", "ea"))
    oa = good_obs(a, "0xdup", 100)
    e.settle(a["intent_id"], oa, providers(oa))

    b = advance(e, new_intent(e, "b", "b", "eb"))
    ob = good_obs(b, "0xdup", 100)
    assert e.verify_observation(b["intent_id"], ob, providers(ob)) == "MANUAL_REVIEW"


def test_multiple_active_treasuries_and_version_history():
    e = engine()
    r = e.configure_treasury(
        treasury_id="backup", address="0xB", asset="POL", status="ACTIVE",
        priority=2, routing_rule="FALLBACK", valid_from="2020-01-01T00:00:00+00:00",
        valid_to=None, created_by="admin", approved_by="admin2",
    )
    r2 = e.configure_treasury(
        treasury_id="backup", address="0xC", asset="POL", status="ACTIVE",
        priority=2, routing_rule="FALLBACK", valid_from="2020-01-01T00:00:00+00:00",
        valid_to=None, created_by="admin", approved_by="admin2",
    )
    assert r["version"] == 1 and r2["version"] == 2