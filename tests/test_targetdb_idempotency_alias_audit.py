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
          idempotency_key TEXT NOT NULL UNIQUE
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


def _binding(conn: sqlite3.Connection, key: str) -> None:
    conn.execute(
        "INSERT INTO payment_idempotency_bindings VALUES(?,?,?,datetime('now'))",
        (key, "CASE", "f" * 64),
    )


def test_direct_intent_key_is_not_orphan_and_source_is_unchanged(tmp_path: Path) -> None:
    db = tmp_path / "master.sqlite"
    conn = _make_db(db)
    _binding(conn, "direct-secret-key")
    conn.execute("INSERT INTO payment_intents VALUES(?,?)", ("pi_direct", "direct-secret-key"))
    conn.commit()
    conn.close()
    before = db.read_bytes()

    result, code = audit_db(db)

    assert code == 0
    assert result["status"] == "PASS"
    assert result["orphan_aliases"] == 0
    assert result["source_stable"] is True
    assert result["foreign_key_violation_count"] == 0
    assert result["integrity_check"] == ["ok"]
    assert db.read_bytes() == before


def test_durable_resolution_covers_historical_alias(tmp_path: Path) -> None:
    db = tmp_path / "master.sqlite"
    conn = _make_db(db)
    _binding(conn, "origin-key")
    _binding(conn, "alias-key")
    conn.execute("INSERT INTO payment_intents VALUES(?,?)", ("pi_1", "origin-key"))
    conn.execute(
        "INSERT INTO payment_idempotency_resolutions VALUES(?,?,datetime('now'))",
        ("alias-key", "pi_1"),
    )
    conn.commit()
    conn.close()

    result, code = audit_db(db)

    assert code == 0
    assert result["status"] == "PASS"
    assert result["binding_count"] == 2
    assert result["resolution_count"] == 1
    assert result["orphan_aliases"] == 0


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


def test_missing_resolution_schema_requires_migration_without_writes(tmp_path: Path) -> None:
    db = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE payment_idempotency_bindings(idempotency_key TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE payment_intents(intent_id TEXT PRIMARY KEY,idempotency_key TEXT UNIQUE)")
    conn.commit()
    conn.close()
    before = db.read_bytes()

    result, code = audit_db(db)

    assert code == 21
    assert result["status"] == "SCHEMA_REQUIRED"
    assert "payment_idempotency_resolutions" in result["missing_schema"]
    assert db.read_bytes() == before


def test_foreign_key_violation_fails_integrity_gate(tmp_path: Path) -> None:
    db = tmp_path / "broken.sqlite"
    conn = _make_db(db)
    _binding(conn, "alias-key")
    # Leave the valid binding transaction before deliberately inserting a corrupt
    # legacy row with FK enforcement disabled. This models target data created by
    # an older writer that did not enable PRAGMA foreign_keys.
    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        "INSERT INTO payment_idempotency_resolutions VALUES(?,?,datetime('now'))",
        ("alias-key", "missing_intent"),
    )
    conn.commit()
    conn.close()

    result, code = audit_db(db)

    assert code == 22
    assert result["status"] == "DB_INTEGRITY_FAILED"
    assert result["foreign_key_violation_count"] == 1


def test_shm_only_coordination_drift_does_not_fail_source_stability(
    tmp_path: Path, monkeypatch
) -> None:
    """SQLite readers may legitimately change WAL shared-memory read marks.

    The -shm file is coordination metadata, not durable database content. A
    read-only audit must still fail on DB/WAL drift, but it must not reject an
    otherwise stable source merely because its own reader changed -shm bytes.
    """
    db = tmp_path / "wal.sqlite"
    conn = _make_db(db)
    _binding(conn, "direct-key")
    conn.execute("INSERT INTO payment_intents VALUES(?,?)", ("pi_1", "direct-key"))
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
            fingerprint["shm"] = {
                "size": 32768,
                "mtime_ns": 1,
                "sha256": "f" * 64,
            }
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


def test_cli_returns_20_and_json_contains_no_raw_orphan_key(tmp_path: Path) -> None:
    db = tmp_path / "master.sqlite"
    conn = _make_db(db)
    _binding(conn, "never-print-this-key")
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
    assert payload["orphan_aliases"] == 1
    assert payload["status"] == "MIGRATION_REQUIRED"
    assert "never-print-this-key" not in completed.stdout
    assert completed.stderr == ""
