from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from core import AUTH_SESSION_GUARD_VERSION, CaseEngine, CoreError
from core.case_engine import CaseEngine as LegacyCaseEngine


def _count(db_path, table: str) -> int:
    with sqlite3.connect(db_path) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_auth_session_guard_is_versioned_and_applies_to_legacy_import(tmp_path):
    assert AUTH_SESSION_GUARD_VERSION == "1.0.0"
    db_path = tmp_path / "master.sqlite"
    engine = LegacyCaseEngine(db_path)

    with pytest.raises(CoreError) as exc:
        engine.register_user(
            "sic:legacy",
            {},
            idempotency_key="   ",
            request_id="req-legacy",
        )
    assert exc.value.code == "IDEMPOTENCY_KEY_REQUIRED"
    assert _count(db_path, "core_users") == 0
    assert _count(db_path, "core_requests") == 0


def test_register_user_rejects_blank_request_metadata_before_write(tmp_path):
    db_path = tmp_path / "master.sqlite"
    engine = CaseEngine(db_path)

    with pytest.raises(CoreError) as exc:
        engine.register_user(
            "sic:first",
            {"display": "first"},
            idempotency_key="idem-register-1",
            request_id="  ",
        )
    assert exc.value.code == "REQUEST_ID_REQUIRED"

    with pytest.raises(CoreError) as exc:
        engine.register_user(
            "sic:first",
            {"display": "first"},
            idempotency_key="\t",
            request_id="req-register-1",
        )
    assert exc.value.code == "IDEMPOTENCY_KEY_REQUIRED"

    assert _count(db_path, "core_users") == 0
    assert _count(db_path, "core_requests") == 0


def test_first_and_returning_user_remain_deterministic(tmp_path):
    db_path = tmp_path / "master.sqlite"
    engine = CaseEngine(db_path)

    first = engine.register_user(
        "sic:alice",
        {"display": "Alice"},
        idempotency_key="idem-register-first",
        request_id="req-register-first",
    )
    assert first["returning"] is False

    replay = engine.register_user(
        "sic:alice",
        {"display": "Alice"},
        idempotency_key="idem-register-first",
        request_id="req-register-retry",
    )
    assert replay == first

    returning = engine.register_user(
        "sic:alice",
        {"display": "Alice"},
        idempotency_key="idem-register-returning",
        request_id="req-register-returning",
    )
    assert returning["returning"] is True
    assert returning["user_id"] == first["user_id"]
    assert _count(db_path, "core_users") == 1


def test_create_session_rejects_blank_request_metadata_before_write(tmp_path):
    db_path = tmp_path / "master.sqlite"
    engine = CaseEngine(db_path)
    user = engine.register_user(
        "sic:session",
        {},
        idempotency_key="idem-register-session",
        request_id="req-register-session",
    )

    with pytest.raises(CoreError) as exc:
        engine.create_session(
            user["user_id"],
            "sic:session",
            request_id="",
            idempotency_key="idem-session-1",
        )
    assert exc.value.code == "REQUEST_ID_REQUIRED"

    with pytest.raises(CoreError) as exc:
        engine.create_session(
            user["user_id"],
            "sic:session",
            request_id="req-session-1",
            idempotency_key="   ",
        )
    assert exc.value.code == "IDEMPOTENCY_KEY_REQUIRED"

    assert _count(db_path, "core_sessions") == 0
    # Only the successful registration request exists.
    assert _count(db_path, "core_requests") == 1


def test_concurrent_same_key_session_retries_create_exactly_one_session(tmp_path):
    db_path = tmp_path / "master.sqlite"
    engine = CaseEngine(db_path)
    user = engine.register_user(
        "sic:race",
        {},
        idempotency_key="idem-register-race",
        request_id="req-register-race",
    )

    def create_session(worker: int) -> dict:
        return engine.create_session(
            user["user_id"],
            "sic:race",
            request_id=f"req-session-race-{worker}",
            idempotency_key="idem-session-race",
            ttl_seconds=3600,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(create_session, range(8)))

    assert len({row["session_id"] for row in results}) == 1
    assert _count(db_path, "core_sessions") == 1
    with sqlite3.connect(db_path) as conn:
        request_count = conn.execute(
            "SELECT COUNT(*) FROM core_requests WHERE operation='create_session'"
        ).fetchone()[0]
    assert request_count == 1

    with pytest.raises(CoreError) as exc:
        engine.create_session(
            user["user_id"],
            "sic:race",
            request_id="req-session-drift",
            idempotency_key="idem-session-race",
            ttl_seconds=7200,
        )
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"
