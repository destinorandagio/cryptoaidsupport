# HANDOFF_05 — CRYPTO AID UI/UX/PWA — v2.1.1

cycle=20260902-1741
stage=05/06 UI_UX_PWA
owner=CHAT04_UI_UX_PWA
growth_owner=CHAT09_GROWTH_MARKETING_PARTNERSHIP
status=HANDOFF_READY_ENGINEERING_CANDIDATE_NO_GO
release_state=NO_GO_GLOBAL_AUTHORITY_SERIAL_RUNTIME_QA_GATES
branch=feat/chat04-sicid-login-freshmain-1642
parent_main_observed=b7f5345fdf4fa4de06fe9e1d601aa3d6aa1df843
ui_version=2.1.0
pwa_shell_version=2.1.0
pwa_logic_test_head=fdd180d2244559651a724744325b5f90552972e0
shared_production_public_html_mutated=NO
production_MASTER_mutated=NO

## P0 CLOSED IN THIS CYCLE — PWA UPDATE COHERENCE

The security-critical UI 2.1.0 LIVE SIC-ID gate was already CI-green, but `frontend/public_html/sw.js` still used cache namespace `caid-shell-v1.7.0`. An already-installed client could therefore remain on an old shell/app.js until the browser observed a changed service-worker script and completed the update lifecycle.

The candidate now binds the shell cache to UI 2.1.0:

- `SHELL_VERSION='2.1.0'` and cache `caid-shell-v2.1.0`;
- install precaches the complete self-contained shell then calls `skipWaiting()`;
- activate deletes old shell caches and calls `clients.claim()`;
- `/api/`, `/evidence/` and `/payment` remain excluded from authoritative cache handling;
- no network asset, tracker, framework or marketing runtime was added.

This follows the current Service Worker lifecycle pattern: a byte-changed worker installs as a new version, `skipWaiting()` can activate it immediately, and `clients.claim()` can take control of in-scope clients. Real-browser update behavior is still a factual runtime gate and is not promoted from static/CI evidence.

## GOLDEN PATH PRESENTATION

Landing → LIVE SIC-ID request/projection → Search → Twin/TO_VERIFY → +CASE 4-step → local-only Evidence preflight → upstream payment-state presentation → My Recovery → one Next Action → Profile.

Navigation remains HOME | SEARCH | +CASE | RECOVERY | PROFILE. CONNECT WALLET remains persistent and optional. Wallet connect remains Polygon 137, explicit-provider, `connectIsAuthentication=false`.

## CONTRACT / SAFETY

- Core 0.3.13; CoreAPI 1.0.0 consumed only as request/projection authority.
- Search/+CASE/Case-submit still require non-empty `sicId` + `identityDataState=LIVE`.
- Twin/Wallet/DAPPMAP accepted migration set remains 1.0.0 / 1.1.0 / 1.2.0.
- Knowledge Context accepted 1.0.0.
- Unknown/unsupported/ambiguous project state stays TO_VERIFY; no silent canonical promotion.
- Evidence/payment remain fail-closed and upstream-authoritative.
- No frontend economic truth, generic signing, real transaction, recovery guarantee, ROI, fake urgency or fake scarcity.

## ENGINEERING EVIDENCE

- PWA logic/test head `fdd180d2244559651a724744325b5f90552972e0`.
- GitHub Actions CI `33650534945`: SUCCESS on that exact code/test head.
- Added deterministic regression for shell-version/UI coherence, prompt activation, old-cache cleanup, client claim, required shell assets and dynamic-truth cache exclusions.
- Existing LIVE SIC-ID, Twin/TO_VERIFY, wallet, a11y and 390px static contracts remain covered by repository tests.
- Real-origin exact serial browser/PWA install/update/offline/reconnect: NOT_TESTED.

## AG COORDINATION

Do not credit isolated PR17 as final release evidence. On the single exact serial Golden SHA published by CHAT00, Antigravity must execute all prior 23 assertions plus:

24. PWA upgrade coherence: start from/seed a prior shell cache state representative of `caid-shell-v1.7.0`, load the new exact serial worker, record registration/install/activate/controller state, prove the old shell cache is removed, `caid-shell-v2.1.0` exists, current `app.js`/UI 2.1 controls the client, warm offline shell works, reconnect does not invent Case/payment/Twin state, and persist browser/OS/commands/cache keys/network-console/screenshots/hashes/timestamp.

No real signing/payment/transaction/deploy is authorized.

## GROWTH

CHAT09 remains v0.4.0. Feature freeze is maintained: HELP_FIRST, EVIDENCE_FIRST, VALUE_BEFORE_CTA, NO_PURCHASE_NEEDED, OFFICIAL_FREE_PATH_FIRST, no fake urgency/scarcity/testimonials, no recovery guarantee, no ROI. No campaign/runtime expansion occurred in this cycle.

## GLOBAL BLOCKERS

1. Global Case-payment authority/economic reconciliation remains outside CHAT04 and release-blocking until serial acceptance.
2. One exact serial Golden candidate has not yet completed independent acceptance.
3. Real-origin 390px/desktop/a11y/PWA install-update-offline-reconnect evidence is absent on final serial head.
4. CHAT05 full Golden Journey and CHAT10 final package/manifest/backup/restore/rollback remain pending.
5. Physical wallet/sign/payment/tx/deploy remain HUMAN_GATE/NOT_TESTED.

GO_NO_GO: NO_GO_GLOBAL_SERIAL_RUNTIME_QA_GATES
READBACK_REQUIRED: true
