#!/usr/bin/env python3
"""V1.5 fail-closed target-DB audit for direct bindings + interphase continuity.

The legacy v14 entrypoint is intentionally retained for operational continuity.
This wrapper preserves the V1.3 read-only audit, validates the semantic/economic
class of bindings represented directly by payment_intents.idempotency_key, and
proves durable DB+WAL continuity between the embedded V1.3 read transaction and
the later direct-binding read transaction. It never mutates the supplied SQLite
database and never emits raw idempotency keys.
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

from scripts import audit_payment_idempotency_aliases as v13

AUDIT_CONTRACT = "CHAT10_TARGETDB_IDEMPOTENCY_ALIAS_AUDIT_V1_5"
INTERPHASE_SOURCE_STABILITY_CONTRACT = (
    "V1_3_DATABASE_AFTER_EQUALS_V1_4_DATABASE_BEFORE_DB_WAL_V1"
)


def _direct_semantic_rows(conn: sqlite3.Connection) -> dict[str, list[str]]:
    operation_mismatches = [
        str(row[0])
        for row in conn.execute(
            """
            SELECT b.idempotency_key
            FROM payment_idempotency_bindings AS b
            JOIN payment_intents AS p ON p.idempotency_key=b.idempotency_key
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
            JOIN payment_intents AS p ON p.idempotency_key=b.idempotency_key
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
        "direct_operation_mismatches": operation_mismatches,
        "direct_economic_invariant_mismatches": economic_mismatches,
    }


def _interphase_comparison(
    v13_after: dict[str, Any], v14_before: dict[str, Any]
) -> tuple[bool, str]:
    """Compare only durable DB+WAL state and emit a deterministic evidence digest."""
    left = v13._source_data_fingerprint(v13_after)
    right = v13._source_data_fingerprint(v14_before)
    equal = left == right
    evidence = {
        "contract": INTERPHASE_SOURCE_STABILITY_CONTRACT,
        "equal": equal,
        "v13_database_after": left,
        "v14_database_before": right,
    }
    encoded = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return equal, hashlib.sha256(encoded).hexdigest()


def audit_db(db: str | os.PathLike[str]) -> tuple[dict[str, Any], int]:
    supplied = Path(db).expanduser()
    base_result, base_code = v13.audit_db(supplied)
    result = dict(base_result)
    result["contract"] = AUDIT_CONTRACT
    result["base_contract"] = v13.AUDIT_CONTRACT
    result["interphase_source_stability_contract"] = (
        INTERPHASE_SOURCE_STABILITY_CONTRACT
    )

    # Schema/open/integrity/source failures are already fail-closed in V1.3.
    if base_code in (21, 22, 23, 24):
        return result, base_code

    try:
        real = supplied.resolve(strict=True)
        before = v13.sqlite_file_fingerprint(real)
    except OSError as exc:
        result.update(status="OPEN_FAILED", error=type(exc).__name__)
        return result, 24

    base_after = result.get("database_after")
    if not isinstance(base_after, dict):
        result.update(
            status="SOURCE_CHANGED_BETWEEN_PHASES",
            interphase_source_stable=False,
            interphase_comparison_sha256=None,
            v14_database_before=before,
        )
        return result, 23

    interphase_stable, interphase_digest = _interphase_comparison(base_after, before)
    result["v14_database_before"] = before
    result["interphase_source_stable"] = interphase_stable
    result["interphase_comparison_sha256"] = interphase_digest
    if not interphase_stable:
        result["status"] = "SOURCE_CHANGED_BETWEEN_PHASES"
        return result, 23

    try:
        conn = v13._open_read_only(real)
        try:
            conn.execute("BEGIN")
            direct = _direct_semantic_rows(conn)
            conn.execute("ROLLBACK")
        finally:
            conn.close()
        after = v13.sqlite_file_fingerprint(real)
    except (OSError, sqlite3.Error) as exc:
        result.update(status="OPEN_FAILED", error=type(exc).__name__)
        return result, 24

    wrapper_stable = (
        v13._source_data_fingerprint(before) == v13._source_data_fingerprint(after)
    )
    result["v14_database_after"] = after
    result["v14_source_stable"] = wrapper_stable
    for label, keys in direct.items():
        result[label] = len(keys)
        result[f"{label}_sha256"] = v13._private_digest(keys)
    result["direct_semantic_failures"] = sum(len(keys) for keys in direct.values())

    if not wrapper_stable:
        result["status"] = "SOURCE_CHANGED_DURING_SCAN"
        return result, 23
    if result["direct_semantic_failures"]:
        result["status"] = "MIGRATION_REQUIRED"
        return result, 20

    # Preserve every stricter V1.3 verdict, including PROVENANCE_REQUIRED.
    return result, base_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "V1.5 read-only target DB audit for resolved/direct aliases and "
            "V1.3->direct-phase DB+WAL continuity."
        )
    )
    parser.add_argument("--db", required=True, help="Path to factual target SQLite DB")
    args = parser.parse_args(argv)
    result, code = audit_db(args.db)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
