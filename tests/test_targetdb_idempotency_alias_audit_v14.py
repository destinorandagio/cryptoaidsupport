from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from scripts.audit_payment_idempotency_aliases_v14 import audit_db


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


def _binding(conn: sqlite3.Connection, key: str, operation: str) -> None:
    conn.execute(
        "INSERT INTO payment_idempotency_bindings VALUES(?,?,?,datetime('now'))",
        (key, operation, "f" * 64),
    )


def _activation(conn: sqlite3.Connection, intent_id: str, key: str, principal: str = "sic-a") -> None:
    case_id = f"activation:{principal}"
    conn.execute(
        "INSERT INTO payment_intents VALUES(?,?,?,?,?,?)",
        (intent_id, key, case_id, f"activation_credit50:{principal}", "POL", "50"),
    )
    conn.execute(
        "INSERT INTO economic_intents VALUES(?,?,?,?,?,?,?)",
        (intent_id, principal, "ACTIVATION", case_id, "50", "0", "50"),
    )


def _case(
    conn: sqlite3.Connection,
    intent_id: str,
    key: str,
    *,
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
        (intent_id, "sic-a", "CASE", case_id, "500", credit, payable),
    )


def test_qa42_direct_case_binding_to_activation_fails_closed(tmp_path: Path) -> None:
    db = tmp_path / "direct-operation-gap.sqlite"
    conn = _make_db(db)
    _binding(conn, "never-print-direct-key", "CASE")
    _activation(conn, "pi_activation", "never-print-direct-key")
    conn.commit()
    conn.close()
    before = hashlib.sha256(db.read_bytes()).hexdigest()

    result, code = audit_db(db)

    assert code == 20
    assert result["status"] == "MIGRATION_REQUIRED"
    assert result["resolution_count"] == 0
    assert result["direct_operation_mismatches"] == 1
    assert result["direct_economic_invariant_mismatches"] == 1
    assert result["direct_semantic_failures"] == 2
    assert "never-print-direct-key" not in json.dumps(result)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


def test_qa42_direct_case_wrong_economics_fails_closed(tmp_path: Path) -> None:
    db = tmp_path / "direct-economic-gap.sqlite"
    conn = _make_db(db)
    _binding(conn, "direct-case-key", "CASE")
    _case(conn, "pi_case", "direct-case-key", credit="0", payable="500")
    conn.execute("UPDATE payment_intents SET expected_value='499' WHERE intent_id='pi_case'")
    conn.commit()
    conn.close()

    result, code = audit_db(db)

    assert code == 20
    assert result["direct_operation_mismatches"] == 0
    assert result["direct_economic_invariant_mismatches"] == 1
    assert "direct-case-key" not in json.dumps(result)


def test_valid_direct_case_binding_passes_v14(tmp_path: Path) -> None:
    db = tmp_path / "direct-valid.sqlite"
    conn = _make_db(db)
    _binding(conn, "valid-direct-key", "CASE")
    _case(conn, "pi_case", "valid-direct-key")
    conn.commit()
    conn.close()

    result, code = audit_db(db)

    assert code == 0
    assert result["status"] == "PASS"
    assert result["contract"] == "CHAT10_TARGETDB_IDEMPOTENCY_ALIAS_AUDIT_V1_4"
    assert result["resolution_count"] == 0
    assert result["direct_operation_mismatches"] == 0
    assert result["direct_economic_invariant_mismatches"] == 0
    assert result["direct_semantic_failures"] == 0
    assert result["source_stable"] is True
    assert result["v14_source_stable"] is True


def test_v14_preserves_v13_provenance_required(tmp_path: Path) -> None:
    db = tmp_path / "resolution.sqlite"
    conn = _make_db(db)
    _binding(conn, "origin", "CASE")
    _binding(conn, "alias", "CASE")
    _case(conn, "pi_case", "origin")
    conn.execute(
        "INSERT INTO payment_idempotency_resolutions VALUES(?,?,datetime('now'))",
        ("alias", "pi_case"),
    )
    conn.commit()
    conn.close()

    result, code = audit_db(db)

    assert code == 25
    assert result["status"] == "PROVENANCE_REQUIRED"
    assert result["direct_semantic_failures"] == 0
    assert "alias" not in json.dumps(result)


def test_cli_v14_never_emits_raw_direct_key(tmp_path: Path) -> None:
    db = tmp_path / "cli.sqlite"
    conn = _make_db(db)
    _binding(conn, "cli-secret-direct-key", "CASE")
    _activation(conn, "pi_activation", "cli-secret-direct-key")
    conn.commit()
    conn.close()

    completed = subprocess.run(
        [sys.executable, "scripts/audit_payment_idempotency_aliases_v14.py", "--db", str(db)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 20
    payload = json.loads(completed.stdout)
    assert payload["direct_operation_mismatches"] == 1
    assert payload["status"] == "MIGRATION_REQUIRED"
    assert "cli-secret-direct-key" not in completed.stdout
    assert completed.stderr == ""
