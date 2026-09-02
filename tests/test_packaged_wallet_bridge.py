import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "frontend" / "public_html" / "assets" / "runtime-bridge.js").read_text()


def _run_chain_normalizer(value):
    node = shutil.which("node")
    assert node, "Node.js is required for executable wallet bridge contract coverage"
    line = next(line for line in BRIDGE.splitlines() if line.startswith("const normalizeChainId="))
    script = f"{line}\nprocess.stdout.write(JSON.stringify(normalizeChainId(JSON.parse(process.argv[1]))));"
    completed = subprocess.run(
        [node, "-e", script, json.dumps(value)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _run_wallet_event_transition(kind, payload):
    node = shutil.which("node")
    assert node, "Node.js is required for executable wallet lifecycle coverage"
    normalize = next(line for line in BRIDGE.splitlines() if line.startswith("const normalizeChainId="))
    transition = next(line for line in BRIDGE.splitlines() if line.startswith("const walletEventTransition="))
    script = (
        "const TARGET_CHAIN_ID=137;\n"
        f"{normalize}\n{transition}\n"
        "process.stdout.write(JSON.stringify(walletEventTransition(process.argv[1],JSON.parse(process.argv[2]))));"
    )
    completed = subprocess.run(
        [node, "-e", script, kind, json.dumps(payload)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_wallet_bridge_is_packaged_explicit_and_never_identity_or_signing_authority():
    assert "window.CryptoAIDWallet=Object.freeze" in BRIDGE
    assert "contractVersion:'1.2.0'" in BRIDGE
    assert "connectIsAuthentication:false" in BRIDGE
    assert "caid:wallet-connect-request" in BRIDGE
    assert "explicitProviderChoice!==true" in BRIDGE
    assert "eip6963:announceProvider" in BRIDGE
    assert "eip6963:requestProvider" in BRIDGE
    assert "eth_requestAccounts" in BRIDGE
    assert "eth_chainId" in BRIDGE
    assert "chooseProvider(options)" in BRIDGE
    for forbidden in [
        "personal_sign",
        "eth_sign",
        "eth_signTypedData",
        "eth_sendTransaction",
        "eth_sendRawTransaction",
        "wallet_switchEthereumChain",
        "wallet_addEthereumChain",
    ]:
        assert forbidden not in BRIDGE


def test_wallet_chain_parsing_is_fail_closed_for_polygon_137():
    assert _run_chain_normalizer("0x89") == 137
    assert _run_chain_normalizer("137") == 137
    assert _run_chain_normalizer("0x1") == 1
    assert _run_chain_normalizer("not-a-chain") is None


def test_runtime_auth_boundary_and_handled_errors_are_visible():
    assert "authBoundary:'SANDBOX_LOCAL_ONLY'" in BRIDGE
    assert "LOCAL SANDBOX AUTH" in BRIDGE
    assert "caid:bridge-error" in BRIDGE
    assert "SIC-ID sandbox sign-in failed safely" in BRIDGE
    assert "Case request failed safely" in BRIDGE
    login = BRIDGE.split("window.addEventListener('caid:sicid-login-request'", 1)[1].split("window.addEventListener('caid:case-request'", 1)[0]
    case = BRIDGE.split("window.addEventListener('caid:case-request'", 1)[1].split("window.addEventListener('caid:wallet-connect-request'", 1)[0]
    assert ".catch(()=>visibleError(" in login
    assert ".catch(()=>visibleError(" in case


def test_wallet_chooser_declared_modal_has_keyboard_focus_and_inert_contract():
    chooser = BRIDGE.split("function chooseProvider", 1)[1].split("function publishWalletState", 1)[0]
    for required in [
        "aria-modal",
        "document.activeElement",
        "panel.addEventListener('keydown'",
        "event.key==='Escape'",
        "event.key!=='Tab'",
        "event.shiftKey",
        "appShell.inert=true",
        "appShell.inert=shellWasInert",
        "restoreFocus",
        "document.contains(invoker)",
        "first.focus()",
        "last.focus()",
    ]:
        assert required in chooser
    assert "close(null,new Error('wallet_choice_cancelled'))" in chooser
    assert "close(option.id)" in chooser


def test_wallet_disconnect_account_and_chain_changes_fail_closed_without_touching_sicid():
    assert "accountsChanged" in BRIDGE
    assert "chainChanged" in BRIDGE
    assert "disconnect" in BRIDGE
    assert "status:'WRONG_CHAIN'" in BRIDGE
    assert "status:'DISCONNECTED'" in BRIDGE
    wallet_section = BRIDGE.split("async function connectWallet", 1)[1].split("window.addEventListener('caid:sicid-login-request'", 1)[0]
    for forbidden_identity in ["sicId", "sic_id", "userId", "user_id", "identityDataState"]:
        assert forbidden_identity not in wallet_section


def test_wallet_lifecycle_events_never_self_promote_live_and_require_explicit_revalidation():
    cases = [
        ("accountsChanged", ["0xB"]),
        ("accountsChanged", []),
        ("accountsChanged", [""]),
        ("chainChanged", "0x1"),
        ("chainChanged", "0x89"),
        ("chainChanged", "137"),
        ("chainChanged", "garbage"),
        ("disconnect", None),
        ("accountsChanged", ["0xC", "0xD"]),
        ("chainChanged", 137),
    ]
    for kind, payload in cases:
        state = _run_wallet_event_transition(kind, payload)
        assert state["dataState"] == "TO_VERIFY"
        assert state["needs_revalidation"] is True
        assert state.get("account") is None
        assert state["status"] != "CONNECTED"

    assert _run_wallet_event_transition("accountsChanged", ["0xB"])["status"] == "REVALIDATION_REQUIRED"
    assert _run_wallet_event_transition("accountsChanged", [])["status"] == "DISCONNECTED"
    assert _run_wallet_event_transition("chainChanged", "0x1")["status"] == "WRONG_CHAIN"
    assert _run_wallet_event_transition("chainChanged", "0x89")["status"] == "REVALIDATION_REQUIRED"


def test_wallet_lifecycle_generation_invalidates_old_listener_and_prevents_stale_account_resurrection_contract():
    lifecycle = BRIDGE.split("let walletValidationGeneration=0;", 1)[1].split("window.addEventListener('caid:sicid-login-request'", 1)[0]
    assert "generation!==walletValidationGeneration" in lifecycle
    assert "walletValidationGeneration+=1" in lifecycle
    assert "needs_revalidation:true" in lifecycle
    assert "wallet_revalidation_superseded" in lifecycle
    assert "registerWalletLifecycle(entry,generation)" in lifecycle
    # Event callbacks delegate to the fail-closed transition and never publish LIVE directly.
    handlers = lifecycle.split("function registerWalletLifecycle", 1)[1].split("async function connectWallet", 1)[0]
    assert "walletEventTransition" not in handlers  # transition is applied only through invalidateWalletState
    assert "invalidateWalletState" in handlers
    assert "dataState:'LIVE'" not in handlers
    assert "status:'CONNECTED'" not in handlers
