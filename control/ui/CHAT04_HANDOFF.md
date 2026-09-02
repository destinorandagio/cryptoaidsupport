# CHAT04 — Crypto AID UI / UX / PWA — v1.7.0

cycle=20260902-1140  
status=FRONTEND_CANDIDATE_BUILT_NO_GO  
owner=CHAT04_UI_UX_PWA  
shared_public_html_mutated=NO  
production_MASTER_mutated=NO

## SYNC INPUTS

Fresh-read global control plane in `control/latest-state.json`, `control/ownership.json`, `control/contracts.json`, current Core consumer contract v0.3.13, CHAT02 Evidence+Payment v0.6.7, repo CHAT03 Twin/Wallet/DAPPMAP handoff and Drive HANDOFF_04 v1.6.0, current Knowledge MASTER V1. No separately discoverable canonical CHAT06/07/08/09/10 handoff documents were found in the upstream fresh search; their authority is not inferred.

## CONTRACTS CONSUMED

- Core consumer contract: `0.3.13`; CHAT04 uses API/projection state only and never writes Core truth directly.
- Evidence/Payment: `0.6.7`; Evidence is private by default; payment/entitlement truth remains CHAT02-owned.
- Twin schema: `1.0.0`.
- Wallet matrix: `1.0.0`.
- DAPPMAP contract: `1.0.0`.
- Knowledge: `CRYPTOAID_KNOWLEDGE_MASTER_V1` INGESTED baseline only; no CHAT06 context-pack version was available to pin.
- UI contract: `1.7.0`.

## HANDOFF_04 VERIFICATION / COLLISION

The latest Drive HANDOFF_04 v1.6.0 was a source-preserving parent recertification on Core v0.3.12 + H03 v0.6.6. The current upstream lineage is now Core v0.3.13 + H03 v0.6.7, so that Drive H04 is stale-by-parent for final release. The repository's Twin/Wallet/DAPPMAP read contracts remain versioned 1.0.0 and are consumed read-only; CHAT04 does not re-certify or re-own CHAT03.

## UX DELTA

New isolated repo-native candidate at `frontend/public_html/`:

- beginner-first white/red/black-neutral landing with `What happened to your crypto?`;
- persistent top-right `CONNECT WALLET`, implemented as a request event only, with no provider/signing/business logic in CHAT04;
- exact bottom navigation `HOME | SEARCH | +CASE | RECOVERY | PROFILE`, central red +CASE;
- Search delegates to Twin adapter and falls back to `TO_VERIFY`; unknown projects can continue to +CASE without silent canonization;
- 4-step +CASE wizard: Situation → Project → Evidence → Review, including `I do not know`;
- Evidence UX is `PRIVATE BY DEFAULT`; local Web Crypto SHA-256 only; no file upload/storage authority added;
- My Recovery consumes Core SIC-ID/timeline/next-action projections and renders one primary Next Action; absent projection is shown as unavailable/TO_VERIFY, never invented;
- payment UX renders only a persisted + verified + unexpired upstream intent with upstream display amount/purpose; UI never calculates prices or activates a Case from a transaction;
- truth labels: LIVE/CACHED/HISTORICAL/DERIVED/TO_VERIFY/UNKNOWN;
- PWA caches explicit shell assets only and excludes `/api/`, `/evidence/`, `/payment`; private dynamic data is not cached;
- local red shield/+ SVG is a CHAT04 runtime-derived asset, not claimed as canonical brand-master authority.

## OWNERSHIP GUARDS

Frontend source contains no `window.ethereum`, `personal_sign`, generic `eth_sendTransaction`, or client-side 50/450/500 POL truth. Case create requests are adapter events with `idempotencyRequired=true`. Wallet requests carry only wallet-matrix version, Polygon chain 137 and explicit-provider-choice intent. Backend price/payment/Case/Knowledge truth remains upstream-owned.

## QA

Local contract/static tests: **9/9 PASS**. Node syntax for `app.js` and `sw.js`: PASS. Manifest JSON parse: PASS.

Real Chromium injected-document probe: PASS at 390×844 and 1440×900. At 390px: `scrollWidth=390`, body scroll width 390, CONNECT visible/top-right with 44px height, central +CASE 58×58, exact nav labels, route switch works, unknown search produces TO_VERIFY and no canonical fake. Focus outline observed 3px. Chromium with `prefers-reduced-motion: reduce` reports node and circuit animation `none`.

Real-origin Chromium probe against localhost: `NOT_TESTED_RUNTIME_BLOCKED_CHROMIUM_URL_POLICY_ERR_BLOCKED_BY_ADMINISTRATOR`. Therefore service-worker registration, install prompt and actual offline→reconnect on an origin remain NOT_TESTED.

Repository CI run `33616070813` failed before CHAT04 tests could execute because `tests/test_core_case_engine.py` imports `CaseError` from `core.case_engine`, where the symbol is currently absent. This is a CHAT01/Core collision and was not modified by CHAT04.

## A11Y

Static/injected evidence covers skip link, semantic labeled controls, `aria-live` status, keyboard-visible 3px focus, route heading focus transfer, radio-choice focus treatment, ≥44px primary controls, reduced-motion system preference plus manual reduction, no 390px horizontal overflow. Contrast spot checks on white: primary red `#b50917` ≈ 6.96:1, ink `#121417` ≈ 18.45:1, muted `#5d636c` ≈ 6.06:1. Automated axe/real-origin accessibility audit is NOT_TESTED; no matching accessibility/Playwright/PWA plugin was available and nothing was installed.

## PERFORMANCE

Self-contained runtime: 7 files, **31,357 bytes** total; CSS 9,171 B, JS 10,151 B, HTML 9,194 B, SVG 798 B, manifest 338 B, offline 736 B, SW 969 B. External runtime HTTP assets: **0**. Per-file SHA-256 is persisted in `frontend/SOURCE_MANIFEST.sha256`.

## BLOCKED

1. CHAT03 formal parent recertification/compatibility statement against Core v0.3.13 + H03 v0.6.7 is required for final serial lineage.
2. Core CI collection failure (`CaseError` export mismatch) must be fixed by CHAT01 before repository CI can certify CHAT04 tests.
3. CHAT06/07/08/09/10 canonical handoff versions were not discoverable; no contract is invented.
4. Real-origin Chromium is blocked by administrator URL policy; PWA install/offline-reconnect remain NOT_TESTED.
5. MetaMask/TokenPocket/Reown physical/origin acceptance remains HUMAN_GATE.
6. Legacy shared production `public_html` remains DO_NOT_DEPLOY and was not mutated.

## NEXT

CHAT01 fixes Core `CaseError` contract/export and restores green CI; CHAT03 recertifies H04 against current Core/H03; CHAT06 and CHAT10 publish versioned knowledge/runtime contracts; then rerun full repo CI and real-origin browser/PWA matrix. Stage05/Stage06 must serial-compose only exact approved bytes into a disposable tree before any shared `public_html` cutover.

GLOBAL_RELEASE=NO_GO
