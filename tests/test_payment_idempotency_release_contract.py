import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from evidence_payment import EvidencePaymentEngine, EvidencePaymentError


def engine():
    root = Path(tempfile.mkdtemp())
    return EvidencePaymentEngine(root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence")


def assert_integrity(e):
    with e._connect() as c:
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []


def create_generic(e, *, case_id="case-a", entitlement_ref="ent-a", payer="0xpayer-a", asset="POL", expected_value="500", request_id="req-a", key="idem-shared"):
    return e.create_payment_intent(
        case_id=case_id,
        entitlement_ref=entitlement_ref,
        payer=payer,
        asset=asset,
        expected_value=expected_value,
        request_id=request_id,
        idempotency_key=key,
    )


def test_exact_generic_replay_is_idempotent_without_duplicate_event():
    e = engine()
    first = create_generic(e)
    second = create_generic(e)
    assert second["intent_id"] == first["intent_id"]
    with e._connect() as c:
        assert c.execute("SELECT COUNT(*) FROM payment_intents WHERE idempotency_key='idem-shared'").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM payment_events WHERE intent_id=?", (first["intent_id"],)).fetchone()[0] == 1
    assert_integrity(e)


@pytest.mark.parametrize(
    "override",
    [
        {"case_id": "case-b"},
        {"entitlement_ref": "ent-b"},
        {"payer": "0xpayer-b"},
        {"asset": "USDT0"},
        {"expected_value": "450"},
        {"request_id": "req-b"},
    ],
)
def test_generic_same_key_changed_security_payload_fails_closed(override):
    e = engine()
    first = create_generic(e)
    kwargs = dict(case_id="case-a", entitlement_ref="ent-a", payer="0xpayer-a", asset="POL", expected_value="500", request_id="req-a", key="idem-shared")
    kwargs.update(override)
    with pytest.raises(EvidencePaymentError):
        create_generic(e, **kwargs)
    with e._connect() as c:
        assert c.execute("SELECT COUNT(*) FROM payment_intents WHERE idempotency_key='idem-shared'").fetchone()[0] == 1
        row = c.execute("SELECT case_id,entitlement_ref,payer,asset,expected_value,request_id FROM payment_intents WHERE intent_id=?", (first["intent_id"],)).fetchone()
        assert tuple(row) == ("case-a", "ent-a", "0xpayer-a", "POL", "500", "req-a")
    assert_integrity(e)


def test_activation_same_key_changed_principal_fails_closed():
    e = engine()
    first = e.create_activation_intent(principal_id="sic-a", payer="0xpayer-a", request_id="req-a", idempotency_key="idem-activation")
    with pytest.raises(EvidencePaymentError):
        e.create_activation_intent(principal_id="sic-b", payer="0xpayer-a", request_id="req-a", idempotency_key="idem-activation")
    assert first["case_id"] == "activation:sic-a"
    with e._connect() as c:
        assert c.execute("SELECT COUNT(*) FROM economic_intents WHERE intent_id=? AND principal_id='sic-a'", (first["intent_id"],)).fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM economic_intents WHERE principal_id='sic-b'").fetchone()[0] == 0
    assert_integrity(e)


def test_activation_same_key_changed_payer_fails_closed():
    e = engine()
    first = e.create_activation_intent(principal_id="sic-a", payer="0xpayer-a", request_id="req-a", idempotency_key="idem-activation")
    with pytest.raises(EvidencePaymentError):
        e.create_activation_intent(principal_id="sic-a", payer="0xpayer-b", request_id="req-a", idempotency_key="idem-activation")
    assert first["payer"] == "0xpayer-a"
    assert_integrity(e)


def seed_available_credit(e, principal_id):
    now = "2026-09-02T00:00:00+00:00"
    with e._connect() as c:
        c.execute(
            "INSERT INTO activation_credits(principal_id,activation_intent_id,amount,state,reserved_case_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (principal_id, f"seed-{principal_id}", "50", "AVAILABLE", None, now, now),
        )


def test_case_same_key_changed_principal_case_or_payer_fails_closed_without_credit_leakage():
    e = engine()
    seed_available_credit(e, "sic-a")
    first = e.create_case_payment_intent(principal_id="sic-a", case_id="case-a", payer="0xpayer-a", request_id="req-a", idempotency_key="idem-case")
    assert first["expected_value"] == "450"
    assert e.get_activation_credit("sic-a")["state"] == "RESERVED"

    conflicts = [
        dict(principal_id="sic-b", case_id="case-a", payer="0xpayer-a", request_id="req-a"),
        dict(principal_id="sic-a", case_id="case-b", payer="0xpayer-a", request_id="req-a"),
        dict(principal_id="sic-a", case_id="case-a", payer="0xpayer-b", request_id="req-a"),
    ]
    for payload in conflicts:
        with pytest.raises(EvidencePaymentError):
            e.create_case_payment_intent(idempotency_key="idem-case", **payload)

    credit = e.get_activation_credit("sic-a")
    assert credit["state"] == "RESERVED" and credit["reserved_case_id"] == "case-a"
    with e._connect() as c:
        assert c.execute("SELECT COUNT(*) FROM payment_intents WHERE idempotency_key='idem-case'").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM economic_intents WHERE purpose='CASE'").fetchone()[0] == 1
    assert_integrity(e)


def test_conflicting_concurrent_same_key_has_one_winner_and_one_fail_closed():
    e = engine()
    barrier = Barrier(2)

    def attempt(n):
        barrier.wait()
        try:
            intent = create_generic(
                e,
                case_id=f"case-{n}",
                entitlement_ref=f"ent-{n}",
                payer=f"0xpayer-{n}",
                request_id=f"req-{n}",
                key="idem-race",
            )
            return ("ok", intent["intent_id"], intent["case_id"])
        except EvidencePaymentError as exc:
            return ("error", exc.code, None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (1, 2)))
    assert sum(r[0] == "ok" for r in results) == 1
    assert sum(r[0] == "error" for r in results) == 1
    with e._connect() as c:
        assert c.execute("SELECT COUNT(*) FROM payment_intents WHERE idempotency_key='idem-race'").fetchone()[0] == 1
    assert_integrity(e)
