"""MVP hardening layer for CHAT01 canonical Case mutations.

This module does not create a second Case authority. It subclasses the existing
``case_engine.CaseEngine`` and tightens product selection so the user-facing
Golden Path cannot silently switch the Case product after payment work has
started, cannot overwrite a concurrent Case update, and cannot create an
unaudited/non-idempotent product mutation.
"""
from __future__ import annotations

from .case_engine import CaseEngine as _BaseCaseEngine
from .case_engine import CoreError, ident, now

CORE_CASE_ENGINE_MVP_VERSION = "1.4"
_PRODUCT_SELECTION_MUTABLE_STATES = {"DRAFT", "TRIAGE", "PRODUCT_SELECTED"}


class CaseEngine(_BaseCaseEngine):
    """Canonical CaseEngine with release-blocking mutation guards applied."""

    def select_product(
        self,
        case_id: str,
        user_id: str,
        product_code: str,
        request_id: str,
        idempotency_key: str,
        expected_version: int,
    ) -> dict:
        if not isinstance(request_id, str) or not request_id.strip():
            raise CoreError("REQUEST_ID_REQUIRED", "request_id is required", 400)
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise CoreError("IDEMPOTENCY_KEY_REQUIRED", "idempotency_key is required", 400)
        if not isinstance(product_code, str) or not product_code.strip():
            raise CoreError("PRODUCT_REQUIRED", "product_code is required", 400)
        if isinstance(expected_version, bool) or not isinstance(expected_version, int):
            raise CoreError("INVALID_EXPECTED_VERSION", "expected_version must be an integer", 400)

        product_code = product_code.strip()
        request_id = request_id.strip()
        idempotency_key = idempotency_key.strip()
        request_fingerprint = self._request_fingerprint(
            "select_product",
            {
                "case_id": case_id,
                "user_id": user_id,
                "product_code": product_code,
                "expected_version": expected_version,
            },
        )

        with self.conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            replay = self._request_replay(
                conn,
                idempotency_key,
                "select_product",
                request_fingerprint,
            )
            if replay is not None:
                conn.execute("COMMIT")
                return replay

            case = conn.execute(
                "SELECT * FROM core_cases WHERE case_id=? AND user_id=?",
                (case_id, user_id),
            ).fetchone()
            if not case:
                raise CoreError("CASE_NOT_FOUND", "case not found", 404)
            if int(case["version"]) != expected_version:
                raise CoreError("STALE_STATE", "case version is stale", 409)
            if case["state"] not in _PRODUCT_SELECTION_MUTABLE_STATES:
                raise CoreError(
                    "PRODUCT_SELECTION_LOCKED",
                    "product selection is locked after payment/evidence processing begins",
                    409,
                )

            product = conn.execute(
                "SELECT * FROM core_products WHERE product_code=? AND status='ACTIVE'",
                (product_code,),
            ).fetchone()
            if not product:
                raise CoreError("PRODUCT_NOT_ELIGIBLE", "product unavailable", 403)

            version = expected_version + 1
            timestamp = now()
            updated = conn.execute(
                "UPDATE core_cases SET product_code=?,product_kind=?,version=?,updated_at=? "
                "WHERE case_id=? AND user_id=? AND version=?",
                (
                    product_code,
                    product["kind"],
                    version,
                    timestamp,
                    case_id,
                    user_id,
                    expected_version,
                ),
            )
            if updated.rowcount != 1:
                raise CoreError("STALE_STATE", "case version is stale", 409)

            conn.execute(
                "INSERT INTO core_case_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ident("ce"),
                    case_id,
                    "USER",
                    case["state"],
                    case["state"],
                    "product selected",
                    timestamp,
                    request_id,
                    idempotency_key,
                    "OWNER",
                    "CASE_PRODUCT_SELECTED",
                    version,
                ),
            )
            result = {
                "case_id": case_id,
                "product_code": product_code,
                "kind": product["kind"],
                "state": case["state"],
                "version": version,
            }
            self._record_request(
                conn,
                idempotency_key=idempotency_key,
                request_id=request_id,
                operation="select_product",
                request_fingerprint=request_fingerprint,
                result=result,
                created_at=timestamp,
            )
            conn.execute("COMMIT")
            return result


# ``core.case_engine.CaseEngine`` is imported directly by a few trusted legacy
# modules. Patch only this method on the existing class so those imports cannot
# bypass the same release-blocking guard. Database/schema/state authority remains
# the original CaseEngine; this layer changes no storage or economic truth.
_BaseCaseEngine.select_product = CaseEngine.select_product
