import tempfile
from pathlib import Path

from evidence_payment import EvidencePaymentEngine


def engine():
    root = Path(tempfile.mkdtemp())
    return EvidencePaymentEngine(root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence")


def reject_intent(e, intent_id):
    e.transition_payment(intent_id, "USER_ACTION_REQUIRED", "test user action")
    e.transition_payment(intent_id, "TX_OBSERVED", "test tx observed")
    e.transition_payment(intent_id, "REJECTED", "test rejection")


def seed_available_credit(e, principal_id):
    now = "2026-09-03T00:00:00+00:00"
    with e._connect() as c:
        c.execute(
            "INSERT INTO activation_credits(principal_id,activation_intent_id,amount,state,reserved_case_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (principal_id, f"seed-{principal_id}", "50", "AVAILABLE", None, now, now),
        )


def test_activation_secondary_key_replay_stays_bound_to_original_coalesced_intent_after_rejection():
    e = engine()
    primary = e.create_activation_intent(
        principal_id="sic-alias",
        payer="0x1111111111111111111111111111111111111111",
        request_id="req-primary",
        idempotency_key="idem-primary",
    )
    secondary = e.create_activation_intent(
        principal_id="sic-alias",
        payer="0x1111111111111111111111111111111111111111",
        request_id="req-secondary",
        idempotency_key="idem-secondary",
    )
    assert secondary["intent_id"] == primary["intent_id"]

    reject_intent(e, primary["intent_id"])
    replay = e.create_activation_intent(
        principal_id="sic-alias",
        payer="0x1111111111111111111111111111111111111111",
        request_id="req-secondary",
        idempotency_key="idem-secondary",
    )

    assert replay["intent_id"] == primary["intent_id"]
    assert replay["state"] == "REJECTED"
    with e._connect() as c:
        assert c.execute("SELECT COUNT(*) FROM payment_intents").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM economic_intents WHERE purpose='ACTIVATION'").fetchone()[0] == 1


def test_case_secondary_key_replay_stays_bound_to_original_coalesced_intent_after_rejection():
    e = engine()
    seed_available_credit(e, "sic-case-alias")
    primary = e.create_case_payment_intent(
        principal_id="sic-case-alias",
        case_id="case-alias",
        payer="0x2222222222222222222222222222222222222222",
        request_id="req-case-primary",
        idempotency_key="idem-case-primary",
    )
    secondary = e.create_case_payment_intent(
        principal_id="sic-case-alias",
        case_id="case-alias",
        payer="0x2222222222222222222222222222222222222222",
        request_id="req-case-secondary",
        idempotency_key="idem-case-secondary",
    )
    assert secondary["intent_id"] == primary["intent_id"]

    reject_intent(e, primary["intent_id"])
    assert e.get_activation_credit("sic-case-alias")["state"] == "AVAILABLE"
    replay = e.create_case_payment_intent(
        principal_id="sic-case-alias",
        case_id="case-alias",
        payer="0x2222222222222222222222222222222222222222",
        request_id="req-case-secondary",
        idempotency_key="idem-case-secondary",
    )

    assert replay["intent_id"] == primary["intent_id"]
    assert replay["state"] == "REJECTED"
    assert e.get_activation_credit("sic-case-alias")["state"] == "AVAILABLE"
    with e._connect() as c:
        assert c.execute("SELECT COUNT(*) FROM payment_intents WHERE case_id='case-alias'").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM economic_intents WHERE purpose='CASE' AND case_id='case-alias'").fetchone()[0] == 1
