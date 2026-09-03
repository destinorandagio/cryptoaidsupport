from pathlib import Path

import pytest

from evidence_payment import EvidencePaymentError
from runtime.chat02_transport import Chat02TransportConfig


def _build(tmp_path: Path, providers: dict[str, str]):
    static = tmp_path / "public_html"
    static.mkdir(exist_ok=True)
    private = tmp_path / "private-evidence"
    return Chat02TransportConfig.build(
        private_root=private,
        static_root=static,
        evidence_consent_id="consent-test",
        rpc_provider_urls=providers,
    )


def test_same_rpc_hostname_cannot_satisfy_provider_quorum(tmp_path: Path):
    with pytest.raises(EvidencePaymentError) as rejected:
        _build(
            tmp_path,
            {
                "provider_a": "https://rpc.operator.example/v1/key-a",
                "provider_b": "https://rpc.operator.example/v2/key-b",
            },
        )
    assert rejected.value.code == "RPC_PROVIDER_ALIAS"


def test_rpc_hostname_normalization_blocks_case_and_trailing_dot_alias(tmp_path: Path):
    with pytest.raises(EvidencePaymentError) as rejected:
        _build(
            tmp_path,
            {
                "provider_a": "https://RPC.OPERATOR.EXAMPLE/rpc-a",
                "provider_b": "https://rpc.operator.example./rpc-b",
            },
        )
    assert rejected.value.code == "RPC_PROVIDER_ALIAS"


def test_distinct_rpc_hosts_remain_valid_server_configuration(tmp_path: Path):
    config = _build(
        tmp_path,
        {
            "provider_a": "https://rpc-a.operator-one.example/key-a",
            "provider_b": "https://rpc-b.operator-two.example/key-b",
        },
    )
    assert tuple(config.rpc_provider_urls) == ("provider_a", "provider_b")
