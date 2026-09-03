from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from core import CoreError, TrustedActivationClaimConsumer
from core import CaseEngine
from evidence_payment import CORE_ACTIVATION_CLAIM_VERSION, EvidencePaymentEngine


PAYER = "0x1111111111111111111111111111111111111111"


def _advance_payment(engine: EvidencePaymentEngine, intent: dict, tx_byte: str, block: int) -> dict:
    for state in ("USER_ACTION_REQUIRED", "TX_OBSERVED", "VERIFYING", "FINALITY_PENDING"):
        engine.transition_payment(intent["intent_id"], state, f"test {state.lower()}")
    tx_hash = "0x" + tx_byte * 64
    block_hash = "0x" + f"{block:064x}"
    observation = {
        "chain_id": 137,
        "from": PAYER,
        "to": intent["treasury_address"],
        "value": str(intent["expected_value"]),
        "asset": "POL",
        "receipt_status": 1,
        "case_id": intent["case_id"],
        "entitlement_ref": intent["entitlement_ref"],
        "tx_hash": tx_hash,
        "block_hash": block_hash,
        "block_number": block,
    }
    providers = [
        {
            "provider_id": "rpc_a",
            "tx_hash": tx_hash,
            "block_hash": block_hash,
            "receipt_status": 1,
            "tx_block_number": block,
            "finalized_block_number": block + 1,
        },
        {
            "provider_id": "rpc_b",
            "tx_hash": tx_hash,
            "block_hash": block_hash,
            "receipt_status": 1,
            "tx_block_number": block,
            "finalized_block_number": block + 2,
        },
    ]
    result = engine.settle(intent["intent_id"], observation, providers)
    assert result["verdict"] == "SETTLED"
    assert result["entitlement_granted"] is True
    return result


def _claim(engine: EvidencePaymentEngine, intent: dict) -> dict:
    certificate = engine.get_settlement_certificate(intent["intent_id"])
    payload = {
        "contract_version": CORE_ACTIVATION_CLAIM_VERSION,
        "case_id": intent["case_id"],
        "intent_id": intent["intent_id"],
        "entitlement_ref": intent["entitlement_ref"],
        "settlement_certificate_id": certificate["certificate_id"],
        "payment_state": "SETTLED",
        "case_state_authority": "CORE",
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**payload, "sha256": digest}


def _stack(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    payments = EvidencePaymentEngine(db, tmp_path / "private-evidence")

    user = core.register_user("SIC-ACTIVE-CLAIM", {}, "reg-claim", "req-reg-claim")
    opened = core.open_case(
        user["user_id"],
        user["sic_id"],
        None,
        "project:claim",
        False,
        "USER",
        "req-case-claim",
        "idem-case-claim",
    )
    state = core.transition(
        opened["case_id"], user["user_id"], "TRIAGE", "USER", "triage",
        "req-triage", "idem-triage", "OWNER", opened["version"],
    )
    state = core.transition(
        opened["case_id"], user["user_id"], "PRODUCT_SELECTED", "USER", "product",
        "req-product", "idem-product", "OWNER", state["version"],
    )
    state = core.transition(
        opened["case_id"], user["user_id"], "EVIDENCE_REQUIRED", "SYSTEM", "evidence",
        "req-evidence", "idem-evidence", "OWNER", state["version"],
    )
    state = core.transition(
        opened["case_id"], user["user_id"], "CONSENT_REQUIRED", "USER", "consent",
        "req-consent", "idem-consent", "OWNER", state["version"],
    )
    state = core.transition(
        opened["case_id"], user["user_id"], "PAYMENT_REQUIRED", "SYSTEM", "payment",
        "req-payment", "idem-payment", "OWNER", state["version"],
    )
    state = core.transition(
        opened["case_id"], user["user_id"], "PAYMENT_VERIFYING", "SYSTEM", "verify",
        "req-verify", "idem-verify", "OWNER", state["version"],
    )

    activation = payments.create_activation_intent(
        principal_id=user["sic_id"],
        payer=PAYER,
        request_id="pay-activation-req",
        idempotency_key="pay-activation-idem",
    )
    _advance_payment(payments, activation, "a", 100)

    intent = payments.create_case_payment_intent(
        principal_id=user["sic_id"],
        case_id=opened["case_id"],
        payer=PAYER,
        request_id="pay-case-req",
        idempotency_key="pay-case-idem",
    )
    _advance_payment(payments, intent, "b", 110)
    return db, core, payments, user, opened, state, intent, _claim(payments, intent)


def test_settled_hash_bound_claim_activates_same_case_once(tmp_path: Path):
    db, core, _, user, opened, state, intent, claim = _stack(tmp_path)
    consumer = TrustedActivationClaimConsumer(db)

    activated = consumer.consume(claim=claim, request_id="claim-consume-1")
    assert activated["case_id"] == opened["case_id"]
    assert activated["state"] == "ACTIVE"
    assert activated["previous_state"] == "PAYMENT_VERIFYING"
    assert activated["version"] == state["version"] + 1
    assert activated["intent_id"] == intent["intent_id"]
    assert activated["activation_claim_sha256"] == claim["sha256"]
    assert activated["idempotent"] is False

    replay = consumer.consume(claim=claim, request_id="claim-consume-retry")
    assert replay["state"] == "ACTIVE"
    assert replay["version"] == activated["version"]
    assert replay["idempotent"] is True
    assert core.get_case(opened["case_id"], user["user_id"])["state"] == "ACTIVE"

    key = f"core-activation-claim:{claim['sha256']}"
    with core.conn() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM core_case_events WHERE case_id=? AND idempotency_key=?",
            (opened["case_id"], key),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM core_requests WHERE idempotency_key=? AND operation='transition'",
            (key,),
        ).fetchone()[0] == 1
        event = conn.execute(
            "SELECT * FROM core_case_events WHERE idempotency_key=?", (key,)
        ).fetchone()
        assert event["authorization"] == "ENTITLEMENT_GRANTED"
        assert event["actor"] == "CORE_SETTLEMENT_EFFECT"


def test_eight_concurrent_claim_consumers_converge_to_one_activation(tmp_path: Path):
    db, core, _, user, opened, state, _, claim = _stack(tmp_path)

    def consume(index: int):
        return TrustedActivationClaimConsumer(db).consume(
            claim=claim,
            request_id=f"claim-race-{index}",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(consume, range(8)))

    assert {result["state"] for result in results} == {"ACTIVE"}
    assert {result["version"] for result in results} == {state["version"] + 1}
    assert core.get_case(opened["case_id"], user["user_id"])["state"] == "ACTIVE"
    key = f"core-activation-claim:{claim['sha256']}"
    with core.conn() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM core_case_events WHERE idempotency_key=?", (key,)
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM core_requests WHERE idempotency_key=?", (key,)
        ).fetchone()[0] == 1


def test_claim_hash_and_durable_lineage_fail_closed(tmp_path: Path):
    db, _, payments, _, _, _, _, claim = _stack(tmp_path)
    consumer = TrustedActivationClaimConsumer(db)

    tampered = dict(claim)
    tampered["settlement_certificate_id"] = "sc_forged"
    with pytest.raises(CoreError) as rejected:
        consumer.consume(claim=tampered, request_id="claim-tamper")
    assert rejected.value.code == "ACTIVATION_CLAIM_HASH_MISMATCH"

    forged = dict(claim)
    forged["settlement_certificate_id"] = "sc_forged"
    payload = {key: forged[key] for key in forged if key != "sha256"}
    forged["sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    with pytest.raises(CoreError) as rejected:
        consumer.consume(claim=forged, request_id="claim-forged-cert")
    assert rejected.value.code == "ACTIVATION_EFFECT_MISMATCH"

    with payments._connect() as conn:
        conn.execute(
            "UPDATE economic_intents SET purpose='ACTIVATION' WHERE intent_id=?",
            (claim["intent_id"],),
        )
    with pytest.raises(CoreError) as rejected:
        consumer.consume(claim=claim, request_id="claim-wrong-purpose")
    assert rejected.value.code == "ACTIVATION_EFFECT_MISMATCH"


def test_claim_cannot_skip_required_core_state_or_accept_client_shape_drift(tmp_path: Path):
    db, core, _, user, opened, _, _, claim = _stack(tmp_path)
    with core.conn() as conn:
        conn.execute(
            "UPDATE core_cases SET state='PAYMENT_REQUIRED' WHERE case_id=?",
            (opened["case_id"],),
        )
    consumer = TrustedActivationClaimConsumer(db)
    with pytest.raises(CoreError) as rejected:
        consumer.consume(claim=claim, request_id="claim-too-early")
    assert rejected.value.code == "ACTIVATION_STATE_INVALID"
    assert core.get_case(opened["case_id"], user["user_id"])["state"] == "PAYMENT_REQUIRED"

    extra = {**claim, "authorization": "ENTITLEMENT_GRANTED"}
    with pytest.raises(CoreError) as rejected:
        consumer.consume(claim=extra, request_id="claim-extra-field")
    assert rejected.value.code == "ACTIVATION_CLAIM_INVALID"

    with pytest.raises(CoreError) as rejected:
        consumer.consume(claim=claim, request_id="   ")
    assert rejected.value.code == "REQUEST_ID_REQUIRED"
