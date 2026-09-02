# HANDOFF_05 — CRYPTO AID UI/UX/PWA — v2.1.0

cycle=20260902-1712
stage=05/06 UI_UX_PWA
owner=CHAT04_UI_UX_PWA
growth_owner=CHAT09_GROWTH_MARKETING_PARTNERSHIP
status=HANDOFF_READY_ENGINEERING_CANDIDATE_NO_GO
release_state=NO_GO_GLOBAL_AUTHORITY_SERIAL_RUNTIME_QA_GATES
branch=feat/chat04-sicid-login-freshmain-1642
parent_main_observed=fd952c591bb1f2c09576458c2a48c70af0c1b814
runtime_logic_head=7213b4deb44d0be806a9268bfb45944c56511056
shared_production_public_html_mutated=NO
production_MASTER_mutated=NO

## P0 CLOSED IN THIS CYCLE

UI v2.0.0 exposed an explicit SIC-ID LOGIN_OR_RESUME request, but Search and +CASE could still be entered when the runtime projection had no LIVE SIC-ID. That contradicted the Golden Path ordering Landing → SIC-ID/login → Search.

UI v2.1.0 now consumes the CHAT01/CoreAPI projection fail-closed:

- a usable identity projection requires non-empty `sicId` AND `identityDataState === LIVE`;
- Search and Case routes are centrally protected;
- hero Search does not execute a Twin query when the protected route rejects;
- Case submit re-checks LIVE identity, covering identity/session expiry after entering the wizard;
- CACHED/TO_VERIFY identity keeps the resume CTA enabled rather than pretending authentication succeeded;
- when LIVE identity disappears during a state update, protected Search/Case views return to HOME;
- the UI requests trusted Core `LOGIN_OR_RESUME`; it never creates, validates, refreshes or authenticates SIC-ID itself.

The request contract remains:

- event: `caid:sicid-login-request`
- CoreAPI: `1.0.0`
- action: `LOGIN_OR_RESUME`
- `requiresLiveSession=true`
- `callerMayProvideIdentity=false`
- `walletIsIdentity=false`

## GOLDEN PATH PRESENTATION

Landing → LIVE SIC-ID request/projection → Search → Twin/TO_VERIFY → +CASE 4-step → local-only Evidence preflight → upstream payment-state presentation → My Recovery → one Next Action → Profile.

Navigation remains HOME | SEARCH | +CASE | RECOVERY | PROFILE. CONNECT WALLET remains persistent and optional. Wallet connect remains Polygon 137, explicit-provider, `connectIsAuthentication=false`.

## CONTRACT / SAFETY

- Core 0.3.13; CoreAPI 1.0.0 consumed as request/projection contract only.
- Twin/Wallet/DAPPMAP accepted migration set remains 1.0.0 / 1.1.0 / 1.2.0.
- Knowledge Context accepted 1.0.0.
- Unknown/unsupported/ambiguous project state stays TO_VERIFY; +CASE continuation requires LIVE SIC-ID.
- Evidence/payment remain fail-closed and upstream-authoritative.
- Frontend tests reject local 50/450/500 POL literals and parallel 100/400/500 USDT Case semantics.
- No generic signing, real transaction, recovery guarantee, ROI, fake urgency or fake scarcity.

## ENGINEERING EVIDENCE

- Runtime/test head `7213b4deb44d0be806a9268bfb45944c56511056`.
- GitHub Actions CI run `33647671672`: SUCCESS.
- PASS steps: checkout, Python setup/dependencies, compile, full pytest, PHP baseline, staging PWA shell package+restore smoke, token scan.
- Added deterministic regression for LIVE SIC-ID protected routes, non-LIVE resume behavior, Search query suppression and Case submit re-check.
- Real-origin exact-head browser/PWA: NOT_TESTED.

## AG COORDINATION

Do not credit stale isolated-head browser results. The shared CHAT04 Antigravity acceptance task must be updated with the UI 2.1.0 assertions, but broad real-origin execution remains HOLD until CHAT00 publishes one exact serial Golden candidate after the global payment-authority quarantine/reconciliation. On that exact serial head Antigravity must test 390x844 + desktop, direct #search/#case without LIVE SIC-ID, CACHED/TO_VERIFY identity, successful LIVE projection, session loss during Search/Case, keyboard/focus, reduced motion, Service Worker install/offline/reconnect and cache/network safety.

## GLOBAL BLOCKERS

1. Global parallel Case-payment authority/economic collision remains release-blocking until CHAT00/CHAT02/CHAT05 quarantine/reconcile it.
2. No one exact serial Golden candidate yet.
3. Real-origin 390px/desktop/PWA install/offline/reconnect evidence absent on final serial head.
4. CHAT05 full Golden Journey and final CHAT10 package/manifest/backup/restore/rollback absent.
5. Physical wallet/sign/payment/tx/deploy remain HUMAN_GATE/NOT_TESTED.

GO_NO_GO: NO_GO
READBACK_REQUIRED: true
