from pathlib import Path

import pytest

from admin import ADMIN_ROLE, AdminAPI, AdminError
from bot.support_mvp import build_case_support_request, build_safe_case_notification
from core import CaseEngine, CoreAPI, CoreError


def _user_with_session(core: CaseEngine, sic_id: str, suffix: str) -> tuple[dict, dict]:
    user = core.register_user(sic_id, {}, f"reg-{suffix}", f"req-reg-{suffix}")
    session = core.create_session(
        user["user_id"],
        user["sic_id"],
        f"req-session-{suffix}",
        f"idem-session-{suffix}",
        3600,
    )
    return user, session


def test_core_api_requires_live_session_and_derives_case_subject(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    api = CoreAPI(db)
    user_a, session_a = _user_with_session(core, "SIC-API-A", "a")
    user_b, session_b = _user_with_session(core, "SIC-API-B", "b")

    opened = api.create_case(
        session_id=session_a["session_id"],
        sic_id=user_a["sic_id"],
        wallet=None,
        project_ref="unknown-project",
        search_hit=False,
        request_id="req-case-a",
        idempotency_key="idem-case-a",
    )
    assert opened["project_truth"] == "TO_VERIFY"
    assert api.resume_case(
        session_id=session_a["session_id"],
        sic_id=user_a["sic_id"],
        case_id=opened["case_id"],
    )["user_id"] == user_a["user_id"]

    with pytest.raises(CoreError) as exc:
        api.resume_case(
            session_id=session_b["session_id"],
            sic_id=user_b["sic_id"],
            case_id=opened["case_id"],
        )
    assert exc.value.code == "CASE_NOT_FOUND"

    with pytest.raises(CoreError) as exc:
        api.create_case(
            session_id="",
            sic_id=user_a["sic_id"],
            wallet=None,
            project_ref="unknown-project",
            search_hit=False,
            request_id="req-no-session",
            idempotency_key="idem-no-session",
        )
    assert exc.value.code == "SESSION_REQUIRED"

    core.revoke_session(session_a["session_id"], user_a["user_id"])
    with pytest.raises(CoreError) as exc:
        api.resume_case(
            session_id=session_a["session_id"],
            sic_id=user_a["sic_id"],
            case_id=opened["case_id"],
        )
    assert exc.value.code == "SESSION_INACTIVE"


def test_core_api_user_cannot_submit_privileged_activation_authorization(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    api = CoreAPI(db)
    user, session = _user_with_session(core, "SIC-API-PAID", "paid")

    opened = api.create_case(
        session_id=session["session_id"],
        sic_id=user["sic_id"],
        wallet=None,
        project_ref="project:unknown",
        search_hit=False,
        request_id="req-paid-case",
        idempotency_key="idem-paid-case",
    )
    state = api.transition_case(
        session_id=session["session_id"],
        sic_id=user["sic_id"],
        case_id=opened["case_id"],
        new_state="TRIAGE",
        reason="user triage",
        request_id="req-paid-1",
        idempotency_key="idem-paid-1",
        expected_version=1,
    )
    state = api.transition_case(
        session_id=session["session_id"],
        sic_id=user["sic_id"],
        case_id=opened["case_id"],
        new_state="PRODUCT_SELECTED",
        reason="product selected",
        request_id="req-paid-2",
        idempotency_key="idem-paid-2",
        expected_version=state["version"],
    )

    with pytest.raises(CoreError) as exc:
        api.transition_case(
            session_id=session["session_id"],
            sic_id=user["sic_id"],
            case_id=opened["case_id"],
            new_state="ACTIVE",
            reason="caller tries to activate",
            request_id="req-paid-3",
            idempotency_key="idem-paid-3",
            expected_version=state["version"],
        )
    assert exc.value.code == "MISSING_ENTITLEMENT"


def test_core_api_next_action_is_session_scoped(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    api = CoreAPI(db)
    user, session = _user_with_session(core, "SIC-API-NEXT", "next")
    opened = api.create_case(
        session_id=session["session_id"],
        sic_id=user["sic_id"],
        wallet=None,
        project_ref=None,
        search_hit=False,
        request_id="req-next-case",
        idempotency_key="idem-next-case",
    )
    core.add_task(
        opened["case_id"],
        user["user_id"],
        "Submit recovery details",
        "OPEN_RECOVERY_CHECKLIST",
    )

    action = api.next_action(
        session_id=session["session_id"],
        sic_id=user["sic_id"],
        case_id=opened["case_id"],
    )
    assert action is not None
    assert action["next_action"] == "OPEN_RECOVERY_CHECKLIST"

    core.revoke_session(session["session_id"], user["user_id"])
    with pytest.raises(CoreError) as exc:
        api.next_action(
            session_id=session["session_id"],
            sic_id=user["sic_id"],
            case_id=opened["case_id"],
        )
    assert exc.value.code == "SESSION_INACTIVE"


def test_core_api_rejects_unattributable_or_non_idempotent_mutations(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    api = CoreAPI(db)
    user, session = _user_with_session(core, "SIC-API-AUDIT", "audit")

    with pytest.raises(CoreError) as exc:
        api.create_case(
            session_id=session["session_id"],
            sic_id=user["sic_id"],
            wallet=None,
            project_ref="unknown-project",
            search_hit=False,
            request_id="",
            idempotency_key="idem-audit-case",
        )
    assert exc.value.code == "REQUEST_ID_REQUIRED"

    with pytest.raises(CoreError) as exc:
        api.create_case(
            session_id=session["session_id"],
            sic_id=user["sic_id"],
            wallet=None,
            project_ref="unknown-project",
            search_hit=False,
            request_id="req-audit-case",
            idempotency_key=" ",
        )
    assert exc.value.code == "IDEMPOTENCY_KEY_REQUIRED"

    opened = api.create_case(
        session_id=session["session_id"],
        sic_id=user["sic_id"],
        wallet=None,
        project_ref="unknown-project",
        search_hit=False,
        request_id="req-audit-good",
        idempotency_key="idem-audit-good",
    )
    with pytest.raises(CoreError) as exc:
        api.transition_case(
            session_id=session["session_id"],
            sic_id=user["sic_id"],
            case_id=opened["case_id"],
            new_state="TRIAGE",
            reason=" ",
            request_id="req-audit-transition",
            idempotency_key="idem-audit-transition",
            expected_version=1,
        )
    assert exc.value.code == "REASON_REQUIRED"

    with core.conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM core_cases WHERE user_id=?", (user["user_id"],)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM core_requests WHERE idempotency_key='' ").fetchone()[0] == 0


def test_core_support_owner_verdict_is_live_minimized_and_consumer_compatible(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    api = CoreAPI(db)
    user_a, session_a = _user_with_session(core, "SIC-SUPPORT-A", "support-a")
    user_b, session_b = _user_with_session(core, "SIC-SUPPORT-B", "support-b")
    opened = api.create_case(
        session_id=session_a["session_id"],
        sic_id=user_a["sic_id"],
        wallet=None,
        project_ref="unknown-project",
        search_hit=False,
        request_id="req-support-case",
        idempotency_key="idem-support-case",
    )

    verdict = api.support_case_authorization(
        session_id=session_a["session_id"],
        sic_id=user_a["sic_id"],
        case_id=opened["case_id"],
    )
    assert verdict == {
        "case_id": opened["case_id"],
        "requester_is_case_owner": True,
        "case_state": "DRAFT",
        "case_version": 1,
    }
    assert not ({"user_id", "sic_id", "wallet", "evidence", "payment"} & set(verdict))

    support = build_case_support_request(
        case_id=verdict["case_id"],
        summary="I need help understanding the next recovery step.",
        category="CASE",
        requester_is_case_owner=verdict["requester_is_case_owner"],
    )
    assert support.case_id == opened["case_id"]

    notification = build_safe_case_notification(
        case_id=verdict["case_id"],
        event_type="STATUS_CHANGED",
        case_version=verdict["case_version"],
        requester_is_case_owner=verdict["requester_is_case_owner"],
    )
    assert notification.case_id == opened["case_id"]
    assert notification.idempotency_key.startswith("support-notify-")

    with pytest.raises(CoreError) as exc:
        api.support_case_authorization(
            session_id=session_b["session_id"],
            sic_id=user_b["sic_id"],
            case_id=opened["case_id"],
        )
    assert exc.value.code == "CASE_NOT_FOUND"

    core.revoke_session(session_a["session_id"], user_a["user_id"])
    with pytest.raises(CoreError) as exc:
        api.support_case_authorization(
            session_id=session_a["session_id"],
            sic_id=user_a["sic_id"],
            case_id=opened["case_id"],
        )
    assert exc.value.code == "SESSION_INACTIVE"


def test_admin_api_derives_actor_and_roles_from_trusted_session_resolver(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    user, _ = _user_with_session(core, "SIC-ADMIN-API", "admin-user")
    opened = core.open_case(
        user["user_id"],
        user["sic_id"],
        None,
        "unknown-project",
        False,
        "USER",
        "req-admin-case",
        "idem-admin-case",
    )

    principals = {
        "admin-token": {"actor": "admin-1", "roles": [ADMIN_ROLE]},
        "user-token": {"actor": "plain-user", "roles": []},
    }

    def resolver(token: str):
        if token not in principals:
            raise KeyError(token)
        return principals[token]

    admin = AdminAPI(db, resolver)
    lookup = admin.user_lookup(admin_session_id="admin-token", sic_id=user["sic_id"])
    assert lookup["case_count"] == 1

    transitioned = admin.transition_case(
        admin_session_id="admin-token",
        case_id=opened["case_id"],
        new_state="TRIAGE",
        reason="manual review triage",
        request_id="req-admin-transition",
        idempotency_key="idem-admin-transition",
        expected_version=1,
    )
    assert transitioned["state"] == "TRIAGE"

    timeline = admin.crm_timeline(admin_session_id="admin-token", sic_id=user["sic_id"])
    assert timeline[0]["actor"] == "admin-1"
    assert timeline[0]["authorization"] == "ADMIN_REVIEW"

    with pytest.raises(AdminError) as exc:
        admin.user_lookup(admin_session_id="user-token", sic_id=user["sic_id"])
    assert exc.value.code == "ADMIN_FORBIDDEN"

    with pytest.raises(AdminError) as exc:
        admin.case_queue(admin_session_id="forged-token")
    assert exc.value.code == "ADMIN_SESSION_INVALID"

    with pytest.raises(AdminError) as exc:
        admin.case_queue(admin_session_id="")
    assert exc.value.code == "ADMIN_SESSION_REQUIRED"
