import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "frontend" / "public_html" / "assets" / "runtime-bridge.js").read_text()
ACCOUNT = "0x" + ("ab" * 20)


def _line(prefix):
    return next(line for line in BRIDGE.splitlines() if line.startswith(prefix))


def _run_registration_case(case):
    node = shutil.which("node")
    assert node, "Node.js is required for executable wallet provider capability coverage"
    script = "\n".join(
        [
            "const providers=new Map();",
            _line("function registerProvider"),
            "const request=()=>Promise.resolve(null);",
            "const fn=()=>{};",
            "const cases={",
            "  request_only:{request},",
            "  missing_on:{request,removeListener:fn},",
            "  missing_remove:{request,on:fn},",
            "  nonfunction_on:{request,on:true,removeListener:fn},",
            "  nonfunction_remove:{request,on:fn,removeListener:true},",
            "  complete:{request,on:fn,removeListener:fn},",
            "};",
            "registerProvider('p','Provider',cases[process.argv[1]],'TEST');",
            "process.stdout.write(JSON.stringify({registered:providers.has('p'),size:providers.size}));",
        ]
    )
    completed = subprocess.run([node, "-e", script, case], check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def _run_connect_with_capabilities(on_kind="function", remove_kind="function"):
    node = shutil.which("node")
    assert node, "Node.js is required for executable wallet connect capability coverage"
    script = "\n".join(
        [
            "const TARGET_CHAIN_ID=137;",
            "const providers=new Map();",
            "global.CustomEvent=class CustomEvent{constructor(type,init={}){this.type=type;this.detail=init.detail;}};",
            "global.window={__CRYPTOAID_WALLET_STATE__:null,dispatchEvent:()=>{}};",
            _line("const normalizeChainId="),
            _line("const normalizeAccount="),
            _line("const walletEventTransition="),
            _line("function publishWalletState"),
            _line("let walletValidationGeneration="),
            _line("function invalidateWalletState"),
            _line("function registerWalletLifecycle"),
            _line("async function connectWallet"),
            f"const ACCOUNT={json.dumps(ACCOUNT)};",
            "const provider={request:({method})=>Promise.resolve(method==='eth_requestAccounts'?[ACCOUNT]:'0x89')};",
            "provider.on=process.argv[1]==='function'?(()=>{}):true;",
            "provider.removeListener=process.argv[2]==='function'?(()=>{}):true;",
            "providers.set('p',{id:'p',name:'Provider',provider,source:'TEST'});",
            "(async()=>{let ok=true,error=null;try{await connectWallet('p')}catch(err){ok=false;error=err&&err.message?err.message:String(err)}process.stdout.write(JSON.stringify({ok,error,state:window.__CRYPTOAID_WALLET_STATE__}));})().catch(err=>{process.stderr.write(String(err));process.exit(2)});",
        ]
    )
    completed = subprocess.run([node, "-e", script, on_kind, remove_kind], check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def test_registration_requires_request_on_and_remove_listener_before_provider_is_selectable():
    for case in ["request_only", "missing_on", "missing_remove", "nonfunction_on", "nonfunction_remove"]:
        assert _run_registration_case(case) == {"registered": False, "size": 0}
    assert _run_registration_case("complete") == {"registered": True, "size": 1}


def test_connect_rechecks_event_capability_and_never_publishes_live_when_lifecycle_is_unobservable():
    for on_kind, remove_kind in [("nonfunction", "function"), ("function", "nonfunction")]:
        result = _run_connect_with_capabilities(on_kind, remove_kind)
        assert result["ok"] is False
        assert result["error"] == "wallet_provider_lifecycle_unavailable"
        state = result["state"]
        assert state["status"] != "CONNECTED"
        assert state["dataState"] == "TO_VERIFY"
        assert state["needs_revalidation"] is True
        assert state.get("account") is None
