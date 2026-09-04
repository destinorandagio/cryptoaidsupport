from types import SimpleNamespace

import pytest

from evidence_payment import EvidencePaymentError
from runtime.chat02_transport import Chat02HTTPTransport


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, *, json, headers):
        self.calls.append((url, json, headers))
        payload = self.payload(json) if callable(self.payload) else self.payload
        return FakeResponse(payload)


def transport_with_response(payload):
    transport = object.__new__(Chat02HTTPTransport)
    transport.config = SimpleNamespace(rpc_provider_urls={"rpc_a": "https://rpc-a.invalid"})
    transport._http_client = FakeClient(payload)
    return transport


def test_rpc_response_rejects_mismatched_request_id():
    transport = transport_with_response({"jsonrpc": "2.0", "id": "wrong-request", "result": "0x89"})
    with pytest.raises(EvidencePaymentError) as rejected:
        transport._rpc_call("rpc_a", "eth_chainId", [])
    assert rejected.value.code == "RPC_RESPONSE_MISMATCH"


def test_rpc_response_requires_jsonrpc_2_0_and_id():
    payloads = (
        lambda request: {"id": request["id"], "result": "0x89"},
        lambda request: {"jsonrpc": "1.0", "id": request["id"], "result": "0x89"},
        lambda request: {"jsonrpc": "2.0", "result": "0x89"},
    )
    for payload in payloads:
        transport = transport_with_response(payload)
        with pytest.raises(EvidencePaymentError) as rejected:
            transport._rpc_call("rpc_a", "eth_chainId", [])
        assert rejected.value.code == "RPC_RESPONSE_MISMATCH"


def test_rpc_response_requires_exactly_one_result_or_error():
    payloads = (
        lambda request: {"jsonrpc": "2.0", "id": request["id"]},
        lambda request: {
            "jsonrpc": "2.0",
            "id": request["id"],
            "result": "0x89",
            "error": {"code": -32000, "message": "ambiguous"},
        },
    )
    for payload in payloads:
        transport = transport_with_response(payload)
        with pytest.raises(EvidencePaymentError) as rejected:
            transport._rpc_call("rpc_a", "eth_chainId", [])
        assert rejected.value.code == "RPC_MALFORMED"


def test_rpc_response_accepts_exact_jsonrpc_correlation():
    transport = transport_with_response(
        lambda request: {"jsonrpc": "2.0", "id": request["id"], "result": "0x89"}
    )
    response = transport._rpc_call("rpc_a", "eth_chainId", [])
    assert response["jsonrpc"] == "2.0"
    assert response["result"] == "0x89"
    assert response["id"].startswith("caid-")
