from pathlib import Path

import pytest

from evidence_payment import EvidencePaymentError
from runtime.chat02_transport import Chat02TransportConfig


PROVIDERS = {
    "rpc-a": "https://rpc-a.example",
    "rpc-b": "https://rpc-b.example",
}


def _build(private_root: Path, static_root: Path):
    return Chat02TransportConfig.build(
        private_root=private_root,
        static_root=static_root,
        evidence_consent_id="consent-test",
        rpc_provider_urls=PROVIDERS,
    )


def test_rejects_private_root_inside_static_root(tmp_path):
    static = tmp_path / "public_html"
    private = static / "private-evidence"
    private.mkdir(parents=True)

    with pytest.raises(EvidencePaymentError) as exc:
        _build(private, static)

    assert exc.value.code == "PUBLIC_STORAGE_FORBIDDEN"


def test_rejects_static_root_inside_private_root(tmp_path):
    private = tmp_path / "runtime-data"
    static = private / "public_html"
    static.mkdir(parents=True)

    # A Case storage key named "public_html" is valid, so allowing this root
    # layout could place Evidence bytes directly beneath the served tree.
    with pytest.raises(EvidencePaymentError) as exc:
        _build(private, static)

    assert exc.value.code == "PUBLIC_STORAGE_FORBIDDEN"


def test_allows_disjoint_private_and_static_roots(tmp_path):
    private = tmp_path / "private-evidence"
    static = tmp_path / "public_html"
    private.mkdir()
    static.mkdir()

    config = _build(private, static)

    assert config.private_root == private.resolve()
