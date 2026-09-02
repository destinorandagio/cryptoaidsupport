from pathlib import Path

import pytest

from admin import ADMIN_ROLE, AdminError, AdminOps
from core import CaseEngine, CoreError
from evidence_payment import EvidencePaymentEngine


def test_sic_session_idempotency_resume_and_revoke(tmp_path: Path):
    core = CaseEngine(tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite")
    user = core.register_user("SIC-SESSION-1", {}, "reg-session", "req-reg-session")

    session = core.create_session(user["user_id"], user["sic_id"], "req-s1", "idem-s1", 3600)
    replay = core.create_session(user["user_id"], user["sic_id"], "req-s1b", "idem-s1", 3600)
    assert replay == session
    assert core.resume_session(session["session_id"], user["sic_id"])["status"] == "ACTIVE"

    with pytest.raises(CoreError) as exc:
        core.resume_session(session["session_id"], "SIC-WRONG")
    assert exc.value.code == "SIC_ID_MISMATCH"

    assert core.revoke_session(session["session_id"], user["user_id"])["status"] == "REVOKED"
    with pytest.raises(CoreError) as exc:
        core.resume_session(session["session_id"], user["sic_id"])
    assert exc.value.code == "SESSION_INACTIVE"


def test_paid_active_rejects_forged_entitlement_authorization(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    user = core.register_user("SIC-PAID-GUARD", {}, "reg-paid", "req-reg-paid")
    case = core.open_case(user["user_id"], user["sic_id"], None, "unknown", False, "USER", "req-case", "idem-case")
    state = core.transition(case["case_id"], user["user_id"], "TRIAGE", "USER", "triage", "r1", "i1", "OWNER", 1)
    state = core.transition(case["case_id"], user["user_id"], "PRODUCT_SELECTED", "USER", "product", "r2", "i2", "OWNER", state["version"])

    with pytest.raises(CoreError) as exc:
        core.transition(case["case_id"], user["user_id"], "ACTIVE", "SYSTEM", "forged", "r3", "i3", "ENTITLEMENT_GRANTED", state["version"])
    assert exc.value.code == "MISSING_ENTITLEMENT"


def test_mvp_golden_path_core_payment_admin(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    payments = EvidencePaymentEngine(db, tmp_path / "private-evidence")
    admin = AdminOps(db)

    user = core.register_user("SIC-GOLDEN-1", {"locale": "it"}, "reg-1", "req-reg-1")
    returning = core.register_user("SIC-GOLDEN-1", {}, "reg-2", "req-reg-2")
    assert returning["returning"] is True and returning["user_id"] == user["user_id"]

    session = core.create_session(user["user_id"], user["sic_id"], "req-session", "idem-session", 3600)
    assert core.resume_session(session["session_id"], user["sic_id"])["user_id"] == user["user_id"]

    opened = core.open_case(
        user["user_id"], user["sic_id"], None, "project:unknown", False,
        "USER", "req-case", "idem-case",
    )
    assert opened["project_truth"] == "TO_VERIFY"
    replay = core.open_case(
        user["user_id"], user["sic_id"], None, "project:unknown", False,
        "USER", "req-case-replay", "idem-case",
    )
    assert replay["case_id"] == opened["case_id"]

    state = core.transition(opened["case_id"], user["user_id"], "TRIAGE", "USER", "triage", "r1", "c1", "OWNER", 1)
    state = core.transition(opened["case_id"], user["user_id"], "PRODUCT_SELECTED", "USER", "paid case", "r2", "c2", "OWNER", state["version"])

    evidence = payments.store_evidence(
        case_id=opened["case_id"], content=b"%PDF-1.4 synthetic evidence", original_name="proof.pdf",
        mime_declared="application/pdf", mime_detected="application/pdf", uploader=user["sic_id"],
        consent_id="CONSENT-GOLDEN-1", authorization="OWNER",
    )
    assert evidence["status"] == "AVAILABLE"

    state = core.transition(opened["case_id"], user["user_id"], "EVIDENCE_REQUIRED", "SYSTEM", "evidence route", "r3", "c3", "OWNER", state["version"])
    state = core.transition(opened["case_id"], user["user_id"], "CONSENT_REQUIRED", "USER", "consent", "r4", "c4", "OWNER", state["version"])
    state = core.transition(opened["case_id"], user["user_id"], "PAYMENT_REQUIRED", "SYSTEM", "payment", "r5", "c5", "OWNER", state["version"])
    state = core.transition(opened["case_id"], user["user_id"], "PAYMENT_VERIFYING", "SYSTEM", "intent", "r6", "c6", "OWNER", state["version"])

    payer = "0x0000000000000000000000000000000000000001"
    intent = payments.create_payment_intent(
        case_id=opened["case_id"], entitlement_ref="ENT-GOLDEN-1", payer=payer,
        asset="POL", expected_value="450", request_id="pay-r1", idempotency_key="pay-i1",
    )
    payments.transition_payment(intent["intent_id"], "USER_ACTION_REQUIRED", "user action")
    payments.transition_payment(intent["intent_id"], "TX_OBSERVED", "synthetic observation")
    payments.transition_payment(intent["intent_id"], "VERIFYING", "provider verification")
    payments.transition_payment(intent["intent_id"], "FINALITY_PENDING", "await confirmations")

    tx_hash = "0x" + "ab" * 32
    block_hash = "0x" + "cd" * 32
    observation = {
        "chain_id": 137,
        "from": payer,
        "to": intent["treasury_address"],
        "value": "450",
        "asset": "POL",
        "receipt_status": 1,
        "case_id": opened["case_id"],
        "entitlement_ref": "ENT-GOLDEN-1",
        "tx_hash": tx_hash,
        "block_hash": block_hash,
        "confirmations": 12,
        "required_confirmations": 2,
    }
    providers = [
        {"provider_id": "rpc_a", "tx_hash": tx_hash, "block_hash": block_hash, "receipt_status": 1},
        {"provider_id": "rpc_b", "tx_hash": tx_hash, "block_hash": block_hash, "receipt_status": 1},
    ]
    settled = payments.settle(intent["intent_id"], observation, providers)
    assert settled["verdict"] == "SETTLED" and settled["entitlement_granted"] is True

    active = core.transition(
        opened["case_id"], user["user_id"], "ACTIVE", "SYSTEM", "settled entitlement",
        "r7", "c7", "ENTITLEMENT_GRANTED", state["version"],
    )
    assert active["state"] == "ACTIVE"

    task = core.add_task(opened["case_id"], user["user_id"], "Submit recovery details", "OPEN_RECOVERY_CHECKLIST")
    assert task["next_action"] == "OPEN_RECOVERY_CHECKLIST"

    lookup = admin.user_lookup(roles=[ADMIN_ROLE], sic_id=user["sic_id"])
    assert lookup["case_count"] == 1 and lookup["active_sessions"] == 1
    summary = admin.case_summary(roles=[ADMIN_ROLE], case_id=opened["case_id"])
    assert summary["state"] == "ACTIVE" and summary["open_tasks"] == 1
    timeline = admin.crm_timeline(roles=[ADMIN_ROLE], sic_id=user["sic_id"])
    assert timeline[0]["new_state"] == "ACTIVE"
    assert timeline[0]["authorization"] == "ENTITLEMENT_GRANTED"

    with pytest.raises(AdminError) as exc:
        admin.user_lookup(roles=[], sic_id=user["sic_id"])
    assert exc.value.code == "ADMIN_FORBIDDEN"
