import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "frontend" / "public_html" / "assets" / "runtime-bridge.js").read_text()
ACCOUNT_A = "0x" + ("11" * 20)
ACCOUNT_B = "0x" + ("22" * 20)


def _line(prefix):
    return next(line for line in BRIDGE.splitlines() if line.startswith(prefix))


def _run_connect_race(mode):
    node = shutil.which("node")
    assert node, "Node.js is required for executable connect validation race coverage"
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
            f"const ACCOUNT_A={json.dumps(ACCOUNT_A)};",
            f"const ACCOUNT_B={json.dumps(ACCOUNT_B)};",
            "class Provider{",
            "  constructor(mode){this.mode=mode;this.handlers=new Map();}",
            "  on(name,fn){const list=this.handlers.get(name)||[];list.push(fn);this.handlers.set(name,list);}",
            "  emit(name,payload){for(const fn of this.handlers.get(name)||[])fn(payload);}",
            "  request({method}){",
            "    if(method==='eth_requestAccounts'){",
            "      if(this.mode==='account_between_requests')return Promise.resolve([ACCOUNT_A]).then(value=>{this.emit('accountsChanged',[ACCOUNT_B]);return value;});",
            "      return Promise.resolve([ACCOUNT_A]);",
            "    }",
            "    if(method==='eth_chainId'){",
            "      if(this.mode==='chain_after_read_before_live')return Promise.resolve('0x89').then(value=>{this.emit('chainChanged','0x1');return value;});",
            "      return Promise.resolve('0x89');",
            "    }",
            "    throw new Error('unexpected_method');",
            "  }",
            "}",
            "const provider=new Provider(process.argv[1]);",
            "providers.set('p',{id:'p',name:'Test wallet',provider,source:'TEST'});",
            "(async()=>{",
            "  let ok=true; let error=null;",
            "  try{await connectWallet('p')}catch(err){ok=false;error=err&&err.message?err.message:String(err)}",
            "  process.stdout.write(JSON.stringify({ok,error,state:window.__CRYPTOAID_WALLET_STATE__}));",
            "})().catch(err=>{process.stderr.write(String(err));process.exit(2)});",
        ]
    )
    completed = subprocess.run(
        [node, "-e", script, mode],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _assert_validation_was_superseded(result):
    assert result["ok"] is False
    assert result["error"] == "wallet_revalidation_superseded"
    state = result["state"]
    assert state["status"] != "CONNECTED"
    assert state["dataState"] == "TO_VERIFY"
    assert state["needs_revalidation"] is True
    assert state.get("account") is None


def test_accounts_changed_during_initial_validation_cannot_publish_stale_live():
    _assert_validation_was_superseded(_run_connect_race("account_between_requests"))


def test_chain_changed_after_chain_read_before_live_cannot_publish_stale_live():
    _assert_validation_was_superseded(_run_connect_race("chain_after_read_before_live"))
