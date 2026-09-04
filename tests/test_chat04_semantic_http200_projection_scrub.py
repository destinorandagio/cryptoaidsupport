import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "frontend" / "public_html" / "assets" / "runtime-bridge.js").read_text()

PRIVATE_CASE_KEYS = [
    "caseId",
    "caseState",
    "caseDataState",
    "nextAction",
    "timeline",
    "paymentIntent",
]


def _function_block(name: str, next_name: str) -> str:
    start = BRIDGE.index(f"function {name}(")
    end = BRIDGE.index(f"function {next_name}(", start)
    return BRIDGE[start:end]


def _execute_invalid_http200_projection() -> dict:
    node = shutil.which("node")
    assert node, "Node.js is required for the CHAT04 semantic projection regression"
    render = _function_block("renderCanonicalCaseState", "publishCanonicalState")
    publish = _function_block("publishCanonicalState", "clearCanonicalState")
    clear = _function_block("clearCanonicalState", "publishProtectedProjection")
    protected = _function_block("publishProtectedProjection", "paymentProjection")
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
{protected}
const result=publishProtectedProjection({{}},'session_projection_invalid');
process.stdout.write(JSON.stringify({{result,state:window.__CRYPTOAID_STATE__,calls}}));
"""
    completed = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def test_semantic_invalid_http200_projection_scrubs_private_state_fail_closed():
    output = _execute_invalid_http200_projection()
    assert output["result"] is False
    assert output["state"]["identityDataState"] == "TO_VERIFY"
    assert output["state"]["dataState"] == "TO_VERIFY"
    assert output["state"]["reason"] == "session_projection_invalid"
    for key in PRIVATE_CASE_KEYS:
        assert key not in output["state"]
    assert "caid:state-updated" in output["calls"]


def test_all_protected_projection_consumers_use_fail_closed_publisher():
    assert "function publishProtectedProjection(" in BRIDGE
    resume_start = BRIDGE.index("async function resume(")
    resume_end = BRIDGE.index("function registerProvider(", resume_start)
    resume = BRIDGE[resume_start:resume_end]
    assert "publishProtectedProjection(await request('/session')" in resume
    assert "return publishCanonicalState(await request('/session'))" not in resume

    login_start = BRIDGE.index("window.addEventListener('caid:sicid-login-request'")
    case_start = BRIDGE.index("window.addEventListener('caid:case-request'", login_start)
    login = BRIDGE[login_start:case_start]
    assert "publishProtectedProjection" in login
    assert ".then(publishCanonicalState)" not in login

    case_end = BRIDGE.index("window.addEventListener('caid:wallet-connect-request'", case_start)
    case_listener = BRIDGE[case_start:case_end]
    assert "publishProtectedProjection(payload" in case_listener


def test_semantic_projection_fix_requires_precached_bridge_rollover():
    sw = (ROOT / "frontend" / "public_html" / "sw.js").read_text()
    assert "./assets/runtime-bridge.js" in sw
    assert "const SHELL_VERSION='2.1.14'" in sw