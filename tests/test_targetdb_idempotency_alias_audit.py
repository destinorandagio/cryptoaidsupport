from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import scripts.audit_payment_idempotency_aliases as audit_module
from scripts.audit_payment_idempotency_aliases import audit_db


def _make_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE payment_idempotency_bindings(
          idempotency_key TEXT PRIMARY KEY,
          operation TEXT NOT NULL,
          request_fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE payment_intents(
          intent_id TEXT PRIMARY KEY,
          idempotency_key TEXT NOT NULL UNIQUE,
          case_id TEXT NOT NULL,
          entitlement_ref TEXT NOT NULL,
          asset TEXT NOT NULL,
          expected_value TEXT NOT NULL
        );
        CREATE TABLE economic_intents(
          intent_id TEXT PRIMARY KEY,
          principal_id TEXT NOT NULL,
          purpose TEXT NOT NULL,
          case_id TEXT NOT NULL,
          nominal_value TEXT NOT NULL,
          credit_applied TEXT NOT NULL,
          payable_value TEXT NOT NULL,
          FOREIGN KEY(intent_id) REFERENCES payment_intents(intent_id)
        );
        CREATE TABLE payment_idempotency_resolutions(
          idempotency_key TEXT PRIMARY KEY,
          intent_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(idempotency_key) REFERENCES payment_idempotency_bindings(idempotency_key),
          FOREIGN KEY(intent_id) REFERENCES payment_intents(intent_id)
        );
        """
    )
    return conn


def _binding(conn: sqlite3.Connection, key: str, operation: str = "CASE") -> None:
    conn.execute(
        "INSERT INTO payment_idempotency_bindings VALUES(?,?,?,datetime('now'))",
        (key, operation, "f" * 64),
    )


def _generic_intent(conn: sqlite3.Connection, intent_id: str, key: str) -> None:
    conn.execute(
        "INSERT INTO payment_intents VALUES(?,?,?,?,?,?)",
        (intent_id, key, "generic-case", "generic-entitlement", "POL", "1"),
    )


def _activation_intent(
    conn: sqlite3.Connection, intent_id: str, key: str, principal: str = "sic-a"
) -> None:
    case_id = f"activation:{principal}"
    conn.execute(
        "INSERT INTO payment_intents VALUES(?,?,?,?,?,?)",
        (intent_id, key, case_id, f"activation_credit50:{principal}", "POL", "50"),
    )
    conn.execute(
        "INSERT INTO economic_intents VALUES(?,?,?,?,?,?,?)",
        (intent_id, principal, "ACTIVATION", case_id, "50", "0", "50"),
    )


def _case_intent(
    conn: sqlite3.Connection,
    intent_id: str,
    key: str,
    *,
    principal: str = "sic-a",
    case_id: str = "case-1",
    credit: str = "50",
    payable: str = "450",
) -> None:
    conn.execute(
        "INSERT INTO payment_intents VALUES(?,?,?,?,?,?)",
        (intent_id, key, case_id, f"case_active:{case_id}", "POL", payable),
    )
    conn.execute(
        "INSERT INTO economic_intents VALUES(?,?,?,?,?,?,?)",
        (intent_id, principal, "CASE", case_id, "500", credit, payable),
    )


def _resolve(conn: sqlite3.Connection, key: str, intent_id: str) -> None:
    conn.execute(
        "INSERT INTO payment_idempotency_resolutions VALUES(?,?,datetime('now'))",
        (key, intent_id),
    )


def test_direct_intent_key_is_not_orphan_and_source_is_unchanged(tmp_path: Path) -> None:
    db = tmp_path / "master.sqlite"
    conn = _make_db(db)
    _binding(conn, "direct-secret-key", "GENERIC")
    _generic_intent(conn, "pi_direct", "direct-secret-key")
    conn.commit()
    conn.close()
    before = db.read_bytes()

    result, code = audit_db(db)

    assert code == 0
    assert result["status"] == "PASS"
    assert result["orphan_aliases"] == 0
    assert result["direct_resolution_conflicts"] == 0
    assert result["resolution_operation_mismatches"] == 0
    assert result["resolved_economic_invariant_mismatches"] == 0
    assert result["source_stable"] is True
    assert result["foreign_key_violation_count"] == 0
    assert result["integrity_check"] == ["ok"]
    assert db.read_bytes() == before


def test_durable_resolution_covers_semantically_matching_case_alias(tmp_path: Path) -> None:
    db = tmp_path / "master.sqlite"
    conn = _make_db(db)
    _binding(conn, "origin-key", "CASE")
    _binding(conn, "alias-key", "CASE")
    _case_intent(conn, "pi_1", "origin-key")
    _resolve(conn, "alias-key", "pi_1")
    conn.commit()
    conn.close()

    result, code = audit_db(db)

    assert code == 0
    assert result["status"] == "PASS"
    assert result["binding_count"] == 2
    assert result["resolution_count"] == 1
    assert result["orphan_aliases"] == 0
    assert result["semantic_resolution_failures"] == 0


def test_orphan_alias_fails_closed_without_leaking_raw_key(tmp_path: Path) -> None:
    db = tmp_path / "master.sqlite"
    conn = _make_db(db)
    _binding(conn, "raw-sensitive-orphan-key")
    conn.commit()
    conn.close()
    before_digest = hashlib.sha256(db.read_bytes()).hexdigest()

    result, code = audit_db(db)

    assert code == 20
    assert result["status"] == "MIGRATION_REQUIRED"
    assert result["orphan_aliases"] == 1
    assert "raw-sensitive-orphan-key" not in json.dumps(result)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before_digest


def test_fk_valid_case_binding_resolved_to_activation_intent_fails_semantic_gate(
    tmp_path: Path,
) -> None:
    """Reproduce QA40: orphan=0/FK=0 must not hide a semantic alias mismatch."""
    db = tmp_path / "semantic-gap.sqlite"
    conn = _make_db(db)
    _binding(conn, "origin-activation", "ACTIVATION")
    _binding(conn, "case-alias-secret", "CASE")
    _activation_intent(conn, "pi_activation", "origin-activation")
    _resolve(conn, "case-alias-secret", "pi_activation")
    conn.commit()
    conn.close()

    result, code = audit_db(db)

    assert code == 20
    assert result["status"] == "MIGRATION_REQUIRED"
    assert result["orphan_aliases"] == 0
    assert result["foreign_key_violation_count"] == 0
    assert result["resolution_operation_mismatches"] == 1
    assert result["resolved_economic_invariant_mismatches"] == 1
    assert "case-alias-secret" not in json.dumps(result)


def test_direct_key_and_resolution_to_different_intents_fails_closed(tmp_path: Path) -> None:
    db = tmp_path / "direct-conflict.sqlite"
    conn = _make_db(db)
    _binding(conn, "same-secret-key", "GENERIC")
    _binding(conn, "other-origin", "GENERIC")
    _generic_intent(conn, "pi_direct", "same-secret-key")
    _generic_intent(conn, "pi_other", "other-origin")
    _resolve(conn, "same-secret-key", "pi_other")
    conn.commit()
    conn.close()

    result, code = audit_db(db)

    assert code == 20
    assert result["status"] == "MIGRATION_REQUIRED"
    assert result["orphan_aliases"] == 0
    assert result["direct_resolution_conflicts"] == 1
    assert "same-secret-key" not in json.dumps(result)


def test_case_resolution_with_wrong_frozen_economics_fails_closed(tmp_path: Path) -> None:
    db = tmp_path / "economic-conflict.sqlite"
    conn = _make_db(db)
    _binding(conn, "origin-key", "CASE")
    _binding(conn, "alias-key", "CASE")
    _case_intent(conn, "pi_bad", "origin-key", credit="0", payable="500")
    conn.execute(
        "UPDATE payment_intents SET expected_value='499' WHERE intent_id='pi_bad'"
    )
    _resolve(conn, "alias-key", "pi_bad")
    conn.commit()
    conn.close()

    result, code = audit_db(db)

    assert code == 20
    assert result["resolution_operation_mismatches"] == 0
    assert result["resolved_economic_invariant_mismatches"] == 1


def test_missing_resolution_schema_requires_migration_without_writes(tmp_path: Path) -> None:
    db = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE payment_idempotency_bindings(idempotency_key TEXT PRIMARY KEY,operation TEXT)"
    )
    conn.execute(
        "CREATE TABLE payment_intents(intent_id TEXT PRIMARY KEY,idempotency_key TEXT UNIQUE)"
    )
    conn.commit()
    conn.close()
    before = db.read_bytes()

    result, code = audit_db(db)

    assert code == 21
    assert result["status"] == "SCHEMA_REQUIRED"
    assert "payment_idempotency_resolutions" in result["missing_schema"]
    assert "economic_intents" in result["missing_schema"]
    assert db.read_bytes() == before


def test_foreign_key_violation_fails_integrity_gate(tmp_path: Path) -> None:
    db = tmp_path / "broken.sqlite"
    conn = _make_db(db)
    _binding(conn, "alias-key")
    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    _resolve(conn, "alias-key", "missing_intent")
    conn.commit()
    conn.close()

    result, code = audit_db(db)

    assert code == 22
    assert result["status"] == "DB_INTEGRITY_FAILED"
    assert result["foreign_key_violation_count"] == 1


def test_shm_only_coordination_drift_does_not_fail_source_stability(
    tmp_path: Path, monkeypatch
) -> None:
    db = tmp_path / "wal.sqlite"
    conn = _make_db(db)
    _binding(conn, "direct-key", "GENERIC")
    _generic_intent(conn, "pi_1", "direct-key")
    conn.commit()
    conn.close()

    original = audit_module.sqlite_file_fingerprint
    calls = 0

    def fingerprint_with_shm_coordination_change(path: Path):
        nonlocal calls
        calls += 1
        fingerprint = original(path)
        if calls >= 2:
            fingerprint = dict(fingerprint)
            fingerprint["shm"] = {"size": 32768, "mtime_ns": 1, "sha256": "f" * 64}
        return fingerprint

    monkeypatch.setattr(
        audit_module, "sqlite_file_fingerprint", fingerprint_with_shm_coordination_change
    )

    result, code = audit_module.audit_db(db)

    assert code == 0
    assert result["status"] == "PASS"
    assert result["source_stable"] is True
    assert result["orphan_aliases"] == 0
    assert result["database_before"]["database"] == result["database_after"]["database"]
    assert result["database_before"].get("wal") == result["database_after"].get("wal")
    assert result["database_before"].get("shm") != result["database_after"].get("shm")
    assert result["shm_changed_observational"] is True


def test_real_wal_reader_does_not_self_fail_when_only_shm_read_marks_change(
    tmp_path: Path,
) -> None:
    db = tmp_path / "live-wal.sqlite"
    conn = _make_db(db)
    assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
    _binding(conn, "direct-key", "GENERIC")
    _generic_intent(conn, "pi_1", "direct-key")
    conn.commit()

    wal = Path(str(db) + "-wal")
    shm = Path(str(db) + "-shm")
    assert wal.exists()
    assert shm.exists()
    db_before = hashlib.sha256(db.read_bytes()).hexdigest()
    wal_before = hashlib.sha256(wal.read_bytes()).hexdigest()

    result, code = audit_module.audit_db(db)

    assert code == 0
    assert result["status"] == "PASS"
    assert result["source_stable"] is True
    assert result["orphan_aliases"] == 0
    assert hashlib.sha256(db.read_bytes()).hexdigest() == db_before
    assert hashlib.sha256(wal.read_bytes()).hexdigest() == wal_before
    conn.close()


def test_database_or_wal_drift_still_fails_closed(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "drift.sqlite"
    conn = _make_db(db)
    _binding(conn, "direct-key", "GENERIC")
    _generic_intent(conn, "pi_1", "direct-key")
    conn.commit()
    conn.close()

    original = audit_module.sqlite_file_fingerprint
    calls = 0

    def fingerprint_with_database_drift(path: Path):
        nonlocal calls
        calls += 1
        fingerprint = original(path)
        if calls >= 2:
            fingerprint = dict(fingerprint)
            database = dict(fingerprint["database"])
            database["sha256"] = "0" * 64
            fingerprint["database"] = database
        return fingerprint

    monkeypatch.setattr(
        audit_module, "sqlite_file_fingerprint", fingerprint_with_database_drift
    )

    result, code = audit_module.audit_db(db)

    assert code == 23
    assert result["status"] == "SOURCE_CHANGED_DURING_SCAN"
    assert result["source_stable"] is False


def test_cli_returns_20_and_json_contains_no_raw_semantic_key(tmp_path: Path) -> None:
    db = tmp_path / "master.sqlite"
    conn = _make_db(db)
    _binding(conn, "origin-activation", "ACTIVATION")
    _binding(conn, "never-print-this-key", "CASE")
    _activation_intent(conn, "pi_activation", "origin-activation")
    _resolve(conn, "never-print-this-key", "pi_activation")
    conn.commit()
    conn.close()

    completed = subprocess.run(
        [sys.executable, "scripts/audit_payment_idempotency_aliases.py", "--db", str(db)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 20
    payload = json.loads(completed.stdout)
    assert payload["orphan_aliases"] == 0
    assert payload["resolution_operation_mismatches"] == 1
    assert payload["status"] == "MIGRATION_REQUIRED"
    assert "never-print-this-key" not in completed.stdout
    assert completed.stderr == ""
