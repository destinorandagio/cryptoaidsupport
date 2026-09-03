#!/usr/bin/env python3
"""Fail-closed, read-only audit for PR87 historical idempotency aliases.

This is release-evidence tooling only. It never initializes application engines,
creates tables, runs migrations, or mutates the supplied SQLite database.

PASS invariants on the factual target DB:
  * every payment_idempotency_bindings.idempotency_key is represented either by
    payment_intents.idempotency_key directly or by payment_idempotency_resolutions;
  * a key may not directly identify one intent while resolving to another;
  * every durable resolution must be semantically compatible with the binding
    operation and with the frozen ACTIVATION/CASE economic contract.

Source-stability invariant:
  durable data-bearing SQLite files (database + WAL when present) must remain
  byte-identical for the full audit. The -shm file is reported for evidence but
  excluded from the stability verdict because SQLite readers may legitimately
  update shared-memory read marks even when the connection is mode=ro/query_only.

Exit codes:
  0  PASS (all alias/semantic/integrity/schema/source-stability checks pass)
  20 MIGRATION_REQUIRED (orphan or semantically inconsistent historical alias)
  21 SCHEMA_REQUIRED (required table/column absent)
  22 DB_INTEGRITY_FAILED (integrity_check or foreign_key_check failed)
  23 SOURCE_CHANGED_DURING_SCAN (database/WAL fingerprint changed during audit)
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
    "payment_idempotency_bindings": {"idempotency_key", "operation"},
    "payment_intents": {
        "intent_id",
        "idempotency_key",
        "case_id",
        "entitlement_ref",
        "asset",
        "expected_value",
    },
    "payment_idempotency_resolutions": {"idempotency_key", "intent_id"},
    "economic_intents": {
        "intent_id",
        "principal_id",
        "purpose",
        "case_id",
        "nominal_value",
        "credit_applied",
        "payable_value",
    },
}

AUDIT_CONTRACT = "CHAT10_TARGETDB_IDEMPOTENCY_ALIAS_AUDIT_V1_2"
SOURCE_STABILITY_CONTRACT = "SQLITE_DATABASE_PLUS_WAL_V1"


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
    """Hash the database and current WAL/SHM sidecars without creating them."""
    result: dict[str, Any] = {"database": _file_state(db_path)}
    for suffix, label in (("-wal", "wal"), ("-shm", "shm")):
        candidate = Path(str(db_path) + suffix)
        result[label] = _file_state(candidate) if candidate.exists() else None
    return result


def _source_data_fingerprint(fingerprint: dict[str, Any]) -> dict[str, Any]:
    """Return only durable data-bearing files used for stability acceptance."""
    return {
        "database": fingerprint.get("database"),
        "wal": fingerprint.get("wal"),
    }


def _record_after(
    result: dict[str, Any], before: dict[str, Any], db_path: Path
) -> tuple[dict[str, Any], bool]:
    after = sqlite_file_fingerprint(db_path)
    stable = _source_data_fingerprint(before) == _source_data_fingerprint(after)
    result["database_after"] = after
    result["source_stability_contract"] = SOURCE_STABILITY_CONTRACT
    result["source_stable"] = stable
    result["shm_changed_observational"] = before.get("shm") != after.get("shm")
    return after, stable


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    quoted = table.replace('"', '""')
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{quoted}")')}


def _open_read_only(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _private_digest(values: list[str]) -> str:
    """Return deterministic evidence without emitting the underlying secret keys."""
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def _semantic_alias_rows(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Return privacy-sensitive key sets for semantic alias validation.

    The caller emits only counts and SHA-256 digests. Queries intentionally stay
    inside the existing CHAT02 schema and do not infer authority from UI state.
    """
    direct_conflicts = [
        str(row[0])
        for row in conn.execute(
            """
            SELECT b.idempotency_key
            FROM payment_idempotency_bindings AS b
            JOIN payment_idempotency_resolutions AS r
              ON r.idempotency_key=b.idempotency_key
            JOIN payment_intents AS direct
              ON direct.idempotency_key=b.idempotency_key
            WHERE direct.intent_id<>r.intent_id
            ORDER BY b.idempotency_key
            """
        ).fetchall()
    ]

    operation_mismatches = [
        str(row[0])
        for row in conn.execute(
            """
            SELECT b.idempotency_key
            FROM payment_idempotency_bindings AS b
            JOIN payment_idempotency_resolutions AS r
              ON r.idempotency_key=b.idempotency_key
            JOIN payment_intents AS p ON p.intent_id=r.intent_id
            LEFT JOIN economic_intents AS e ON e.intent_id=p.intent_id
            WHERE b.operation NOT IN ('GENERIC','ACTIVATION','CASE')
               OR (b.operation='GENERIC' AND e.intent_id IS NOT NULL)
               OR (b.operation='ACTIVATION' AND (e.intent_id IS NULL OR e.purpose<>'ACTIVATION'))
               OR (b.operation='CASE' AND (e.intent_id IS NULL OR e.purpose<>'CASE'))
            ORDER BY b.idempotency_key
            """
        ).fetchall()
    ]

    economic_mismatches = [
        str(row[0])
        for row in conn.execute(
            """
            SELECT b.idempotency_key
            FROM payment_idempotency_bindings AS b
            JOIN payment_idempotency_resolutions AS r
              ON r.idempotency_key=b.idempotency_key
            JOIN payment_intents AS p ON p.intent_id=r.intent_id
            LEFT JOIN economic_intents AS e ON e.intent_id=p.intent_id
            WHERE (
                b.operation='ACTIVATION'
                AND NOT (
                    e.intent_id IS NOT NULL
                    AND e.purpose='ACTIVATION'
                    AND e.case_id='activation:' || e.principal_id
                    AND p.case_id=e.case_id
                    AND p.entitlement_ref='activation_credit50:' || e.principal_id
                    AND p.asset='POL'
                    AND p.expected_value='50'
                    AND e.nominal_value='50'
                    AND e.credit_applied='0'
                    AND e.payable_value='50'
                )
            ) OR (
                b.operation='CASE'
                AND NOT (
                    e.intent_id IS NOT NULL
                    AND e.purpose='CASE'
                    AND p.case_id=e.case_id
                    AND p.entitlement_ref='case_active:' || e.case_id
                    AND p.asset='POL'
                    AND p.expected_value=e.payable_value
                    AND e.nominal_value='500'
                    AND (
                        (e.credit_applied='50' AND e.payable_value='450')
                        OR (e.credit_applied='0' AND e.payable_value='500')
                    )
                )
            )
            ORDER BY b.idempotency_key
            """
        ).fetchall()
    ]

    return {
        "direct_resolution_conflicts": direct_conflicts,
        "resolution_operation_mismatches": operation_mismatches,
        "resolved_economic_invariant_mismatches": economic_mismatches,
    }


def audit_db(db: str | os.PathLike[str]) -> tuple[dict[str, Any], int]:
    supplied = Path(db).expanduser()
    if not supplied.exists() or not supplied.is_file():
        return {"status": "INPUT_ERROR", "error": "database path is not a regular file"}, 24

    real = supplied.resolve(strict=True)
    before = sqlite_file_fingerprint(real)
    result: dict[str, Any] = {
        "contract": AUDIT_CONTRACT,
        "database_realpath": str(real),
        "database_before": before,
        "source_stability_contract": SOURCE_STABILITY_CONTRACT,
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
            _, stable = _record_after(result, before, real)
            return result, 21 if stable else 23

        integrity_rows = [str(row[0]) for row in conn.execute("PRAGMA integrity_check")]
        foreign_key_rows = [list(row) for row in conn.execute("PRAGMA foreign_key_check")]
        result["integrity_check"] = integrity_rows
        result["foreign_key_violation_count"] = len(foreign_key_rows)
        if integrity_rows != ["ok"] or foreign_key_rows:
            conn.execute("ROLLBACK")
            result["status"] = "DB_INTEGRITY_FAILED"
            _, stable = _record_after(result, before, real)
            return result, 22 if stable else 23

        binding_count = int(
            conn.execute("SELECT COUNT(*) FROM payment_idempotency_bindings").fetchone()[0]
        )
        intent_count = int(conn.execute("SELECT COUNT(*) FROM payment_intents").fetchone()[0])
        resolution_count = int(
            conn.execute("SELECT COUNT(*) FROM payment_idempotency_resolutions").fetchone()[0]
        )

        orphan_keys = [
            str(row[0])
            for row in conn.execute(
                """
                SELECT b.idempotency_key
                FROM payment_idempotency_bindings AS b
                WHERE NOT EXISTS (
                    SELECT 1 FROM payment_intents AS p
                    WHERE p.idempotency_key=b.idempotency_key
                )
                AND NOT EXISTS (
                    SELECT 1 FROM payment_idempotency_resolutions AS r
                    WHERE r.idempotency_key=b.idempotency_key
                )
                ORDER BY b.idempotency_key
                """
            ).fetchall()
        ]

        semantic = _semantic_alias_rows(conn)
        result.update(
            binding_count=binding_count,
            payment_intent_count=intent_count,
            resolution_count=resolution_count,
            orphan_aliases=len(orphan_keys),
            orphan_aliases_sha256=_private_digest(orphan_keys),
        )
        for label, keys in semantic.items():
            result[label] = len(keys)
            result[f"{label}_sha256"] = _private_digest(keys)
        result["semantic_resolution_failures"] = sum(len(keys) for keys in semantic.values())
        conn.execute("ROLLBACK")
    except sqlite3.Error as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        result.update(status="OPEN_FAILED", error=type(exc).__name__)
        _, stable = _record_after(result, before, real)
        return result, 24 if stable else 23
    finally:
        conn.close()

    _, stable = _record_after(result, before, real)
    if not stable:
        result["status"] = "SOURCE_CHANGED_DURING_SCAN"
        return result, 23
    if result["orphan_aliases"] or result["semantic_resolution_failures"]:
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
