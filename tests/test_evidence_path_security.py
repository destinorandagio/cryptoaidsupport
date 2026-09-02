import tempfile
from pathlib import Path

import pytest

from evidence_payment import EvidencePaymentEngine, EvidencePaymentError
from evidence_payment.engine import EvidencePaymentEngine as DirectEngine


MALICIOUS_CASE_IDS = (
    "../public_html/case",
    "../../outside",
    "/tmp/absolute-case",
    r"..\public_html\case",
    "case/../../outside",
    ".",
    "..",
    "",
)


def _engine():
    root = Path(tempfile.mkdtemp())
    return root, EvidencePaymentEngine(root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence")


def _store(e, case_id):
    return e.store_evidence(
        case_id=case_id,
        content=b"private-evidence",
        original_name="proof.pdf",
        mime_declared="application/pdf",
        mime_detected="application/pdf",
        uploader="sic_test",
        consent_id="cons_test",
        authorization="ALLOW",
    )


@pytest.mark.parametrize("case_id", MALICIOUS_CASE_IDS)
def test_case_id_path_traversal_fails_before_any_evidence_write(case_id):
    root, e = _engine()
    with pytest.raises(EvidencePaymentError) as exc:
        _store(e, case_id)
    assert exc.value.code == "INVALID_CASE_STORAGE_KEY"
    assert not list(root.rglob("*.bin"))
    assert not list(root.rglob("*.quarantine"))
    with e._connect() as c:
        assert c.execute("SELECT COUNT(*) FROM evidence_records").fetchone()[0] == 0


def test_valid_case_key_stays_beneath_private_root_and_hashes_bytes():
    root, e = _engine()
    stored = _store(e, "CASE-123_abc.1")
    assert stored["status"] == "AVAILABLE"
    with e._connect() as c:
        row = c.execute(
            "SELECT storage_relpath,sha256 FROM evidence_records WHERE evidence_id=?",
            (stored["evidence_id"],),
        ).fetchone()
    physical = (e.private_root / row["storage_relpath"]).resolve()
    assert physical.is_relative_to(e.private_root)
    assert physical.read_bytes() == b"private-evidence"
    assert row["sha256"] == stored["sha256"]
    assert "public_html" not in str(physical).lower()
    assert not list(root.rglob("*.quarantine"))


def test_direct_engine_import_cannot_bypass_canonical_storage_guard():
    assert DirectEngine is EvidencePaymentEngine
    root = Path(tempfile.mkdtemp())
    e = DirectEngine(root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence")
    with pytest.raises(EvidencePaymentError) as exc:
        _store(e, "../public_html/direct-bypass")
    assert exc.value.code == "INVALID_CASE_STORAGE_KEY"


def test_database_integrity_after_rejected_traversal_and_valid_write():
    _, e = _engine()
    with pytest.raises(EvidencePaymentError):
        _store(e, "../../escape")
    _store(e, "CASE-integrity-1")
    with e._connect() as c:
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
