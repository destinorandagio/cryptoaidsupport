from concurrent.futures import ThreadPoolExecutor
import inspect
from pathlib import Path

import pytest

from core import CaseEngine, CoreError, TrustedSupportAPI


def _fixture(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    owner = core.register_user("SIC-SUPPORT-OWNER", {}, "reg-owner", "req-owner")
    other = core.register_user("SIC-SUPPORT-OTHER", {}, "reg-other", "req-other")
    owner_session = core.create_session(
        owner["user_id"], owner["sic_id"], "req-owner-session", "idem-owner-session", 3600
    )
    other_session = core.create_session(
        other["user_id"], other["sic_id"], "req-other-session", "idem-other-session", 3600
    )
    case = core.open_case(
        owner["user_id"],
        owner["sic_id"],
        None,
        "project:unknown",
        False,
        "USER",
        "req-case",
        "idem-case",
    )
    mapping = {
        "support-owner": {
            "session_id": owner_session["session_id"],
            "sic_id": owner["sic_id"],
        },
        "support-other": {
            "session_id": other_session["session_id"],
            "sic_id": other["sic_id"],
        },
    }

    def resolver(token: str):
        return mapping[token]

    return db, core, owner, other, owner_session, other_session, case, resolver


def _assert_uniform_denial(exc: pytest.ExceptionInfo[CoreError]) -> None:
    assert exc.value.code == "SUPPORT_AUTHORIZATION_FAILED"
    assert exc.value.status == 403
    assert str(exc.value) == "support authorization failed"


def test_trusted_support_session_returns_only_minimized_core_owner_verdict(tmp_path: Path):
    db, _, owner, _, _, _, case, resolver = _fixture(tmp_path)
    api = TrustedSupportAPI(db, resolver)

    verdict = api.case_authorization(
        support_session_id="support-owner",
        case_id=case["case_id"],
    )

    assert set(verdict) == {
        "case_id",
        "requester_is_case_owner",
        "case_state",
        "case_version",
    }
    assert verdict["case_id"] == case["case_id"]
    assert verdict["requester_is_case_owner"] is True
    serialized = repr(verdict)
    assert owner["sic_id"] not in serialized
    assert owner["user_id"] not in serialized
    assert "wallet" not in serialized.lower()
    assert "evidence" not in serialized.lower()
    assert "payment" not in serialized.lower()


def test_support_contract_does_not_accept_user_id_or_raw_sic_id_from_caller():
    parameters = set(inspect.signature(TrustedSupportAPI.case_authorization).parameters)
    assert parameters == {"self", "support_session_id", "case_id"}
    assert "user_id" not in parameters
    assert "sic_id" not in parameters


def test_unknown_or_malformed_support_session_fails_uniformly(tmp_path: Path):
    db, _, _, _, _, _, case, resolver = _fixture(tmp_path)
    api = TrustedSupportAPI(db, resolver)

    with pytest.raises(CoreError) as unknown:
        api.case_authorization(support_session_id="forged-token", case_id=case["case_id"])
    _assert_uniform_denial(unknown)

    malformed = TrustedSupportAPI(db, lambda _: {"user_id": "usr-forged", "sic_id": "SIC-FORGED"})
    with pytest.raises(CoreError) as missing_live_session:
        malformed.case_authorization(
            support_session_id="support-forged",
            case_id=case["case_id"],
        )
    _assert_uniform_denial(missing_live_session)


def test_cross_user_case_lookup_is_indistinguishable_from_other_auth_failure(tmp_path: Path):
    db, _, _, _, _, _, case, resolver = _fixture(tmp_path)
    api = TrustedSupportAPI(db, resolver)

    with pytest.raises(CoreError) as exc:
        api.case_authorization(
            support_session_id="support-other",
            case_id=case["case_id"],
        )
    _assert_uniform_denial(exc)


def test_revocation_of_core_session_immediately_invalidates_support_principal(tmp_path: Path):
    db, core, owner, _, owner_session, _, case, resolver = _fixture(tmp_path)
    api = TrustedSupportAPI(db, resolver)
    core.revoke_session(owner_session["session_id"], owner["user_id"])

    with pytest.raises(CoreError) as exc:
        api.case_authorization(
            support_session_id="support-owner",
            case_id=case["case_id"],
        )
    _assert_uniform_denial(exc)


def test_resolver_configuration_is_required(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    CaseEngine(db)

    with pytest.raises(CoreError) as exc:
        TrustedSupportAPI(db, None)  # type: ignore[arg-type]
    assert exc.value.code == "SUPPORT_RESOLVER_REQUIRED"
    assert exc.value.status == 500


def test_eight_concurrent_case_retries_converge_to_one_case_event_and_request(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    owner = core.register_user("SIC-EIGHT-WAY", {}, "reg-eight", "req-reg-eight")

    def create(index: int):
        return core.open_case(
            owner["user_id"],
            owner["sic_id"],
            None,
            "project:race-unknown",
            False,
            "USER",
            f"req-eight-{index}",
            "idem-eight-way-case",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(create, range(8)))

    assert len(results) == 8
    assert all(result == results[0] for result in results)
    assert results[0]["project_truth"] == "TO_VERIFY"
    with core.conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM core_cases").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM core_case_events").fetchone()[0] == 1
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM core_requests WHERE idempotency_key=? AND operation='open_case'",
                ("idem-eight-way-case",),
            ).fetchone()[0]
            == 1
        )
