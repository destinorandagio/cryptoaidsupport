# HANDOFF_05 — CRYPTO AID UI/UX/PWA — v2.1.6

cycle=20260902-2240
stage=05/06 UI_UX_PWA
owner=CHAT04_UI_UX_PWA
growth_owner=CHAT09_GROWTH_MARKETING_PARTNERSHIP
status=HANDOFF_READY_ENGINEERING_CANDIDATE_NO_GO
release_state=NO_GO_SERIAL_REFRESH_RUNTIME_BRIDGE_AG_CHAT05_CHAT10
branch=feat/chat04-sicid-login-freshmain-1642
serial_pr50_observed=5ccbb6a0c989d5f6a22e7ddca7785f4db2bbd902
runtime_logic_test_head=e6427ef1ab9136c22dcfeca6cf60c81c33ade173
ui_version=2.1.2
pwa_shell_version=2.1.5
shared_production_public_html_mutated=NO
production_MASTER_mutated=NO

## P0 CLOSED — COREAPI 1.1 LOGIN/RESUME NEGOTIATION

Fresh serial reconciliation found the public UI requesting only CoreAPI 1.0.0 while the exact PR50 authoritative `core/api.py` declares CoreAPI 1.1.0. CHAT04 now accepts CoreAPI 1.0.0/1.1.0 explicitly, prefers 1.1.0 and sends `supportedCoreApiVersions`, `preferredCoreApiVersion` and `FAIL_CLOSED_EXPLICIT_VERSION_LIST` on `caid:sicid-login-request`. `requiresLiveSession=true`, `callerMayProvideIdentity=false` and `walletIsIdentity=false` remain mandatory. CHAT04 still does not create or authenticate identity.

Because `assets/app.js` is part of the offline shell, the Service Worker advances to `caid-shell-v2.1.5`. Previous namespace-scoped deletion, current-cache-only reads, same-origin/query canonicalization, `skipWaiting()`, `clients.claim()` and `/api/`, `/evidence/`, `/payment` dynamic-truth exclusions remain intact.

## GOLDEN PATH PRESENTATION

Landing → LIVE SIC-ID request/projection → Search → Twin/TO_VERIFY → +CASE 4-step → local-only Evidence preflight → upstream payment-state presentation → My Recovery → one Next Action → Profile.

Navigation remains HOME | SEARCH | +CASE | RECOVERY | PROFILE. CONNECT WALLET remains persistent and optional. Search/+CASE/Recovery/Profile continue to require LIVE SIC-ID. Recovery/Profile private projection remains scrubbed fail-closed on identity loss. No frontend prices/payment verification/Case truth/Knowledge authority were introduced.

## ENGINEERING EVIDENCE

- exact runtime/test head: `e6427ef1ab9136c22dcfeca6cf60c81c33ade173`;
- GitHub Actions CI `33681190014` SUCCESS: checkout, Python setup/deps, compile, full pytest, PHP baseline, staging PWA shell package/restore smoke and token scan PASS;
- Release Candidate Package `33681190016` SUCCESS;
- PR17 remains OPEN / DRAFT / MERGEABLE / REVIEW_ONLY;
- no merge, real signing, payment, transaction, production deploy or cutover performed.

## RELEASE-BLOCKING RUNTIME BRIDGE FINDING

The exact serial PR50 public `index.html` loads only `assets/app.js`. The UI dispatches `caid:sicid-login-request`, `caid:case-request` and wallet events and expects approved Twin/Wallet runtime adapters, but the static public package does not load a trusted adapter bridge script/module. Consequently a synthetic adapter/listener injected through DevTools or a test harness is not evidence that the public MVP is usable.

CHAT00/CHAT01/CHAT03 must compose the trusted protected-origin runtime bridge or equivalent without creating a second Core/Twin/Case authority. CHAT04 will consume that bridge; it must not fabricate identity, Case, payment, Twin or wallet truth.

## ACCESSIBILITY / PERFORMANCE / GROWTH

No HTML/CSS/copy redesign, framework, remote asset, tracker or marketing SDK was added. Existing skip-link, focus-visible, route-heading focus, 44px touch target, 390px overflow guard, aria-live and reduced-motion contracts remain. CHAT09 stays feature-frozen: HELP_FIRST, EVIDENCE_FIRST, VALUE_BEFORE_CTA, NO_PURCHASE_NEEDED, OFFICIAL_FREE_PATH_FIRST, no fake urgency/scarcity/testimonials, no recovery guarantee and no ROI.

## AG COORDINATION

CHAT00 must first publish one refreshed exact serial Golden SHA containing UI 2.1.2/PWA 2.1.5 and the trusted runtime bridge/equivalent. Antigravity must then execute assertions 1-30 on that same SHA.

Assertion 29 — COREAPI 1.1 NEGOTIATION: capture a normal user-triggered SIC-ID login event and prove CoreAPI 1.1.0 is preferred/current, 1.0.0+1.1.0 are explicitly supported, fail-closed negotiation is present, and an unsupported adapter cannot create LIVE identity.

Assertion 30 — NORMAL-PACKAGE TRUSTED RUNTIME BRIDGE: do not inject adapters/globals/listeners through DevTools or a test harness. Launch exactly the refreshed public package and prove its trusted bridge consumes SIC-ID login/resume and Case requests and exposes approved Twin/Wallet adapters. Known/unknown Search and +CASE must work through packaged wiring; wallet remains explicit-provider and never authenticates SIC-ID. If the package lacks this bridge, mark FAIL with exact missing script/module/listener/network evidence rather than emulating success.

Assertions 1-28 remain mandatory; PWA cache/update/query/offline assertions now expect `caid-shell-v2.1.5`. Persist exact SHA, OS/browser/version, serve command/URL/timestamp, event payloads, SW/controller/cache/network/console evidence and screenshot SHA-256. No real signing/payment/transaction/deploy is authorized.

## GLOBAL BLOCKERS

1. CHAT00 must serial-refresh PR50 with UI 2.1.2/PWA 2.1.5 and trusted runtime bridge/equivalent.
2. Antigravity assertions 1-30 are absent on that refreshed exact serial SHA.
3. CHAT05 full Golden Journey/privacy/security acceptance is pending.
4. CHAT10 final package/manifest/backup/restore/rollback is pending.
5. Physical wallet/sign/payment/tx/deploy remain HUMAN_GATE/NOT_TESTED.

GO_NO_GO: NO_GO_SERIAL_REFRESH_RUNTIME_BRIDGE_AG_CHAT05_CHAT10
READBACK_REQUIRED: true
