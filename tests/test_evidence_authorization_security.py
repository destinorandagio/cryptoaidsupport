import tempfile
from pathlib import Path

import pytest

from evidence_payment import EvidencePaymentEngine, EvidencePaymentError


def _engine():
    root = Path(tempfile.mkdtemp())
    return root, EvidencePaymentEngine(
        root / "BLOCKCHAINPLUS-MASTER.sqlite", root / "private-evidence"
    )


def _store(engine, *, authorization="ALLOW", consent_id="cons_123"):
    return engine.store_evidence(
        case_id="CASE-AUTH-1",
        content=b"private-evidence",
        original_name="proof.pdf",
        mime_declared="application/pdf",
        mime_detected="application/pdf",
        uploader="sic_test",
        consent_id=consent_id,
        authorization=authorization,
    )


def _assert_no_evidence_side_effect(root, engine):
    assert not list(root.rglob("*.bin"))
    assert not list(root.rglob("*.quarantine"))
    with engine._connect() as c:
        assert c.execute("SELECT COUNT(*) FROM evidence_records").fetchone()[0] == 0
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
    "authorization",
    (
        "REVOKED",
        "PENDING",
        "DENY",
        "FALSE",
        "0",
        "AUTHORIZED_PENDING",
        " DENIED",
        "DENIED ",
        "allow",
        "owner",
        "",
        "   ",
    ),
)
def test_non_authorizing_states_fail_before_evidence_bytes_or_rows(authorization):
    root, engine = _engine()
    with pytest.raises(EvidencePaymentError) as exc:
        _store(engine, authorization=authorization)
    assert exc.value.code == "UNAUTHORIZED"
    _assert_no_evidence_side_effect(root, engine)


@pytest.mark.parametrize("consent_id", ("", " ", "\t", "\n", None))
def test_missing_or_blank_consent_binding_fails_before_evidence_bytes_or_rows(consent_id):
    root, engine = _engine()
    with pytest.raises(EvidencePaymentError) as exc:
        _store(engine, consent_id=consent_id)
    assert exc.value.code == "CONSENT_REQUIRED"
    _assert_no_evidence_side_effect(root, engine)


@pytest.mark.parametrize("authorization", ("ALLOW", "OWNER"))
def test_explicit_allowed_states_write_private_evidence(authorization):
    root, engine = _engine()
    stored = _store(engine, authorization=authorization, consent_id="cons_123")
    assert stored["status"] == "AVAILABLE"
    assert len(list(root.rglob("*.bin"))) == 1
    assert not list(root.rglob("*.quarantine"))
