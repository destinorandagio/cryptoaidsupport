"""CHAT02 Evidence storage path-containment guard for the 48H MVP.

This module is the canonical exported EvidencePaymentEngine.  Case identifiers
are logical identifiers, never filesystem paths; unsafe values fail closed
before any quarantine/private-storage write occurs.
"""
from __future__ import annotations

import re
from typing import Any

from .engine import EvidencePaymentError
from .mvp_engine import EvidencePaymentEngine as _MvpEvidencePaymentEngine

EVIDENCE_STORAGE_GUARD_VERSION = "1.1"
_CASE_STORAGE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def validate_case_storage_key(case_id: Any) -> str:
    if not isinstance(case_id, str) or not _CASE_STORAGE_KEY.fullmatch(case_id):
        raise EvidencePaymentError(
            "INVALID_CASE_STORAGE_KEY",
            "Case identifier is not a valid private Evidence storage key",
        )
    if case_id in {".", ".."}:
        raise EvidencePaymentError(
            "INVALID_CASE_STORAGE_KEY",
            "Case identifier cannot be a filesystem traversal segment",
        )
    return case_id


class EvidencePaymentEngine(_MvpEvidencePaymentEngine):
    """Canonical CHAT02 engine with fail-closed Evidence path containment."""

    def store_evidence(self, *, case_id: str, **kwargs):
        safe_case_id = validate_case_storage_key(case_id)
        return super().store_evidence(case_id=safe_case_id, **kwargs)
