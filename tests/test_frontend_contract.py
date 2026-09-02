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
    for literal in ['50 POL','450 POL','500 POL']: assert literal not in JS+HTML

def test_required_nav_and_connect():
    for item in ['HOME','SEARCH','+CASE','RECOVERY','PROFILE','CONNECT WALLET']: assert item in HTML

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
