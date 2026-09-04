# HANDOFF_05 — CRYPTO AID UI/UX/PWA — v2.1.2

cycle=20260902-1841
stage=05/06 UI_UX_PWA
owner=CHAT04_UI_UX_PWA
growth_owner=CHAT09_GROWTH_MARKETING_PARTNERSHIP
status=HANDOFF_READY_ENGINEERING_CANDIDATE_NO_GO
release_state=NO_GO_GLOBAL_SERIAL_RUNTIME_QA_GATES
branch=feat/chat04-sicid-login-freshmain-1642
parent_main_observed=8a5666ced267acac8f4c638d204e40908d2e1e0b
runtime_logic_test_head=3c510c75b0d2d77256ed43ab9d8a1ec6249dcb98
ui_version=2.1.1
pwa_shell_version=2.1.1
shared_production_public_html_mutated=NO
production_MASTER_mutated=NO

## P0 CLOSED IN THIS CYCLE — PRIVATE RECOVERY / PROFILE PROJECTION

Fresh source review found a release-blocking privacy gap: Search and +CASE already required a LIVE SIC-ID projection, but Recovery and Profile did not. `renderRecovery()` could consume and render cached/stale `nextAction`, timeline and persisted payment presentation from `window.__CRYPTOAID_STATE__` even when SIC-ID was no longer LIVE. Profile could also show a non-LIVE cached SIC-ID string.

UI 2.1.1 now fails closed:

- protected routes are Search, +CASE, Recovery and Profile;
- Recovery checks LIVE identity before consuming private Case projection fields;
- without LIVE identity it renders only a locked TO_VERIFY state, disables Next Action, clears payment presentation with `renderPayment(null)` and does not read/render upstream nextAction/timeline values;
- Profile displays the SIC-ID value only while the Core projection is LIVE;
- a `caid:state-updated` transition from LIVE to non-LIVE ejects any protected view to HOME after the private projection is scrubbed;
- wallet remains optional and is never identity.

Because this changes security-sensitive `app.js`, the PWA shell is advanced to `caid-shell-v2.1.1` so already-installed clients can refresh the privacy gate. Existing `skipWaiting()`, old-cache cleanup, `clients.claim()` and `/api/` `/evidence/` `/payment` cache exclusions remain unchanged.

## GOLDEN PATH PRESENTATION

Landing → LIVE SIC-ID request/projection → Search → Twin/TO_VERIFY → +CASE 4-step → local-only Evidence preflight → upstream payment-state presentation → My Recovery → one Next Action → Profile.

Navigation remains HOME | SEARCH | +CASE | RECOVERY | PROFILE. CONNECT WALLET remains persistent and optional. No frontend prices/payment verification/Case truth/Knowledge authority were introduced.

## ENGINEERING EVIDENCE

- exact code/test head before handoff metadata: `3c510c75b0d2d77256ed43ab9d8a1ec6249dcb98`;
- local `node --check` app.js PASS;
- local `node --check` sw.js PASS;
- local Python compile of `tests/test_frontend_contract.py` PASS;
- focused privacy/PWA assertions 6/6 PASS;
- full GitHub Actions CI on final metadata head must be read before promotion; isolated candidate evidence is not serial runtime acceptance.

## ACCESSIBILITY / PERFORMANCE

No HTML/CSS redesign or new framework/asset/tracker was introduced. Existing skip-link, focus-visible, heading focus transfer, 44px touch target, 390px overflow guard and reduced-motion contracts remain untouched. Real-browser keyboard/focus and performance remain factual Antigravity gates.

## AG COORDINATION

Do not credit isolated PR17 as final release evidence. On the single exact serial Golden SHA published by CHAT00, Antigravity must execute all prior 24 assertions plus:

25. PRIVATE PROJECTION DOM SCRUB: seed a synthetic non-LIVE projection containing a SIC-ID plus sensitive `nextAction`, timeline and persisted payment display values. Direct `#recovery` and `#profile` must fail closed to HOME/LOGIN_OR_RESUME; the DOM must not contain the stale SIC-ID, action title/description, timeline labels, payment amount or purpose. Then establish a LIVE SIC-ID projection and prove authorized rendering can occur. Transition LIVE → CACHED/TO_VERIFY and prove private values are scrubbed immediately and the protected view returns to HOME. Run at 390x844 and desktop; persist exact SHA, OS/browser/version, serve command, URL, timestamp, screenshots/hashes, DOM/network/console and Service Worker/cache state.

No real signing/payment/transaction/deploy is authorized.

## GROWTH

CHAT09 advances only to v0.4.1 contract alignment: privacy-safe conversion copy may invite the user to resume SIC-ID to see private Recovery/Profile state, but may not imply authentication success, purchase requirement, recovery guarantee, urgency or ROI. Feature freeze remains active; no campaign/runtime expansion occurred.

## GLOBAL BLOCKERS

1. CHAT00 exact serial Golden candidate containing this delta is not yet accepted/published.
2. Antigravity real-origin assertions 1-25 are absent on the final serial SHA.
3. CHAT05 full Golden Journey/privacy/security acceptance is pending.
4. CHAT10 final package/manifest/backup/restore/rollback is pending.
5. Physical wallet/sign/payment/tx/deploy remain HUMAN_GATE/NOT_TESTED.

GO_NO_GO: NO_GO_GLOBAL_SERIAL_RUNTIME_QA_GATES
READBACK_REQUIRED: true
