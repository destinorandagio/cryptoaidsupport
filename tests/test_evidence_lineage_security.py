import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from evidence_payment import EvidencePaymentEngine, EvidencePaymentError


def _engine():
    root = Path(tempfile.mkdtemp())
    return root, EvidencePaymentEngine(
        root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence"
    )


def _store(e, *, content: bytes, parent_evidence_id: str | None = None):
    return e.store_evidence(
        case_id="CASE-LINEAGE-1",
        content=content,
        original_name="proof.pdf",
        mime_declared="application/pdf",
        mime_detected="application/pdf",
        uploader="sic_test",
        consent_id="cons_test",
        authorization="ALLOW",
        parent_evidence_id=parent_evidence_id,
        reason="REPLACE" if parent_evidence_id else "UPLOAD",
    )


def _lineage_rows(e, parent_id: str):
    with e._connect() as c:
        parent = c.execute(
            "SELECT * FROM evidence_records WHERE evidence_id=?", (parent_id,)
        ).fetchone()
        children = c.execute(
            "SELECT * FROM evidence_records WHERE parent_evidence_id=? ORDER BY created_at,evidence_id",
            (parent_id,),
        ).fetchall()
        integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
        fk = c.execute("PRAGMA foreign_key_check").fetchall()
    return parent, children, integrity, fk


def test_superseded_parent_cannot_spawn_second_successor():
    _, e = _engine()
    parent = _store(e, content=b"v1")
    first_child = _store(
        e, content=b"v2-first", parent_evidence_id=parent["evidence_id"]
    )

    with pytest.raises(EvidencePaymentError) as exc:
        _store(e, content=b"v2-second", parent_evidence_id=parent["evidence_id"])
    assert exc.value.code == "EVIDENCE_PARENT_NOT_AVAILABLE"

    row, children, integrity, fk = _lineage_rows(e, parent["evidence_id"])
    assert row["status"] == "SUPERSEDED"
    assert len(children) == 1
    assert children[0]["evidence_id"] == first_child["evidence_id"]
    assert children[0]["version"] == 2
    assert children[0]["status"] == "AVAILABLE"
    assert integrity == "ok"
    assert fk == []

    third = _store(
        e, content=b"v3", parent_evidence_id=first_child["evidence_id"]
    )
    assert third["version"] == 3


def test_concurrent_same_parent_has_exactly_one_successor():
    _, e = _engine()
    parent = _store(e, content=b"v1-race")
    barrier = threading.Barrier(2)

    def worker(content: bytes):
        barrier.wait(timeout=5)
        try:
            result = _store(
                e, content=content, parent_evidence_id=parent["evidence_id"]
            )
            return ("ok", result)
        except EvidencePaymentError as exc:
            return ("error", exc.code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(worker, (b"v2-A", b"v2-B")))

    winners = [value for kind, value in outcomes if kind == "ok"]
    conflicts = [value for kind, value in outcomes if kind == "error"]
    assert len(winners) == 1
    assert conflicts == ["EVIDENCE_PARENT_NOT_AVAILABLE"]

    row, children, integrity, fk = _lineage_rows(e, parent["evidence_id"])
    assert row["status"] == "SUPERSEDED"
    assert len(children) == 1
    assert children[0]["evidence_id"] == winners[0]["evidence_id"]
    assert children[0]["version"] == 2
    assert children[0]["status"] == "AVAILABLE"
    assert integrity == "ok"
    assert fk == []
