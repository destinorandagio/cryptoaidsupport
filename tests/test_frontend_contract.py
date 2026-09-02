from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1]/'frontend'/'public_html'
HTML=(ROOT/'index.html').read_text()
CSS=(ROOT/'assets/app.css').read_text()
JS=(ROOT/'assets/app.js').read_text()
SW=(ROOT/'sw.js').read_text()

def test_runtime_is_self_contained():
    assert not re.search(r'https?://',HTML+CSS+JS+SW)

def test_no_frontend_economic_truth_or_generic_signing():
    banned=['first_activation_pol','first_case_residual_pol','subsequent_case_pol','personal_sign','eth_sendTransaction','window.ethereum']
    for token in banned: assert token not in JS+HTML
    for literal in ['50 POL','450 POL','500 POL','100 USDT','400 USDT','500 USDT']: assert literal not in JS+HTML

def test_required_nav_and_connect():
    for item in ['HOME','SEARCH','+CASE','RECOVERY','PROFILE','CONNECT WALLET']: assert item in HTML

def test_sicid_login_is_explicit_first_step_and_fail_closed():
    assert 'SIGN IN / SIC-ID' in HTML
    assert HTML.index('SIGN IN / SIC-ID') < HTML.index('id="heroSearchForm"')
    assert "coreApi:'1.0.0'" in JS
    assert "caid:sicid-login-request" in JS
    assert "action:'LOGIN_OR_RESUME'" in JS
    assert "requiresLiveSession:true" in JS
    assert "callerMayProvideIdentity:false" in JS
    assert "walletIsIdentity:false" in JS
    assert 'No session was created.' in JS
    assert 'data-sicid-login' in HTML

def test_live_sicid_is_required_before_search_and_case():
    assert "ui:'2.1.0'" in JS
    assert "const PROTECTED_GOLDEN_ROUTES=new Set(['search','case'])" in JS
    assert "r.identityDataState==='LIVE'" in JS
    assert "PROTECTED_GOLDEN_ROUTES.has(name)&&!requireLiveIdentity()" in JS
    assert "Sign in with a live SIC-ID session to continue." in JS
    assert "if(route('search'))search(input.value)" in JS
    assert "if(!requireLiveIdentity()){route('home');return}" in JS
    assert "btn.disabled=live" in JS
    assert "RESUME SIC-ID" in JS
    assert "hasLiveIdentity" in JS

def test_truth_labels_present():
    for item in ['LIVE','CACHED','HISTORICAL','DERIVED','TO_VERIFY']: assert item in JS+HTML

def test_accessibility_static_contract():
    assert 'Skip to main content' in HTML
    assert ':focus-visible' in CSS and 'outline:3px' in CSS
    assert 'input:focus-visible+label' in CSS
    assert 'heading.tabIndex=-1' in JS
    assert 'prefers-reduced-motion:reduce' in CSS
    assert 'min-height:44px' in CSS
    assert 'aria-live="polite"' in HTML
    assert 'aria-label="SIC-ID sign in"' in HTML

def test_390_overflow_guard():
    assert '@media(max-width:390px)' in CSS
    assert 'overflow-x:clip' in CSS

def test_private_evidence_and_payment_fail_closed():
    assert 'PRIVATE BY DEFAULT' in HTML
    assert "intent.persisted===true&&intent.verified===true&&intent.expired===false" in JS
    assert 'Transaction submission never activates a Case by itself.' in JS

def test_service_worker_excludes_dynamic_truth():
    assert "url.pathname.includes('/api/')" in SW
    assert "url.pathname.includes('/evidence/')" in SW
    assert "url.pathname.includes('/payment')" in SW
    assert "req.mode==='navigate'" in SW

def test_manifest_valid():
    data=json.loads((ROOT/'manifest.webmanifest').read_text())
    assert data['display']=='standalone'
    assert data['theme_color']=='#ffffff'

def test_twin_wallet_contract_compatibility_is_explicit_and_fail_closed():
    assert "ui:'2.1.0'" in JS
    assert "twin:Object.freeze(['1.0.0','1.1.0','1.2.0'])" in JS
    assert "walletMatrix:Object.freeze(['1.0.0','1.1.0','1.2.0'])" in JS
    assert "dappmap:Object.freeze(['1.0.0','1.1.0','1.2.0'])" in JS
    assert "knowledgeContext:Object.freeze(['1.0.0'])" in JS
    assert "contractRejected:true" in JS
    assert "supportedWalletMatrixVersions" in JS
    assert "preferredWalletMatrixVersion:PREFERRED.walletMatrix" in JS
    assert "connectIsAuthentication:false" in JS
    assert "FAIL_CLOSED_EXPLICIT_VERSION_LIST" in JS
    assert "acceptedContracts:ACCEPTED" in JS
    assert "acceptsContract:acceptedVersion" in JS

def test_twin_12_result_shapes_are_fail_closed_and_case_continuable():
    assert "result.state==='MATCH'" in JS
    assert "candidate_status==='USER_SUBMITTED_TO_VERIFY'" in JS
    assert "ambiguous:result.results.length>1" in JS
    assert 'The UI will not silently pick a Twin.' in JS
    assert 'CONTINUE TO +CASE' in JS
    assert 'appendProvenance' in JS
    assert 'confidence' in JS
