from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from core import CaseEngine, CoreAPI, CoreError


def _fixture(tmp_path: Path):
    db = tmp_path / "BLOCKCHAINPLUS-MASTER.sqlite"
    core = CaseEngine(db)
    user = core.register_user("SIC-NEXT-ACTION-1", {}, "reg-i", "reg-r")
    session = core.create_session(user["user_id"], user["sic_id"], "ses-r", "ses-i", 3600)
    case = core.open_case(
        user["user_id"],
        user["sic_id"],
        None,
        "project:next-action",
        False,
        "USER",
        "case-r",
        "case-i",
    )
    return db, core, user, session, case


def test_next_action_task_exact_replay_is_single_side_effect(tmp_path: Path):
    db, core, user, session, case = _fixture(tmp_path)

    first = core.add_task(
        case["case_id"],
        user["user_id"],
        "Submit recovery details",
        "OPEN_RECOVERY_CHECKLIST",
        request_id="task-r-1",
        idempotency_key="task-i-1",
        expected_version=case["version"],
    )
    replay = core.add_task(
        case["case_id"],
        user["user_id"],
        "Submit recovery details",
        "OPEN_RECOVERY_CHECKLIST",
        request_id="task-r-2",
        idempotency_key="task-i-1",
        expected_version=case["version"],
    )
    assert replay == first

    with core.conn() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM core_case_tasks WHERE case_id=?",
            (case["case_id"],),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM core_case_events WHERE case_id=? AND audit_event='CASE_TASK_CREATED'",
            (case["case_id"],),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM core_requests WHERE idempotency_key='task-i-1' AND operation='add_task'"
        ).fetchone()[0] == 1
        version = conn.execute(
            "SELECT version FROM core_cases WHERE case_id=?",
            (case["case_id"],),
        ).fetchone()[0]
    assert version == case["version"] + 1

    projection = CoreAPI(db).next_action(
        session_id=session["session_id"],
        sic_id=user["sic_id"],
        case_id=case["case_id"],
    )
    assert projection["task_id"] == first["task_id"]
    assert projection["next_action"] == "OPEN_RECOVERY_CHECKLIST"


def test_next_action_projection_ignores_open_non_action_tasks(tmp_path: Path):
    db, core, user, session, case = _fixture(tmp_path)
    generic = core.add_task(
        case["case_id"],
        user["user_id"],
        "Internal review placeholder",
        None,
        request_id="task-r-generic",
        idempotency_key="task-i-generic",
        expected_version=case["version"],
    )
    actionable = core.add_task(
        case["case_id"],
        user["user_id"],
        "Upload requested evidence",
        "UPLOAD_REQUESTED_EVIDENCE",
        request_id="task-r-action",
        idempotency_key="task-i-action",
        expected_version=generic["version"],
    )

    projection = CoreAPI(db).next_action(
        session_id=session["session_id"],
        sic_id=user["sic_id"],
        case_id=case["case_id"],
    )
    assert projection["task_id"] == actionable["task_id"]
    assert projection["next_action"] == "UPLOAD_REQUESTED_EVIDENCE"


def test_next_action_projection_is_none_when_only_generic_open_tasks(tmp_path: Path):
    db, core, user, session, case = _fixture(tmp_path)
    core.add_task(
        case["case_id"],
        user["user_id"],
        "Internal review placeholder",
        None,
        request_id="task-r-generic-only",
        idempotency_key="task-i-generic-only",
        expected_version=case["version"],
    )

    projection = CoreAPI(db).next_action(
        session_id=session["session_id"],
        sic_id=user["sic_id"],
        case_id=case["case_id"],
    )
    assert projection is None


def test_next_action_task_rejects_whitespace_only_action_before_write(tmp_path: Path):
    _, core, user, _, case = _fixture(tmp_path)
    with pytest.raises(CoreError) as exc:
        core.add_task(
            case["case_id"],
            user["user_id"],
            "Whitespace placeholder",
            " \t\n\r ",
            request_id="task-r-whitespace",
            idempotency_key="task-i-whitespace",
            expected_version=case["version"],
        )
    assert exc.value.code == "NEXT_ACTION_INVALID"

    with core.conn() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM core_case_tasks WHERE case_id=?",
            (case["case_id"],),
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM core_requests WHERE idempotency_key='task-i-whitespace'"
        ).fetchone()[0] == 0
        version = conn.execute(
            "SELECT version FROM core_cases WHERE case_id=?",
            (case["case_id"],),
        ).fetchone()[0]
    assert version == case["version"]


def test_next_action_same_key_payload_drift_and_stale_version_fail_closed(tmp_path: Path):
    _, core, user, _, case = _fixture(tmp_path)
    core.add_task(
        case["case_id"],
        user["user_id"],
        "Submit recovery details",
        "OPEN_RECOVERY_CHECKLIST",
        request_id="task-r-1",
        idempotency_key="task-i-1",
        expected_version=case["version"],
    )

    with pytest.raises(CoreError) as exc:
        core.add_task(
            case["case_id"],
            user["user_id"],
            "Different task",
            "OPEN_DIFFERENT",
            request_id="task-r-2",
            idempotency_key="task-i-1",
            expected_version=case["version"],
        )
    assert exc.value.code == "IDEMPOTENCY_CONFLICT"

    with pytest.raises(CoreError) as exc:
        core.add_task(
            case["case_id"],
            user["user_id"],
            "Second task",
            "OPEN_SECOND",
            request_id="task-r-3",
            idempotency_key="task-i-2",
            expected_version=case["version"],
        )
    assert exc.value.code == "STALE_STATE"


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"request_id": "", "idempotency_key": "task-i", "expected_version": 1}, "REQUEST_ID_REQUIRED"),
        ({"request_id": "task-r", "idempotency_key": "", "expected_version": 1}, "IDEMPOTENCY_KEY_REQUIRED"),
        ({"request_id": "task-r", "idempotency_key": "task-i", "expected_version": None}, "INVALID_EXPECTED_VERSION"),
    ],
)
def test_next_action_task_requires_mutation_metadata(tmp_path: Path, kwargs: dict, code: str):
    _, core, user, _, case = _fixture(tmp_path)
    with pytest.raises(CoreError) as exc:
        core.add_task(
            case["case_id"],
            user["user_id"],
            "Submit recovery details",
            "OPEN_RECOVERY_CHECKLIST",
            **kwargs,
        )
    assert exc.value.code == code


def test_eight_concurrent_same_key_next_action_retries_converge_once(tmp_path: Path):
    _, core, user, _, case = _fixture(tmp_path)

    def create_once(index: int):
        worker = CaseEngine(core.db_path)
        return worker.add_task(
            case["case_id"],
            user["user_id"],
            "Submit recovery details",
            "OPEN_RECOVERY_CHECKLIST",
            request_id=f"task-r-{index}",
            idempotency_key="task-i-race",
            expected_version=case["version"],
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(create_once, range(8)))

    assert len({item["task_id"] for item in results}) == 1
    assert len({item["version"] for item in results}) == 1
    with core.conn() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM core_case_tasks WHERE case_id=?",
            (case["case_id"],),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM core_case_events WHERE case_id=? AND audit_event='CASE_TASK_CREATED'",
            (case["case_id"],),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM core_requests WHERE idempotency_key='task-i-race' AND operation='add_task'"
        ).fetchone()[0] == 1
