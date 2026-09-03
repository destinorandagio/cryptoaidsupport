from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public_html"
HTML = (PUBLIC / "index.html").read_text()
BRIDGE = (PUBLIC / "assets" / "runtime-bridge.js").read_text()
SW = (PUBLIC / "sw.js").read_text()


def _section(start: str, end: str) -> str:
    return BRIDGE.split(start, 1)[1].split(end, 1)[0]


def test_private_evidence_consumer_is_same_origin_raw_bytes_and_browser_never_supplies_authority():
    assert "window.CryptoAIDProtectedRuntime=Object.freeze" in BRIDGE
    assert "uploadEvidence" in BRIDGE
    assert "`${API}/evidence`" in BRIDGE
    evidence = _section("async function uploadEvidence", "function publishCanonicalState")
    for required in [
        "method:'POST'",
        "credentials:'same-origin'",
        "cache:'no-store'",
        "'X-CAID-Case-ID'",
        "'X-CAID-Filename'",
        "'Content-Type':String(file.type",
        "body:file",
    ]:
        assert required in evidence
    for forbidden in [
        "authorization",
        "consent",
        "uploader",
        "mimeDetected",
        "providerIds",
        "expectedValue",
        "treasury",
        "chainId",
    ]:
        assert forbidden not in evidence
    for forbidden_storage in ["localStorage", "sessionStorage", "indexedDB"]:
        assert forbidden_storage not in evidence


def test_evidence_file_is_optional_but_if_selected_fails_closed_before_case_when_unsupported():
    assert 'accept="application/pdf,image/png,image/jpeg"' in HTML
    assert "const MAX_EVIDENCE_BYTES=25000000" in BRIDGE
    assert "new Set(['application/pdf','image/png','image/jpeg'])" in BRIDGE
    assert "evidence_type_rejected" in BRIDGE
    assert "evidence_size_rejected" in BRIDGE
    assert "Selected Evidence must be a PDF, PNG or JPEG" in BRIDGE
    assert "Selected Evidence must be between 1 byte and 25 MB" in BRIDGE
    case = _section("window.addEventListener('caid:case-request'", "window.addEventListener('caid:wallet-connect-request'")
    assert case.index("evidenceFileFromUI()") < case.index("request('/cases'")


def test_evidence_upload_occurs_only_after_canonical_case_and_requires_server_hash_match():
    case = _section("window.addEventListener('caid:case-request'", "window.addEventListener('caid:wallet-connect-request'")
    assert case.index("request('/cases'") < case.index("uploadEvidence(payload.caseId,evidenceFile)")
    assert "publishProtectedProjection(payload,'case_projection_invalid')&&payload.caseId" in case
    assert "stored.private_storage!==true" in case
    assert "stored.sha256!==localHash" in case
    assert "PRIVATE EVIDENCE STORED" in case
    assert "caid:evidence-uploaded" in case
    assert "Case created, but Evidence upload failed safely" in case


def test_canonical_case_success_enters_recovery_via_ui_router_not_hash_only():
    assert "function routeRecovery(){if(window.CryptoAIDUI&&typeof window.CryptoAIDUI.route==='function')window.CryptoAIDUI.route('recovery');else location.hash='recovery'}" in BRIDGE
    case = _section("window.addEventListener('caid:case-request'", "window.addEventListener('caid:wallet-connect-request'")
    assert "routeRecovery()" in case
    assert "location.hash='recovery'" not in case


def test_payment_intent_consumer_uses_upstream_quote_status_and_no_browser_settlement_path():
    payment = _section("async function requestPaymentIntent", "function installProtectedUx")
    for required in [
        "request('/payment/quote')",
        "quote.stage==='ACTIVATION_REQUIRED'",
        "'/payment/activation-intents'",
        "['FIRST_CASE','SUBSEQUENT_CASE'].includes(quote.stage)",
        "'/payment/case-intents'",
        "/payment/status?intentId=",
    ]:
        assert required in payment
    for forbidden in ["expectedValue", "treasury", "providerIds", "receiptStatus", "settlement", "txHash"]:
        assert forbidden not in payment
    assert "/payment/settle" not in BRIDGE
    for literal in ["50 POL", "450 POL", "500 POL"]:
        assert literal not in BRIDGE + HTML


def test_payment_action_is_fail_closed_until_packaged_bridge_and_live_case_wallet_are_present():
    assert 'id="paymentIntentButton"' in HTML
    assert 'id="paymentIntentButton" type="button" disabled' in HTML
    assert "This button never signs or submits a transaction." in HTML
    ux = _section("function installProtectedUx", "function routeRecovery")
    assert "button.disabled=false" in ux
    assert "state.identityDataState!=='LIVE'" in ux
    assert "typeof state.caseId!=='string'" in ux
    assert "wallet.status!=='CONNECTED'" in ux
    assert "wallet.dataState!=='LIVE'" in ux
    assert "Wallet connection is not SIC-ID authentication." in ux
    assert "No transaction was submitted." in ux


def test_payment_projection_is_server_authority_bound_and_never_equates_settlement_to_case_activation():
    projection = _section("function paymentProjection", "function publishPaymentIntent")
    assert "payload.payment_authority!=='CHAT02_EVIDENCE_PAYMENT_ENTITLEMENT'" in projection
    assert "payload.payable_value??payload.expected_value" in projection
    assert "paymentVerified:state==='SETTLED'" in projection
    assert "dataState:'LIVE'" in projection
    assert "case_active" not in projection
    assert "CASE_ACTIVE" not in projection


def test_protected_runtime_bridge_change_rolls_installed_pwa_shell_and_dynamic_truth_is_never_cached():
    assert "const SHELL_VERSION='2.1.11'" in SW
    assert "./assets/runtime-bridge.js" in SW
    assert "url.pathname.includes('/api/')" in SW
    assert "url.pathname.includes('/evidence/')" in SW
    assert "url.pathname.includes('/payment')" in SW
