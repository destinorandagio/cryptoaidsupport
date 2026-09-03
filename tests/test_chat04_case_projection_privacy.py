import json
import shutil
import subprocess
from pathlib import Path

from runtime.mvp_bridge_server import BridgeConfig, MVPBridgeRuntime


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public_html"
BRIDGE = (PUBLIC / "assets" / "runtime-bridge.js").read_text()
SW = (PUBLIC / "sw.js").read_text()

PRIVATE_CASE_KEYS = [
    "caseId",
    "caseState",
    "caseDataState",
    "nextAction",
    "timeline",
    "paymentIntent",
]


def _config(tmp_path: Path, sic_id: str = "SIC-CHAT04-A") -> BridgeConfig:
    static = tmp_path / "public_html"
    private = tmp_path / "private"
    static.mkdir(parents=True)
    private.mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>chat04</title>")
    return BridgeConfig(
        master_db=private / "BLOCKCHAINPLUS-MASTER.sqlite",
        static_root=static,
        sandbox_sic_id=sic_id,
    )


def _function_block(name: str, next_name: str) -> str:
    start = BRIDGE.index(f"function {name}(")
    end = BRIDGE.index(f"function {next_name}(", start)
    return BRIDGE[start:end]


def _execute_projection_switch() -> dict:
    node = shutil.which("node")
    assert node, "Node.js is required for the CHAT04 executable projection regression"
    render = _function_block("renderCanonicalCaseState", "publishCanonicalState")
    publish = _function_block("publishCanonicalState", "clearCanonicalState")
    clear = _function_block("clearCanonicalState", "paymentProjection")
    script = f"""
const calls=[];
global.CustomEvent=function(name,init){{this.name=name;this.detail=init&&init.detail}};
global.document={{getElementById:()=>null}};
global.window={{
  __CRYPTOAID_STATE__:Object.freeze({{
    sicId:'SIC-A',identityDataState:'LIVE',dataState:'LIVE',
    caseId:'CASE-A',caseState:'ACTIVE',caseDataState:'LIVE',
    nextAction:{{title:'PRIVATE-A'}},timeline:[{{label:'PRIVATE-A'}}],
    paymentIntent:{{intentId:'PRIVATE-A'}}
  }}),
  dispatchEvent:(event)=>calls.push(event.name)
}};
{render}
{publish}
{clear}
publishCanonicalState({{sicId:'SIC-B',identityDataState:'LIVE',dataState:'LIVE'}});
process.stdout.write(JSON.stringify({{state:window.__CRYPTOAID_STATE__,calls}}));
"""
    completed = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def test_protected_session_projects_read_only_canonical_case_state(tmp_path: Path):
    runtime = MVPBridgeRuntime(_config(tmp_path))
    session = runtime.login_sandbox({"action": "LOGIN_OR_RESUME"})
    opened = runtime.create_case(
        session["session_id"],
        {
            "caseType": "UNKNOWN",
            "projectQuery": "unknown project",
            "description": "chat04 projection contract",
            "requestId": "chat04_req",
            "idempotencyKey": "chat04_idem",
        },
    )
    projection = runtime.session_projection(session["session_id"], opened["caseId"])
    with runtime.engine.conn() as connection:
        row = connection.execute(
            "SELECT state FROM core_cases WHERE case_id=?", (opened["caseId"],)
        ).fetchone()
    assert row is not None
    assert projection["caseState"] == row["state"] == "DRAFT"
    assert projection["caseDataState"] == "LIVE"


def test_principal_switch_replaces_private_case_projection_instead_of_merging():
    output = _execute_projection_switch()
    assert output["state"]["sicId"] == "SIC-B"
    assert output["state"]["identityDataState"] == "LIVE"
    for key in PRIVATE_CASE_KEYS:
        assert key not in output["state"]
    assert "caid:state-updated" in output["calls"]
    assert "{...current,...allowed}" not in BRIDGE


def test_session_failure_has_explicit_fail_closed_scrub_and_recovery_refresh():
    assert "function clearCanonicalState(" in BRIDGE
    assert "caid:recovery-refresh-request" in BRIDGE
    assert "scrubPrivateBefore:true" in BRIDGE
    assert "clearCanonicalState('session_unavailable')" in BRIDGE
    for key in PRIVATE_CASE_KEYS:
        assert key in BRIDGE


def test_case_active_presentation_is_bound_only_to_canonical_case_state():
    assert "payload.caseState" in BRIDGE
    assert "caseState==='ACTIVE'" in BRIDGE
    assert "CASE ACTIVE" in BRIDGE
    assert "paymentVerified" in BRIDGE
    assert "paymentVerified===true" not in BRIDGE.split("CASE ACTIVE", 1)[0][-400:]


def test_projection_security_change_rolls_the_precached_pwa_shell():
    assert "const SHELL_VERSION='2.1.10'" in SW
    assert "./assets/runtime-bridge.js" in SW
    assert "url.pathname.includes('/api/')" in SW
    assert "url.pathname.includes('/evidence/')" in SW
    assert "url.pathname.includes('/payment')" in SW
