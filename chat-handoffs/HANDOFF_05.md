# HANDOFF_05 — CRYPTO AID UI/UX/PWA — v2.0.0

cycle=20260902-1642
stage=05/06 UI_UX_PWA
owner=CHAT04_UI_UX_PWA
growth_owner=CHAT09_GROWTH_MARKETING_PARTNERSHIP
status=HANDOFF_READY_ENGINEERING_CANDIDATE_NO_GO
release_state=NO_GO_GLOBAL_AUTHORITY_SERIAL_RUNTIME_QA_GATES
branch=feat/chat04-sicid-login-freshmain-1642
parent_main_observed=46a8e76ac4b6b21284b0b258ed111f72c039f7bd
source_head=THIS_COMMIT
shared_production_public_html_mutated=NO
production_MASTER_mutated=NO

## P0 CLOSED IN THIS CYCLE

The public shell previously talked about SIC-ID but exposed no explicit sign-in/resume request before Search.
UI v2.0.0 now makes SIC-ID the first beginner-facing step and emits only a fail-closed request event:

- event: `caid:sicid-login-request`
- CoreAPI contract requested: `1.0.0`
- action: `LOGIN_OR_RESUME`
- `requiresLiveSession=true`
- `callerMayProvideIdentity=false`
- `walletIsIdentity=false`

CHAT04 does not create, validate or store a session. If no trusted Core runtime adapter consumes the request, the UI says that no session was created. Identity remains upstream CHAT01 truth.

## GOLDEN PATH PRESENTATION

Landing → explicit SIC-ID request → Search → Twin/TO_VERIFY → +CASE 4-step → local-only Evidence preflight → upstream payment-state presentation → My Recovery → one Next Action → Profile.

Navigation remains HOME | SEARCH | +CASE | RECOVERY | PROFILE. CONNECT WALLET remains persistent and optional. Wallet connect remains Polygon 137, explicit-provider, `connectIsAuthentication=false`.

## CONTRACT / SAFETY

- Core 0.3.13; CoreAPI 1.0.0 consumed as request/projection contract only.
- Twin/Wallet/DAPPMAP accepted migration set remains 1.0.0 / 1.1.0 / 1.2.0.
- Knowledge Context accepted 1.0.0.
- Unknown/unsupported/ambiguous project state stays TO_VERIFY and may continue to +CASE.
- Evidence/payment remain fail-closed and upstream-authoritative.
- Frontend tests explicitly reject local 50/450/500 POL literals and parallel 100/400/500 USDT Case semantics.
- No generic signing, real transaction, recovery guarantee, ROI, fake urgency or fake scarcity.

## STATIC EVIDENCE BEFORE PUSH

- `node --check` app.js: PASS.
- Python compile of focused frontend contract test: PASS.
- Focus assertions: SIC-ID CTA precedes hero Search; request event/live-session/caller-identity/wallet-identity flags present; Twin 1.2 and Polygon137 behavior retained: PASS.
- Real-origin exact-head browser/PWA: NOT_TESTED.

## REPOSITORY CI

- Logic/source head `b5817d50e90bd93f5138397c93c564f9a3c47d0e`: CI run `33645275891` SUCCESS.
- `pytest -q`: 88 passed.
- PHP baseline: PASS.
- Staging PWA shell package + restore smoke: PASS.
- Telegram token scan: PASS.
- Metadata-only handoff update requires its own PR CI rerun; runtime files are unchanged by that metadata commit.

## AG COORDINATION

The existing CHAT04 17-assertion Antigravity browser task is NOT promoted to this isolated UI source head. Global HANDOFF_01 currently holds Golden runtime on QA05-P0-016 and absence of one exact serial candidate. When CHAT00 publishes the serial Golden head, the AG browser plan must add explicit SIC-ID request assertions and execute on that exact head only.

## GLOBAL BLOCKERS

1. QA05-P0-016 parallel Case-payment authority/economic collision remains release-blocking.
2. No one exact serial Golden candidate yet.
3. Real-origin 390px/desktop/PWA install/offline/reconnect evidence absent on final serial head.
4. CHAT05 full Golden Journey and final CHAT10 package/manifest/backup/restore/rollback absent.
5. Physical wallet/sign/payment/tx/deploy remain HUMAN_GATE/NOT_TESTED.

GO_NO_GO: NO_GO
READBACK_REQUIRED: true
