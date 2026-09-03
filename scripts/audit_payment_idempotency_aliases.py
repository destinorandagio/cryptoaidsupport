#!/usr/bin/env python3
"""Fail-closed, read-only audit for PR87 historical idempotency aliases.

This is release-evidence tooling only. It never initializes application engines,
creates tables, runs migrations, or mutates the supplied SQLite database.

PASS invariant on the factual target DB:
  every payment_idempotency_bindings.idempotency_key is represented either by
  payment_intents.idempotency_key directly or by payment_idempotency_resolutions.

Exit codes:
  0  PASS (orphan_aliases == 0, integrity/FK/schema/source-stability checks pass)
  20 MIGRATION_REQUIRED (one or more orphan historical aliases)
  21 SCHEMA_REQUIRED (required table/column absent)
  22 DB_INTEGRITY_FAILED (integrity_check or foreign_key_check failed)
  23 SOURCE_CHANGED_DURING_SCAN (DB/WAL/SHM fingerprint changed during the audit)
  24 INPUT_ERROR / OPEN_FAILED
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS: dict[str, set[str]] = {
    "payment_idempotency_bindings": {"idempotency_key"},
    "payment_intents": {"intent_id", "idempotency_key"},
    "payment_idempotency_resolutions": {"idempotency_key", "intent_id"},
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_state(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": _sha256(path),
    }


def sqlite_file_fingerprint(db_path: Path) -> dict[str, Any]:
    """Hash the database and any current WAL/SHM sidecars without creating them."""
    result: dict[str, Any] = {"database": _file_state(db_path)}
    for suffix, label in (("-wal", "wal"), ("-shm", "shm")):
        candidate = Path(str(db_path) + suffix)
        result[label] = _file_state(candidate) if candidate.exists() else None
    return result


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    quoted = table.replace('"', '""')
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{quoted}")')}


def _open_read_only(db_path: Path) -> sqlite3.Connection:
    # Path.as_uri() safely percent-encodes spaces and works on POSIX/Windows.
    conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def audit_db(db: str | os.PathLike[str]) -> tuple[dict[str, Any], int]:
    supplied = Path(db).expanduser()
    if not supplied.exists() or not supplied.is_file():
        return {"status": "INPUT_ERROR", "error": "database path is not a regular file"}, 24

    real = supplied.resolve(strict=True)
    before = sqlite_file_fingerprint(real)
    result: dict[str, Any] = {
        "contract": "CHAT10_TARGETDB_IDEMPOTENCY_ALIAS_AUDIT_V1",
        "database_realpath": str(real),
        "database_before": before,
    }

    try:
        conn = _open_read_only(real)
    except (OSError, sqlite3.Error) as exc:
        result.update(status="OPEN_FAILED", error=type(exc).__name__)
        return result, 24

    try:
        conn.execute("BEGIN")
        schema_version = int(conn.execute("PRAGMA schema_version").fetchone()[0])
        journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0])
        result.update(schema_version=schema_version, journal_mode=journal_mode)

        schema_missing: dict[str, list[str]] = {}
        existing_tables = {
            str(row[0])
            for row in conn.execute("SELECT name FROM sqlite_schema WHERE type='table'")
        }
        for table, required in REQUIRED_COLUMNS.items():
            if table not in existing_tables:
                schema_missing[table] = sorted(required)
                continue
            missing = required - _table_columns(conn, table)
            if missing:
                schema_missing[table] = sorted(missing)
        if schema_missing:
            conn.execute("ROLLBACK")
            result.update(status="SCHEMA_REQUIRED", missing_schema=schema_missing)
            after = sqlite_file_fingerprint(real)
            result["database_after"] = after
            result["source_stable"] = before == after
            return result, 21 if before == after else 23

        integrity_rows = [str(row[0]) for row in conn.execute("PRAGMA integrity_check")]
        foreign_key_rows = [list(row) for row in conn.execute("PRAGMA foreign_key_check")]
        integrity_ok = integrity_rows == ["ok"]
        result["integrity_check"] = integrity_rows
        result["foreign_key_violation_count"] = len(foreign_key_rows)
        if not integrity_ok or foreign_key_rows:
            conn.execute("ROLLBACK")
            result["status"] = "DB_INTEGRITY_FAILED"
            after = sqlite_file_fingerprint(real)
            result["database_after"] = after
            result["source_stable"] = before == after
            return result, 22 if before == after else 23

        binding_count = int(conn.execute(
            "SELECT COUNT(*) FROM payment_idempotency_bindings"
        ).fetchone()[0])
        intent_count = int(conn.execute(
            "SELECT COUNT(*) FROM payment_intents"
        ).fetchone()[0])
        resolution_count = int(conn.execute(
            "SELECT COUNT(*) FROM payment_idempotency_resolutions"
        ).fetchone()[0])

        orphan_rows = conn.execute(
            """
            SELECT b.idempotency_key
            FROM payment_idempotency_bindings AS b
            WHERE NOT EXISTS (
                SELECT 1 FROM payment_intents AS p
                WHERE p.idempotency_key = b.idempotency_key
            )
            AND NOT EXISTS (
                SELECT 1 FROM payment_idempotency_resolutions AS r
                WHERE r.idempotency_key = b.idempotency_key
            )
            ORDER BY b.idempotency_key
            """
        ).fetchall()
        orphan_keys = [str(row[0]) for row in orphan_rows]
        orphan_digest = hashlib.sha256(
            "\n".join(orphan_keys).encode("utf-8")
        ).hexdigest()

        # Do not leak raw idempotency keys; only count + digest are evidence output.
        result.update(
            binding_count=binding_count,
            payment_intent_count=intent_count,
            resolution_count=resolution_count,
            orphan_aliases=len(orphan_keys),
            orphan_aliases_sha256=orphan_digest,
        )
        conn.execute("ROLLBACK")
    except sqlite3.Error as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        result.update(status="OPEN_FAILED", error=type(exc).__name__)
        after = sqlite_file_fingerprint(real)
        result["database_after"] = after
        result["source_stable"] = before == after
        return result, 24 if before == after else 23
    finally:
        conn.close()

    after = sqlite_file_fingerprint(real)
    result["database_after"] = after
    result["source_stable"] = before == after
    if before != after:
        result["status"] = "SOURCE_CHANGED_DURING_SCAN"
        return result, 23
    if result["orphan_aliases"]:
        result["status"] = "MIGRATION_REQUIRED"
        return result, 20
    result["status"] = "PASS"
    return result, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only factual target DB audit for PR87 historical aliases."
    )
    parser.add_argument("--db", required=True, help="Path to factual target SQLite DB")
    args = parser.parse_args(argv)
    result, code = audit_db(args.db)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
