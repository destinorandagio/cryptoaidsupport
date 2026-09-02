from dataclasses import asdict
from pathlib import Path

import pytest

from bot.support_core_adapter import CoreLinkedSupportAdapter
from bot.support_mvp import SupportRejected
from core import CaseEngine


def _fixture(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    owner = core.register_user("SIC-SUPPORT-OWNER", {}, "reg-owner", "req-owner")
    other = core.register_user("SIC-SUPPORT-OTHER", {}, "reg-other", "req-other")
    owner_session = core.create_session(owner["user_id"], owner["sic_id"], "req-s-owner", "idem-s-owner", 3600)
    other_session = core.create_session(other["user_id"], other["sic_id"], "req-s-other", "idem-s-other", 3600)
    case = core.open_case(
        owner["user_id"], owner["sic_id"], None, "project:unknown", False,
        "USER", "req-case", "idem-case",
    )
    return db, core, owner, other, owner_session, other_session, case


def test_owner_session_builds_minimized_case_support_and_notification(tmp_path: Path):
    db, _, owner, _, owner_session, _, case = _fixture(tmp_path)
    adapter = CoreLinkedSupportAdapter(db)

    request = adapter.build_request(
        session_id=owner_session["session_id"],
        sic_id=owner["sic_id"],
        case_id=case["case_id"],
        summary="I need help understanding the next recovery action.",
        category="RECOVERY",
        escalate=True,
    )
    assert request.case_id == case["case_id"]
    assert request.category == "RECOVERY"
    assert request.escalate is True

    notification = adapter.build_notification(
        session_id=owner_session["session_id"],
        sic_id=owner["sic_id"],
        case_id=case["case_id"],
        event_type="ACTION_REQUIRED",
    )
    payload = asdict(notification)
    assert payload["case_id"] == case["case_id"]
    assert payload["case_version"] == 1
    assert payload["idempotency_key"].startswith("support-notify-")
    serialized = repr(payload)
    assert owner["sic_id"] not in serialized
    assert "wallet" not in serialized.lower()
    assert "evidence" not in serialized.lower()
    assert "payment" not in serialized.lower()


def test_cross_user_case_access_fails_with_uniform_support_error(tmp_path: Path):
    db, _, _, other, _, other_session, case = _fixture(tmp_path)
    adapter = CoreLinkedSupportAdapter(db)

    with pytest.raises(SupportRejected) as exc:
        adapter.build_request(
            session_id=other_session["session_id"],
            sic_id=other["sic_id"],
            case_id=case["case_id"],
            summary="status please",
        )
    assert str(exc.value) == "case_support_authorization_failed"


def test_revoked_session_fails_closed_before_support_payload(tmp_path: Path):
    db, core, owner, _, owner_session, _, case = _fixture(tmp_path)
    adapter = CoreLinkedSupportAdapter(db)
    core.revoke_session(owner_session["session_id"], owner["user_id"])

    with pytest.raises(SupportRejected) as exc:
        adapter.build_notification(
            session_id=owner_session["session_id"],
            sic_id=owner["sic_id"],
            case_id=case["case_id"],
            event_type="STATUS_CHANGED",
        )
    assert str(exc.value) == "case_support_authorization_failed"


def test_secret_summary_remains_rejected_after_valid_owner_authorization(tmp_path: Path):
    db, _, owner, _, owner_session, _, case = _fixture(tmp_path)
    adapter = CoreLinkedSupportAdapter(db)

    with pytest.raises(SupportRejected) as exc:
        adapter.build_request(
            session_id=owner_session["session_id"],
            sic_id=owner["sic_id"],
            case_id=case["case_id"],
            summary="my seed phrase is alpha beta gamma",
        )
    assert str(exc.value) == "secret_or_credential_detected"
