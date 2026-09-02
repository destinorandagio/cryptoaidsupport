from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from core import CaseEngine, CoreAPI, CoreError


def _fixture(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    user = core.register_user("SIC-PRODUCT-1", {}, "reg-product", "req-reg-product")
    session = core.create_session(
        user["user_id"], user["sic_id"], "req-session", "idem-session", 3600
    )
    core.upsert_product("CASE-A", "CASE", "ACTIVE", {}, {"price_source": "CHAT02"}, 1)
    core.upsert_product("CASE-B", "CASE", "ACTIVE", {}, {"price_source": "CHAT02"}, 1)
    opened = core.open_case(
        user["user_id"],
        user["sic_id"],
        None,
        "project:unknown",
        False,
        "USER",
        "req-case",
        "idem-case",
    )
    return db, core, user, session, opened


def test_product_selection_exact_replay_is_single_audited_mutation(tmp_path: Path):
    db, core, user, _, opened = _fixture(tmp_path)

    first = core.select_product(
        opened["case_id"], user["user_id"], "CASE-A", "req-p1", "idem-p1", 1
    )
    replay = core.select_product(
        opened["case_id"], user["user_id"], "CASE-A", "req-p1-retry", "idem-p1", 1
    )

    assert replay == first
    assert first["version"] == 2
    case = core.get_case(opened["case_id"], user["user_id"])
    assert case["product_code"] == "CASE-A" and case["version"] == 2
    with core.conn() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM core_case_events WHERE case_id=? AND audit_event='CASE_PRODUCT_SELECTED'",
            (opened["case_id"],),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM core_requests WHERE idempotency_key='idem-p1' AND operation='select_product'"
        ).fetchone()[0] == 1
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_product_selection_same_key_changed_payload_fails_closed(tmp_path: Path):
    _, core, user, _, opened = _fixture(tmp_path)
    core.select_product(
        opened["case_id"], user["user_id"], "CASE-A", "req-p1", "idem-p1", 1
    )

    with pytest.raises(CoreError) as exc:
        core.select_product(
            opened["case_id"], user["user_id"], "CASE-B", "req-p2", "idem-p1", 1
        )
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"
    case = core.get_case(opened["case_id"], user["user_id"])
    assert case["product_code"] == "CASE-A" and case["version"] == 2


def test_product_selection_is_versioned_and_locked_before_payment_truth_can_drift(tmp_path: Path):
    _, core, user, _, opened = _fixture(tmp_path)
    selected = core.select_product(
        opened["case_id"], user["user_id"], "CASE-A", "req-p1", "idem-p1", 1
    )

    with pytest.raises(CoreError) as exc:
        core.select_product(
            opened["case_id"], user["user_id"], "CASE-B", "req-stale", "idem-stale", 1
        )
    assert exc.value.code == "STALE_STATE"

    triage = core.transition(
        opened["case_id"],
        user["user_id"],
        "TRIAGE",
        "USER",
        "triage",
        "req-triage",
        "idem-triage",
        "OWNER",
        selected["version"],
    )
    product_state = core.transition(
        opened["case_id"],
        user["user_id"],
        "PRODUCT_SELECTED",
        "USER",
        "confirm product",
        "req-product-state",
        "idem-product-state",
        "OWNER",
        triage["version"],
    )
    evidence_state = core.transition(
        opened["case_id"],
        user["user_id"],
        "EVIDENCE_REQUIRED",
        "SYSTEM",
        "evidence begins",
        "req-evidence",
        "idem-evidence",
        "OWNER",
        product_state["version"],
    )

    with pytest.raises(CoreError) as exc:
        core.select_product(
            opened["case_id"],
            user["user_id"],
            "CASE-B",
            "req-late-product",
            "idem-late-product",
            evidence_state["version"],
        )
    assert exc.value.code == "PRODUCT_SELECTION_LOCKED"
    case = core.get_case(opened["case_id"], user["user_id"])
    assert case["product_code"] == "CASE-A"


def test_eight_concurrent_same_key_product_retries_converge_once(tmp_path: Path):
    _, core, user, _, opened = _fixture(tmp_path)

    def attempt(index: int):
        worker = CaseEngine(core.db_path)
        return worker.select_product(
            opened["case_id"],
            user["user_id"],
            "CASE-A",
            f"req-race-{index}",
            "idem-race-product",
            1,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))

    assert len({(r["product_code"], r["version"]) for r in results}) == 1
    assert results[0]["product_code"] == "CASE-A" and results[0]["version"] == 2
    with core.conn() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM core_case_events WHERE case_id=? AND audit_event='CASE_PRODUCT_SELECTED'",
            (opened["case_id"],),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM core_requests WHERE idempotency_key='idem-race-product'"
        ).fetchone()[0] == 1


def test_core_api_product_selection_requires_live_session_and_mutation_metadata(tmp_path: Path):
    db, core, user, session, opened = _fixture(tmp_path)
    api = CoreAPI(db)

    selected = api.select_product(
        session_id=session["session_id"],
        sic_id=user["sic_id"],
        case_id=opened["case_id"],
        product_code="CASE-A",
        request_id="req-api-product",
        idempotency_key="idem-api-product",
        expected_version=1,
    )
    assert selected["version"] == 2

    with pytest.raises(CoreError) as exc:
        api.select_product(
            session_id=session["session_id"],
            sic_id=user["sic_id"],
            case_id=opened["case_id"],
            product_code="CASE-B",
            request_id="",
            idempotency_key="idem-api-empty",
            expected_version=2,
        )
    assert exc.value.code == "REQUEST_ID_REQUIRED"

    core.revoke_session(session["session_id"], user["user_id"])
    with pytest.raises(CoreError) as exc:
        api.select_product(
            session_id=session["session_id"],
            sic_id=user["sic_id"],
            case_id=opened["case_id"],
            product_code="CASE-B",
            request_id="req-after-revoke",
            idempotency_key="idem-after-revoke",
            expected_version=2,
        )
    assert exc.value.code == "SESSION_INACTIVE"
