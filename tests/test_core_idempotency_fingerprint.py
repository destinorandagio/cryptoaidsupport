from concurrent.futures import ThreadPoolExecutor

import pytest

from core import CaseEngine, CaseError


def _engine(tmp_path):
    return CaseEngine(tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite")


def _conflict(call):
    with pytest.raises(CaseError) as exc:
        call()
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"
    assert exc.value.status == 409


def test_same_operation_replay_is_subject_and_payload_bound(tmp_path):
    core = _engine(tmp_path)
    user_a = core.register_user("SIC-A", {"locale": "it"}, "reg-a", "req-reg-a")
    user_b = core.register_user("SIC-B", {}, "reg-b", "req-reg-b")

    # Transport request_id may change on an otherwise identical retry.
    assert (
        core.register_user("SIC-A", {"locale": "it"}, "reg-a", "req-reg-a-retry")
        == user_a
    )
    _conflict(lambda: core.register_user("SIC-OTHER", {"locale": "it"}, "reg-a", "req-x"))
    _conflict(lambda: core.register_user("SIC-A", {"locale": "en"}, "reg-a", "req-y"))

    session = core.create_session(
        user_a["user_id"], user_a["sic_id"], "req-session", "session-key", 60
    )
    assert (
        core.create_session(
            user_a["user_id"], user_a["sic_id"], "req-session-retry", "session-key", 60
        )
        == session
    )
    _conflict(
        lambda: core.create_session(
            user_b["user_id"], user_b["sic_id"], "req-other-session", "session-key", 60
        )
    )
    _conflict(
        lambda: core.create_session(
            user_a["user_id"], user_a["sic_id"], "req-ttl-change", "session-key", 120
        )
    )

    wallet = core.bind_wallet(
        user_a["user_id"], user_a["sic_id"], "0xAbC", "req-wallet", "wallet-key"
    )
    assert (
        core.bind_wallet(
            user_a["user_id"], user_a["sic_id"], "0xabc", "req-wallet-retry", "wallet-key"
        )
        == wallet
    )
    _conflict(
        lambda: core.bind_wallet(
            user_a["user_id"], user_a["sic_id"], "0xDef", "req-wallet-change", "wallet-key"
        )
    )

    opened = core.open_case(
        user_a["user_id"],
        user_a["sic_id"],
        "0xABC",
        "project:A",
        False,
        "USER",
        "req-case",
        "case-key",
    )
    assert (
        core.open_case(
            user_a["user_id"],
            user_a["sic_id"],
            "0xabc",
            "project:A",
            False,
            "USER",
            "req-case-retry",
            "case-key",
        )
        == opened
    )
    _conflict(
        lambda: core.open_case(
            user_a["user_id"],
            user_a["sic_id"],
            "0xabc",
            "project:B",
            False,
            "USER",
            "req-project-change",
            "case-key",
        )
    )
    _conflict(
        lambda: core.open_case(
            user_a["user_id"],
            user_a["sic_id"],
            "0xabc",
            "project:A",
            True,
            "USER",
            "req-search-change",
            "case-key",
        )
    )

    transitioned = core.transition(
        opened["case_id"],
        user_a["user_id"],
        "TRIAGE",
        "USER",
        "triage",
        "req-transition",
        "transition-key",
        "OWNER",
        1,
    )
    assert (
        core.transition(
            opened["case_id"],
            user_a["user_id"],
            "TRIAGE",
            "USER",
            "triage",
            "req-transition-retry",
            "transition-key",
            "OWNER",
            1,
        )
        == transitioned
    )
    _conflict(
        lambda: core.transition(
            opened["case_id"],
            user_a["user_id"],
            "TRIAGE",
            "USER",
            "triage",
            "req-auth-change",
            "transition-key",
            "ADMIN_REVIEW",
            1,
        )
    )


def test_concurrent_same_key_changed_project_fails_closed(tmp_path):
    core = _engine(tmp_path)
    user = core.register_user("SIC-RACE", {}, "reg-race", "req-reg-race")

    def create(project):
        try:
            result = core.open_case(
                user["user_id"],
                user["sic_id"],
                None,
                project,
                False,
                "USER",
                f"req-{project}",
                "same-key-different-payload",
            )
            return "ok", result
        except CaseError as exc:
            return "error", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, ("project:A", "project:B")))

    assert sorted(result[0] for result in results) == ["error", "ok"]
    assert [result[1] for result in results if result[0] == "error"] == ["IDEMPOTENCY_CONFLICT"]
    with core.conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM core_cases").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM core_case_events").fetchone()[0] == 1
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM core_requests WHERE idempotency_key='same-key-different-payload'"
            ).fetchone()[0]
            == 1
        )
