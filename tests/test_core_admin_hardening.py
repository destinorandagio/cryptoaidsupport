from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from admin import ADMIN_ROLE, AdminError, AdminOps
from core import CaseEngine, CaseError


def _engine(tmp_path):
    return CaseEngine(tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite")


def _user(core, *, sic_id="SIC-HARDEN", key="register-1"):
    return core.register_user(sic_id, {}, key, f"req-{key}")


def test_idempotency_key_is_operation_bound_and_wallet_binding_replays(tmp_path):
    core = _engine(tmp_path)
    user = _user(core, key="shared-key")

    with pytest.raises(CaseError) as exc:
        core.open_case(
            user["user_id"],
            user["sic_id"],
            None,
            "unknown",
            False,
            "USER",
            "req-case-conflict",
            "shared-key",
        )
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"
    assert exc.value.status == 409

    first = core.bind_wallet(
        user["user_id"], user["sic_id"], "0xAbC", "req-wallet-1", "wallet-key"
    )
    replay = core.bind_wallet(
        user["user_id"], user["sic_id"], "0xAbC", "req-wallet-2", "wallet-key"
    )
    assert replay == first

    with core.conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM core_wallet_bindings").fetchone()[0] == 1
        request = conn.execute(
            "SELECT operation FROM core_requests WHERE idempotency_key='wallet-key'"
        ).fetchone()
    assert request["operation"] == "bind_wallet"


def test_concurrent_case_retry_creates_one_case_and_replays_one_response(tmp_path):
    core = _engine(tmp_path)
    user = _user(core)

    def create(index):
        return core.open_case(
            user["user_id"],
            user["sic_id"],
            None,
            "unknown-project",
            False,
            "USER",
            f"req-race-{index}",
            "case-race-key",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, (1, 2)))

    assert results[0] == results[1]
    assert results[0]["project_truth"] == "TO_VERIFY"
    with core.conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM core_cases").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM core_case_events").fetchone()[0] == 1
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM core_requests WHERE idempotency_key='case-race-key' AND operation='open_case'"
            ).fetchone()[0]
            == 1
        )


def test_admin_override_requires_attributable_audit_fields(tmp_path):
    core = _engine(tmp_path)
    user = _user(core)
    opened = core.open_case(
        user["user_id"],
        user["sic_id"],
        None,
        "project:test",
        False,
        "USER",
        "req-case",
        "case-key",
    )
    admin = AdminOps(core.db_path)

    base = dict(
        roles=[ADMIN_ROLE],
        case_id=opened["case_id"],
        new_state="TRIAGE",
        actor="admin:reviewer",
        reason="manual review",
        request_id="admin-request",
        idempotency_key="admin-idem",
        expected_version=1,
    )
    for field, value, code in (
        ("actor", "  ", "ADMIN_ACTOR_REQUIRED"),
        ("reason", "", "ADMIN_REASON_REQUIRED"),
        ("request_id", " ", "ADMIN_REQUEST_ID_REQUIRED"),
        ("idempotency_key", "", "ADMIN_IDEMPOTENCY_KEY_REQUIRED"),
    ):
        args = dict(base)
        args[field] = value
        with pytest.raises(AdminError) as exc:
            admin.transition_case(**args)
        assert exc.value.code == code
        assert exc.value.status == 400

    assert core.get_case(opened["case_id"], user["user_id"])["state"] == "DRAFT"
    assert len(core.timeline(opened["case_id"], user["user_id"])) == 1


def test_admin_active_session_count_excludes_expired_rows(tmp_path):
    core = _engine(tmp_path)
    user = _user(core)
    session = core.create_session(
        user["user_id"], user["sic_id"], "req-session", "session-key", ttl_seconds=60
    )
    expired_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    with core.conn() as conn:
        conn.execute(
            "UPDATE core_sessions SET expires_at=? WHERE session_id=?",
            (expired_at, session["session_id"]),
        )

    admin = AdminOps(core.db_path)
    lookup = admin.user_lookup(roles=[ADMIN_ROLE], sic_id=user["sic_id"])
    assert lookup["active_sessions"] == 0
