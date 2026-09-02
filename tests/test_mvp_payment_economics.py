import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from evidence_payment import EvidencePaymentEngine, EvidencePaymentError


def engine():
    root = Path(tempfile.mkdtemp())
    return EvidencePaymentEngine(root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence")


def advance(e, intent):
    for state in ("USER_ACTION_REQUIRED", "TX_OBSERVED", "VERIFYING", "FINALITY_PENDING"):
        intent = e.transition_payment(intent["intent_id"], state, "test")
    return intent


def observation(intent, tx_hash, block_number=100):
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
        "confirmations": 0,
        "required_confirmations": 999,
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


def settle_ok(e, intent, tx_hash):
    intent = advance(e, intent)
    obs = observation(intent, tx_hash)
    result = e.settle(intent["intent_id"], obs, providers(obs))
    assert result["verdict"] == "SETTLED"
    assert result["entitlement_granted"] is True
    assert result["settlement_certificate_id"]
    return result


def activate(e, principal):
    activation = e.create_activation_intent(
        principal_id=principal,
        payer="0xsender",
        request_id=f"req-a-{principal}",
        idempotency_key=f"idem-a-{principal}",
    )
    assert activation["expected_value"] == "50"
    settle_ok(e, activation, f"0xactivation-{principal}")
    return activation


def test_payment_intent_persists_expiry_and_fails_closed_after_expiry():
    e = engine()
    intent = e.create_payment_intent(
        case_id="case-exp",
        entitlement_ref="ent-exp",
        payer="0xsender",
        asset="POL",
        expected_value="500",
        request_id="req-exp",
        idempotency_key="idem-exp",
    )
    assert intent["expires_at"]
    with e._connect() as c:
        c.execute(
            "UPDATE payment_intents SET expires_at='2000-01-01T00:00:00+00:00' WHERE intent_id=?",
            (intent["intent_id"],),
        )
    expired = e.get_intent(intent["intent_id"])
    assert expired["state"] == "EXPIRED"
    with pytest.raises(EvidencePaymentError) as exc:
        e.transition_payment(intent["intent_id"], "USER_ACTION_REQUIRED", "too late")
    assert exc.value.code == "INTENT_EXPIRED"
    obs = observation(expired, "0xexpired")
    assert e.verify_observation(intent["intent_id"], obs, providers(obs)) == "MANUAL_REVIEW"
    with e._connect() as c:
        assert c.execute("SELECT COUNT(*) FROM settlement_certificates").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM entitlement_ledger").fetchone()[0] == 0


def test_frozen_activation50_first450_then500_and_credit_consumption():
    e = engine()
    assert e.quote_next_case("sic-1") == {
        "stage": "ACTIVATION_REQUIRED",
        "activation_payable": "50",
    }

    activate(e, "sic-1")
    credit = e.get_activation_credit("sic-1")
    assert credit["amount"] == "50" and credit["state"] == "AVAILABLE"

    first = e.create_case_payment_intent(
        principal_id="sic-1",
        case_id="case-1",
        payer="0xsender",
        request_id="req-c1",
        idempotency_key="idem-c1",
    )
    assert first["expected_value"] == "450"
    econ_first = e.get_economic_intent(first["intent_id"])
    assert econ_first["nominal_value"] == "500"
    assert econ_first["credit_applied"] == "50"
    assert e.get_activation_credit("sic-1")["state"] == "RESERVED"
    settle_ok(e, first, "0xcase1")
    assert e.get_activation_credit("sic-1")["state"] == "CONSUMED"

    subsequent = e.create_case_payment_intent(
        principal_id="sic-1",
        case_id="case-2",
        payer="0xsender",
        request_id="req-c2",
        idempotency_key="idem-c2",
    )
    assert subsequent["expected_value"] == "500"
    assert e.get_economic_intent(subsequent["intent_id"])["credit_applied"] == "0"
    assert e.quote_next_case("sic-1")["stage"] == "SUBSEQUENT_CASE"


def test_activation_is_one_time_after_settlement():
    e = engine()
    activate(e, "sic-once")
    with pytest.raises(EvidencePaymentError) as exc:
        e.create_activation_intent(
            principal_id="sic-once",
            payer="0xsender",
            request_id="req-a2",
            idempotency_key="idem-a2",
        )
    assert exc.value.code == "ACTIVATION_ALREADY_GRANTED"


@pytest.mark.parametrize("terminal_state", ["EXPIRED", "REJECTED"])
def test_first_case_credit_is_released_on_retryable_terminal(terminal_state):
    e = engine()
    principal = f"sic-{terminal_state.lower()}"
    activate(e, principal)
    first = e.create_case_payment_intent(
        principal_id=principal,
        case_id="case-retry",
        payer="0xsender",
        request_id="req-old",
        idempotency_key="idem-old",
    )
    assert e.get_activation_credit(principal)["state"] == "RESERVED"

    if terminal_state == "EXPIRED":
        with e._connect() as c:
            c.execute(
                "UPDATE payment_intents SET expires_at='2000-01-01T00:00:00+00:00' WHERE intent_id=?",
                (first["intent_id"],),
            )
        assert e.get_intent(first["intent_id"])["state"] == "EXPIRED"
    else:
        for state in ("USER_ACTION_REQUIRED", "TX_OBSERVED", "VERIFYING"):
            first = e.transition_payment(first["intent_id"], state, "test")
        assert e.transition_payment(first["intent_id"], "REJECTED", "synthetic reject")["state"] == "REJECTED"

    credit = e.get_activation_credit(principal)
    assert credit["state"] == "AVAILABLE" and credit["reserved_case_id"] is None

    retry = e.create_case_payment_intent(
        principal_id=principal,
        case_id="case-retry",
        payer="0xsender",
        request_id="req-new",
        idempotency_key="idem-new",
    )
    assert retry["intent_id"] != first["intent_id"]
    assert retry["expected_value"] == "450"


def test_first_case_parallel_reservation_fails_closed():
    e = engine()
    activate(e, "sic-race")
    first = e.create_case_payment_intent(
        principal_id="sic-race",
        case_id="case-1",
        payer="0xsender",
        request_id="req-1",
        idempotency_key="idem-1",
    )
    assert first["expected_value"] == "450"
    with pytest.raises(EvidencePaymentError) as exc:
        e.create_case_payment_intent(
            principal_id="sic-race",
            case_id="case-2",
            payer="0xsender",
            request_id="req-2",
            idempotency_key="idem-2",
        )
    assert exc.value.code == "FIRST_CASE_PENDING"


def test_first_case_concurrent_race_has_exactly_one_discount_reservation():
    e = engine()
    activate(e, "sic-thread-race")
    barrier = Barrier(2)

    def attempt(n):
        barrier.wait()
        try:
            intent = e.create_case_payment_intent(
                principal_id="sic-thread-race",
                case_id=f"case-{n}",
                payer="0xsender",
                request_id=f"req-{n}",
                idempotency_key=f"idem-{n}",
            )
            return ("ok", intent["intent_id"], intent["expected_value"])
        except EvidencePaymentError as exc:
            return ("error", exc.code, None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (1, 2)))
    winners = [r for r in results if r[0] == "ok"]
    losers = [r for r in results if r[0] == "error"]
    assert len(winners) == 1 and winners[0][2] == "450"
    assert len(losers) == 1 and losers[0][1] == "FIRST_CASE_PENDING"

    with e._connect() as c:
        discounted = c.execute(
            "SELECT COUNT(*) FROM economic_intents "
            "WHERE principal_id=? AND purpose='CASE' AND credit_applied='50'",
            ("sic-thread-race",),
        ).fetchone()[0]
        assert discounted == 1


def test_case_payment_requires_settled_activation_credit():
    e = engine()
    with pytest.raises(EvidencePaymentError) as exc:
        e.create_case_payment_intent(
            principal_id="sic-none",
            case_id="case-1",
            payer="0xsender",
            request_id="req-1",
            idempotency_key="idem-1",
        )
    assert exc.value.code == "ACTIVATION_REQUIRED"
