from __future__ import annotations

from decimal import Decimal
import http.client
import json
from pathlib import Path
import threading

import pytest

from runtime.mvp_bridge_server import BridgeConfig, Handler, MVPBridgeRuntime
from http.server import ThreadingHTTPServer
from functools import partial


PAYER = "0x1111111111111111111111111111111111111111"
TX_ACT = "0x" + "a" * 64
TX_CASE = "0x" + "b" * 64
TX_LATER = "0x" + "c" * 64


class FakeRPC:
    def __init__(self):
        self.rows: dict[tuple[str, str], dict] = {}

    def set_tx(self, tx_hash: str, *, sender: str, recipient: str, pol: str, block: int, finalized: int):
        wei = int(Decimal(pol) * Decimal(10**18))
        block_hash = "0x" + f"{block:064x}"
        for provider in ("rpc_a", "rpc_b"):
            self.rows[(provider, tx_hash.lower())] = {
                "chain_id": 137,
                "sender": sender.lower(),
                "recipient": recipient.lower(),
                "wei": wei,
                "block": block,
                "block_hash": block_hash,
                "finalized": finalized,
                "status": 1,
            }

    def __call__(self, provider_id: str, method: str, params: list):
        if method == "eth_chainId":
            return "0x89"
        if method == "eth_getBlockByNumber":
            rows = [value for (provider, _), value in self.rows.items() if provider == provider_id]
            return {"number": hex(max(row["finalized"] for row in rows))}
        tx_hash = params[0].lower()
        row = self.rows[(provider_id, tx_hash)]
        if method == "eth_getTransactionByHash":
            return {
                "hash": tx_hash,
                "from": row["sender"],
                "to": row["recipient"],
                "value": hex(row["wei"]),
                "blockNumber": hex(row["block"]),
                "blockHash": row["block_hash"],
            }
        if method == "eth_getTransactionReceipt":
            return {
                "transactionHash": tx_hash,
                "status": "0x1",
                "blockNumber": hex(row["block"]),
                "blockHash": row["block_hash"],
            }
        raise AssertionError(method)


@pytest.fixture()
def http_stack(tmp_path: Path):
    static = tmp_path / "frontend" / "public_html"
    static.mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>test</title>", encoding="utf-8")
    private = tmp_path / "private-evidence"
    runtime = MVPBridgeRuntime(
        BridgeConfig(
            master_db=tmp_path / "master.sqlite",
            static_root=static,
            sandbox_sic_id="SIC-HTTP-A",
            evidence_private_root=private,
            evidence_consent_id="sandbox-consent-20260903",
            rpc_provider_urls={
                "rpc_a": "https://rpc-a.invalid",
                "rpc_b": "https://rpc-b.invalid",
            },
        )
    )
    assert runtime.chat02 is not None
    fake_rpc = FakeRPC()
    runtime.chat02.rpc_adapter.rpc_call = fake_rpc
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, runtime=runtime))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield runtime, fake_rpc, server.server_address[1], static, private
    finally:
        server.shutdown()
        server.server_close()
        runtime.chat02.close()
        thread.join(timeout=2)


def request(port: int, method: str, path: str, *, body: bytes | None = None, headers: dict | None = None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        raw = response.read()
        payload = json.loads(raw.decode("utf-8")) if raw else None
        return response.status, dict(response.getheaders()), payload
    finally:
        connection.close()


def json_request(port: int, method: str, path: str, payload: dict, cookie: str | None = None):
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
    if cookie:
        headers["Cookie"] = cookie
    return request(port, method, path, body=body, headers=headers)


def session_cookie(port: int) -> str:
    status, headers, payload = json_request(port, "POST", "/api/mvp/session", {"action": "LOGIN_OR_RESUME"})
    assert status == 200
    assert payload["identityDataState"] == "LIVE"
    return headers["Set-Cookie"].split(";", 1)[0]


def create_case(port: int, cookie: str, suffix: str) -> str:
    status, _, payload = json_request(
        port,
        "POST",
        "/api/mvp/cases",
        {"projectQuery": f"project-{suffix}", "requestId": f"case-req-{suffix}", "idempotencyKey": f"case-idem-{suffix}"},
        cookie,
    )
    assert status == 201
    return payload["caseId"]


def test_protected_http_golden_50_450_500_and_private_evidence(http_stack):
    runtime, rpc, port, static, private = http_stack
    cookie = session_cookie(port)
    case_one = create_case(port, cookie, "one")

    evidence = b"%PDF-1.4\nprivate-http-evidence\n"
    status, _, stored = request(
        port,
        "POST",
        "/api/mvp/evidence",
        body=evidence,
        headers={
            "Cookie": cookie,
            "Content-Type": "application/pdf",
            "Content-Length": str(len(evidence)),
            "X-CAID-Case-Id": case_one,
            "X-CAID-Filename": "proof.pdf",
        },
    )
    assert status == 201
    assert stored["private_storage"] is True
    assert stored["status"] == "AVAILABLE"
    assert stored["sha256"]
    assert list(private.rglob("*.bin"))
    assert not list(static.rglob("*.bin"))
    assert not list(static.rglob("*.quarantine"))

    status, _, quote = request(port, "GET", "/api/mvp/payment/quote", headers={"Cookie": cookie})
    assert status == 200
    assert quote == {
        "contract_version": "1.0",
        "chain_id": 137,
        "asset": "POL",
        "stage": "ACTIVATION_REQUIRED",
        "activation_payable": "50",
    }

    status, _, forged = json_request(
        port,
        "POST",
        "/api/mvp/payment/activation-intents",
        {
            "payer": PAYER,
            "requestId": "activation-forged",
            "idempotencyKey": "activation-forged",
            "expectedValue": "1",
            "providerIds": ["evil-a", "evil-b"],
        },
        cookie,
    )
    assert status == 400
    assert forged["error"] == "CALLER_AUTHORITY_FORBIDDEN"

    status, _, activation = json_request(
        port,
        "POST",
        "/api/mvp/payment/activation-intents",
        {"payer": PAYER, "requestId": "activation-1", "idempotencyKey": "activation-1"},
        cookie,
    )
    assert status == 201
    assert activation["expected_value"] == "50"
    rpc.set_tx(TX_ACT, sender=PAYER, recipient=activation["treasury_address"], pol="50", block=100, finalized=101)
    status, _, act_settled = json_request(
        port,
        "POST",
        "/api/mvp/payment/settle",
        {"intentId": activation["intent_id"], "txHash": TX_ACT},
        cookie,
    )
    assert status == 200
    assert act_settled["payment_state"] == "SETTLED"
    assert act_settled["credit_effect"] == {"amount": "50", "state": "AVAILABLE"}
    assert act_settled["case_active"] is False

    status, _, first = json_request(
        port,
        "POST",
        "/api/mvp/payment/case-intents",
        {"caseId": case_one, "payer": PAYER, "requestId": "casepay-1", "idempotencyKey": "casepay-1"},
        cookie,
    )
    assert status == 201
    assert first["expected_value"] == "450"
    rpc.set_tx(TX_CASE, sender=PAYER, recipient=first["treasury_address"], pol="450", block=110, finalized=111)
    status, _, settled = json_request(
        port,
        "POST",
        "/api/mvp/payment/settle",
        {"intentId": first["intent_id"], "txHash": TX_CASE},
        cookie,
    )
    assert status == 200
    assert settled["payment_state"] == "SETTLED"
    assert settled["entitlement_granted"] is True
    assert settled["settlement_certificate_id"]
    assert settled["core_activation_ready"] is True
    assert settled["core_activation_claim"]["case_id"] == case_one
    assert settled["case_active"] is False

    case_two = create_case(port, cookie, "two")
    status, _, later = json_request(
        port,
        "POST",
        "/api/mvp/payment/case-intents",
        {"caseId": case_two, "payer": PAYER, "requestId": "casepay-2", "idempotencyKey": "casepay-2"},
        cookie,
    )
    assert status == 201
    assert later["expected_value"] == "500"


def test_evidence_mime_and_authority_are_server_controlled_before_bytes(http_stack):
    runtime, _, port, static, private = http_stack
    cookie = session_cookie(port)
    case_id = create_case(port, cookie, "mime")
    before = list(private.rglob("*.bin"))

    forged = b"not-a-pdf"
    status, _, payload = request(
        port,
        "POST",
        "/api/mvp/evidence",
        body=forged,
        headers={
            "Cookie": cookie,
            "Content-Type": "application/pdf",
            "Content-Length": str(len(forged)),
            "X-CAID-Case-Id": case_id,
            "X-CAID-Filename": "fake.pdf",
        },
    )
    assert status == 400
    assert payload["error"] == "MIME_REJECTED"
    assert list(private.rglob("*.bin")) == before

    real_pdf = b"%PDF-1.4\nforged-authority\n"
    status, _, payload = request(
        port,
        "POST",
        "/api/mvp/evidence",
        body=real_pdf,
        headers={
            "Cookie": cookie,
            "Content-Type": "application/pdf",
            "Content-Length": str(len(real_pdf)),
            "X-CAID-Case-Id": case_id,
            "X-CAID-Filename": "authority.pdf",
            "X-CAID-Authorization": "OWNER",
        },
    )
    assert status == 400
    assert payload["error"] == "CALLER_AUTHORITY_FORBIDDEN"
    assert list(private.rglob("*.bin")) == before
    assert not list(static.rglob("*.bin"))


def test_payment_routes_require_session_and_reject_cross_origin(http_stack):
    _, _, port, _, _ = http_stack
    status, _, payload = request(port, "GET", "/api/mvp/payment/quote")
    assert status == 401
    assert payload["error"] == "SESSION_REQUIRED"

    status, _, payload = json_request(
        port,
        "POST",
        "/api/mvp/payment/activation-intents",
        {"payer": PAYER, "requestId": "x", "idempotencyKey": "x"},
    )
    assert status == 401
    assert payload["error"] == "SESSION_REQUIRED"

    cookie = session_cookie(port)
    body = json.dumps({"payer": PAYER, "requestId": "cross", "idempotencyKey": "cross"}).encode()
    status, _, payload = request(
        port,
        "POST",
        "/api/mvp/payment/activation-intents",
        body=body,
        headers={
            "Cookie": cookie,
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "Origin": "https://attacker.example",
            "Host": f"127.0.0.1:{port}",
        },
    )
    assert status == 403
    assert payload["error"] == "cross_origin_forbidden"


def test_chat02_transport_is_fail_closed_when_not_configured(tmp_path: Path):
    static = tmp_path / "public_html"
    static.mkdir()
    (static / "index.html").write_text("ok", encoding="utf-8")
    runtime = MVPBridgeRuntime(
        BridgeConfig(master_db=tmp_path / "master.sqlite", static_root=static, sandbox_sic_id="SIC-A")
    )
    assert runtime.chat02 is None
    with pytest.raises(Exception) as rejected:
        runtime._chat02()
    assert getattr(rejected.value, "code", None) == "chat02_runtime_not_configured"
