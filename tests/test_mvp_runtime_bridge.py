from pathlib import Path

import pytest

from runtime.mvp_bridge_server import BridgeConfig, BridgeRejected, MVPBridgeRuntime


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public_html"
HTML = (PUBLIC / "index.html").read_text()
BRIDGE = (PUBLIC / "assets" / "runtime-bridge.js").read_text()
SW = (PUBLIC / "sw.js").read_text()
SERVER = (ROOT / "runtime" / "mvp_bridge_server.py").read_text()


def config(tmp_path: Path, sic_id: str | None = "SIC-MVP-RUNTIME-1") -> BridgeConfig:
    static = tmp_path / "public_html"
    static.mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>test</title>")
    return BridgeConfig(master_db=tmp_path / "private" / "BLOCKCHAINPLUS-MASTER.sqlite", static_root=static, sandbox_sic_id=sic_id)


def test_normal_package_loads_bridge_before_app_and_pwa_caches_it():
    bridge_tag = '<script src="assets/runtime-bridge.js" defer></script>'
    app_tag = '<script src="assets/app.js" defer></script>'
    assert bridge_tag in HTML
    assert HTML.index(bridge_tag) < HTML.index(app_tag)
    assert "./assets/runtime-bridge.js" in SW
    assert "const SHELL_VERSION='2.1.6'" in SW


def test_browser_bridge_is_same_origin_fail_closed_and_does_not_author_identity_or_economics():
    assert "const API='/api/mvp'" in BRIDGE
    assert "credentials:'same-origin'" in BRIDGE
    assert "location.protocol==='file:'" in BRIDGE
    assert "caid:sicid-login-request" in BRIDGE and "event.preventDefault()" in BRIDGE
    assert "caid:case-request" in BRIDGE
    assert "window.CryptoAIDTwin" in BRIDGE
    for forbidden in ["first_activation_pol", "first_case_residual_pol", "subsequent_case_pol", "eth_sendTransaction", "personal_sign"]:
        assert forbidden not in BRIDGE
    login_payload = BRIDGE.split("request('/session',{method:'POST'", 1)[1].split("}).then", 1)[0]
    for forbidden_identity in ["sic_id", "sicId", "user_id", "userId", "session_id", "wallet"]:
        assert forbidden_identity not in login_payload


def test_server_requires_private_db_and_explicit_server_side_sandbox_identity(tmp_path: Path):
    runtime = MVPBridgeRuntime(config(tmp_path, None))
    with pytest.raises(BridgeRejected) as exc:
        runtime.login_sandbox({"action": "LOGIN_OR_RESUME"})
    assert exc.value.code == "sandbox_identity_not_configured"
    runtime = MVPBridgeRuntime(config(tmp_path / "configured"))
    with pytest.raises(BridgeRejected) as exc:
        runtime.login_sandbox({"action": "LOGIN_OR_RESUME", "sicId": "SIC-ATTACKER"})
    assert exc.value.code == "caller_identity_forbidden"


def test_sandbox_identity_search_and_case_reach_core_without_client_principal(tmp_path: Path):
    runtime = MVPBridgeRuntime(config(tmp_path))
    session = runtime.login_sandbox({"action": "LOGIN_OR_RESUME", "supportedCoreApiVersions": ["1.1.0"]})
    state = runtime.session_projection(session["session_id"])
    assert state["sicId"] == "SIC-MVP-RUNTIME-1"
    assert state["identityDataState"] == "LIVE"
    search = runtime.search(session["session_id"], "unknown project")
    assert search["state"] == "TO_VERIFY" and search["candidate"]["promoted"] is False
    opened = runtime.create_case(
        session["session_id"],
        {
            "caseType": "UNKNOWN",
            "projectQuery": "unknown project",
            "description": "runtime contract test",
            "requestId": "ui_req_test",
            "idempotencyKey": "ui_idem_test",
        },
    )
    assert opened["sicId"] == "SIC-MVP-RUNTIME-1"
    assert opened["identityDataState"] == "LIVE"
    assert opened["caseDataState"] == "LIVE"
    assert opened["caseId"].startswith("case_")
    with runtime.engine.conn() as connection:
        row = connection.execute("SELECT project_truth,state FROM core_cases WHERE case_id=?", (opened["caseId"],)).fetchone()
    assert tuple(row) == ("TO_VERIFY", "DRAFT")


def test_case_endpoint_rejects_client_identity_or_privileged_truth(tmp_path: Path):
    runtime = MVPBridgeRuntime(config(tmp_path))
    session = runtime.login_sandbox({"action": "LOGIN_OR_RESUME"})
    base = {"projectQuery": "x", "requestId": "r", "idempotencyKey": "i"}
    for key, value in [("sicId", "SIC-ATTACKER"), ("user_id", "usr_attacker"), ("authorization", "ENTITLEMENT_GRANTED"), ("payment", {"value": "1"}), ("entitlement", True)]:
        with pytest.raises(BridgeRejected) as exc:
            runtime.create_case(session["session_id"], {**base, key: value})
        assert exc.value.code == "caller_authority_forbidden"


def test_runtime_server_stays_loopback_by_default_and_has_no_transaction_path():
    assert 'CAID_MVP_HOST", "127.0.0.1"' in SERVER
    assert "CAID_MVP_ALLOW_NONLOOPBACK" in SERVER
    assert "productionDeployPerformed" in SERVER
    for forbidden in ["eth_sendTransaction", "personal_sign", "send_raw_transaction", "eth_sendRawTransaction"]:
        assert forbidden not in SERVER
