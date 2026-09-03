#!/usr/bin/env python3
"""V1.4 fail-closed target-DB audit supplement for direct idempotency bindings.

This wrapper preserves the V1.3 read-only audit and additionally validates the
semantic/economic class of bindings represented directly by
payment_intents.idempotency_key. It never mutates the supplied SQLite database
and never emits raw idempotency keys.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

from scripts import audit_payment_idempotency_aliases as v13

AUDIT_CONTRACT = "CHAT10_TARGETDB_IDEMPOTENCY_ALIAS_AUDIT_V1_4"


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


def audit_db(db: str | os.PathLike[str]) -> tuple[dict[str, Any], int]:
    supplied = Path(db).expanduser()
    base_result, base_code = v13.audit_db(supplied)
    result = dict(base_result)
    result["contract"] = AUDIT_CONTRACT
    result["base_contract"] = v13.AUDIT_CONTRACT

    # Schema/open/integrity/source failures are already fail-closed in V1.3.
    if base_code in (21, 22, 23, 24):
        return result, base_code

    try:
        real = supplied.resolve(strict=True)
        before = v13.sqlite_file_fingerprint(real)
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
    result["v14_database_before"] = before
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
        description="V1.4 read-only target DB audit for direct and resolved aliases."
    )
    parser.add_argument("--db", required=True, help="Path to factual target SQLite DB")
    args = parser.parse_args(argv)
    result, code = audit_db(args.db)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
