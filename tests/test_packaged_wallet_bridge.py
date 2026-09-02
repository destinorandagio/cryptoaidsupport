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
