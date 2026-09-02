from pathlib import Path

import pytest

from admin import ADMIN_ROLE, AdminError, AdminOps
from core import CaseEngine, CoreError
from evidence_payment import EvidencePaymentEngine


def _bootstrap(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    user = core.register_user("SIC-ADMIN-TEST", {}, "reg-1", "req-reg-1")
    opened = core.open_case(
        user["user_id"],
        user["sic_id"],
        None,
        "project:test",
        False,
        "USER",
        "req-case-1",
        "case-1",
    )
    return db, core, user, opened


def test_admin_rbac_case_queue_and_summary(tmp_path: Path):
    db, _, _, opened = _bootstrap(tmp_path)
    admin = AdminOps(db)

    with pytest.raises(AdminError) as exc:
        admin.case_queue(roles=[])
    assert exc.value.code == "ADMIN_FORBIDDEN"

    queue = admin.case_queue(roles=[ADMIN_ROLE])
    assert [row["case_id"] for row in queue] == [opened["case_id"]]
    assert queue[0]["project_truth"] == "TO_VERIFY"
    assert "user_id" not in queue[0]
    assert "wallet" not in queue[0]

    summary = admin.case_summary(roles=[ADMIN_ROLE], case_id=opened["case_id"])
    assert summary["case_id"] == opened["case_id"]
    assert summary["event_count"] == 1
    assert summary["open_tasks"] == 0


def test_admin_transition_uses_core_guard_and_audit(tmp_path: Path):
    db, core, user, opened = _bootstrap(tmp_path)
    admin = AdminOps(db)

    triage = admin.transition_case(
        roles=[ADMIN_ROLE],
        case_id=opened["case_id"],
        new_state="TRIAGE",
        actor="admin:test",
        reason="manual triage",
        request_id="admin-r1",
        idempotency_key="admin-i1",
        expected_version=1,
    )
    assert triage["state"] == "TRIAGE"

    selected = admin.transition_case(
        roles=[ADMIN_ROLE],
        case_id=opened["case_id"],
        new_state="PRODUCT_SELECTED",
        actor="admin:test",
        reason="reviewed route",
        request_id="admin-r2",
        idempotency_key="admin-i2",
        expected_version=2,
    )
    assert selected["state"] == "PRODUCT_SELECTED"

    with pytest.raises(CoreError) as exc:
        admin.transition_case(
            roles=[ADMIN_ROLE],
            case_id=opened["case_id"],
            new_state="ACTIVE",
            actor="admin:test",
            reason="must not bypass entitlement",
            request_id="admin-r3",
            idempotency_key="admin-i3",
            expected_version=3,
        )
    assert exc.value.code == "MISSING_ENTITLEMENT"

    timeline = core.timeline(opened["case_id"], user["user_id"])
    assert timeline[-1]["authorization"] == "ADMIN_REVIEW"
    assert timeline[-1]["audit_event"] == "CASE_STATE_TRANSITION"


def test_manual_review_queue_is_read_only_payment_view(tmp_path: Path):
    db, _, _, opened = _bootstrap(tmp_path)
    payments = EvidencePaymentEngine(db, tmp_path / "private-evidence")
    intent = payments.create_payment_intent(
        case_id=opened["case_id"],
        entitlement_ref="ENT-TEST",
        payer="0x0000000000000000000000000000000000000001",
        asset="POL",
        expected_value="50",
        request_id="pay-r1",
        idempotency_key="pay-i1",
    )
    payments.transition_payment(intent["intent_id"], "USER_ACTION_REQUIRED", "user review")
    payments.transition_payment(intent["intent_id"], "TX_OBSERVED", "synthetic tx")
    payments.transition_payment(intent["intent_id"], "MANUAL_REVIEW", "provider disagreement")

    admin = AdminOps(db)
    rows = admin.manual_review_queue(roles=[ADMIN_ROLE])
    assert len(rows) == 1
    assert rows[0]["intent_id"] == intent["intent_id"]
    assert rows[0]["state"] == "MANUAL_REVIEW"
    assert "payer" not in rows[0]
    assert "treasury_address" not in rows[0]
