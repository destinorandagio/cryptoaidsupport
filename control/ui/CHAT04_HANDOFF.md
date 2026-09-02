# CHAT04 — Crypto AID UI / UX / PWA — v1.7.0

cycle=20260902-1140  
status=FRONTEND_CANDIDATE_BUILT_NO_GO_VERSION_SYNC_PENDING  
owner=CHAT04_UI_UX_PWA  
shared_public_html_mutated=NO  
production_MASTER_mutated=NO

## SYNC_INPUTS

Fresh-read global control plane (`latest-state`, ownership, contracts), current Core consumer contract v0.3.13, CHAT02 Evidence+Payment v0.6.7, current-main CHAT03 Twin/Wallet/DAPPMAP 1.0.0 contract, Drive HANDOFF_04 v1.6.0, current Knowledge MASTER V1, and the later CHAT03 20260902-1130 branch handoff on PR #3. No separately discoverable canonical CHAT06/07/08/09/10 handoff documents were found; their authority is not inferred.

## CONTRACT_VERSIONS

- Core: `0.3.13`; CHAT04 consumes API/projection state only and never writes Core truth directly.
- Evidence/Payment: `0.6.7`; Evidence is private by default; payment/entitlement truth remains CHAT02-owned.
- Current-main Twin schema / Wallet matrix / DAPPMAP: `1.0.0`.
- CHAT03 PR #3 proposed Twin / Wallet matrix / DAPPMAP: `1.1.0` — **not silently consumed before coordinated version sync/merge**.
- Knowledge: `CRYPTOAID_KNOWLEDGE_MASTER_V1` INGESTED baseline; no CHAT06 context-pack version available to pin.
- UI: `1.7.0`.

## HANDOFF_04 / LATE SYNC

The older Drive HANDOFF_04 v1.6.0 was a source-preserving recertification on Core v0.3.12 + H03 v0.6.6 and became stale-by-parent after Core v0.3.13/H03 v0.6.7. During this CHAT04 cycle, CHAT03 published a newer 20260902-1130 handoff on `feat/chat03-twin-wallet-sync-v1-1` / PR #3, read back on GitHub and Drive. It closes the Core/H03 parent drift and proposes Twin/Wallet/DAPPMAP `1.1.0`, while explicitly detecting that this CHAT04 frontend currently pins `1.0.0` and requiring `VERSION_SYNC_REQUIRED_BEFORE_MERGE`. CHAT04 therefore remains fail-closed on current-main `1.0.0`; it does not self-certify or silently consume an unmerged upstream contract.

## UX_DELTA

New isolated repo-native candidate at `frontend/public_html/`:

- beginner-first white/red/black-neutral landing with `What happened to your crypto?`;
- persistent top-right `CONNECT WALLET`, implemented as a request event only, with no provider/signing/business logic in CHAT04;
- exact bottom navigation `HOME | SEARCH | +CASE | RECOVERY | PROFILE`, central red +CASE;
- Search delegates to Twin adapter and falls back to `TO_VERIFY`; unknown projects can continue to +CASE without silent canonization;
- 4-step +CASE wizard: Situation → Project → Evidence → Review, including `I do not know`;
- Evidence UX is `PRIVATE BY DEFAULT`; local Web Crypto SHA-256 only; no upload/storage authority added;
- My Recovery consumes Core SIC-ID/timeline/next-action projections and renders one primary Next Action; absent projection is unavailable/TO_VERIFY, never invented;
- payment UX renders only a persisted + verified + unexpired upstream intent with upstream display amount/purpose; UI never calculates prices or activates a Case from a transaction;
- truth labels: LIVE/CACHED/HISTORICAL/DERIVED/TO_VERIFY/UNKNOWN;
- PWA caches explicit shell assets only and excludes `/api/`, `/evidence/`, `/payment`; private dynamic data is not cached;
- local red shield/+ SVG is a CHAT04 runtime-derived asset, not claimed as canonical brand-master authority.

## OWNERSHIP_GUARDS

Frontend contains no `window.ethereum`, `personal_sign`, generic `eth_sendTransaction`, or client-side 50/450/500 POL truth. Case create requests are adapter events with `idempotencyRequired=true`. Wallet requests carry only wallet-matrix version, Polygon chain 137 and explicit-provider-choice intent. Backend price/payment/Case/Knowledge truth remains upstream-owned.

## BROWSER_STATUS

Local contract/static tests: **9/9 PASS**. Node syntax for `app.js` and `sw.js`: PASS. Manifest JSON parse: PASS.

Real Chromium injected-document probe: PASS at 390×844 and 1440×900. At 390px: `scrollWidth=390`, body scroll width 390, CONNECT visible/top-right with 44px height, central +CASE 58×58, exact nav labels, route switch works, unknown search produces TO_VERIFY and no canonical fake. Focus outline observed 3px. Chromium with `prefers-reduced-motion: reduce` reports node and circuit animation `none`.

Real-origin Chromium probe against localhost: `NOT_TESTED_RUNTIME_BLOCKED_CHROMIUM_URL_POLICY_ERR_BLOCKED_BY_ADMINISTRATOR`. Service-worker registration, install prompt and actual offline→reconnect on an origin remain NOT_TESTED.

Repository CI run `33616070813` failed before CHAT04 tests could execute because `tests/test_core_case_engine.py` imports `CaseError` from `core.case_engine`, where the symbol is currently absent. CHAT03 PR CI is blocked by the same CHAT01/Core regression. CHAT04 did not modify Core.

## A11Y

Static/injected evidence covers skip link, semantic labeled controls, `aria-live` status, keyboard-visible 3px focus, route heading focus transfer, radio-choice focus treatment, ≥44px primary controls, reduced-motion system preference plus manual reduction, no 390px horizontal overflow. Contrast spot checks on white: primary red `#b50917` ≈ 6.96:1, ink `#121417` ≈ 18.45:1, muted `#5d636c` ≈ 6.06:1. Automated axe/real-origin accessibility audit is NOT_TESTED; plugin search returned no matching accessibility/Playwright/PWA capability and nothing was installed.

## PERF

Self-contained runtime: 7 files, **31,357 bytes** total; CSS 9,171 B, JS 10,151 B, HTML 9,194 B, SVG 798 B, manifest 338 B, offline 736 B, SW 969 B. External runtime HTTP assets: **0**. Per-file SHA-256 is persisted in `frontend/SOURCE_MANIFEST.sha256`.

## COLLISIONS

- CHAT03 PR #3 proposes Twin/Wallet/DAPPMAP `1.1.0` while current-main CHAT04 pins `1.0.0`; version sync is an explicit merge/release gate.
- CHAT00-owned `control/latest-state.json` is stale versus newer owner handoffs but remains CHAT00-owned and was not overwritten.
- legacy `web3/ui/cryptoaid-brand.css` is dark-dominant and was not reused as current white-dominant CHAT04 authority.
- shared production `public_html` remains legacy DO_NOT_DEPLOY and was not mutated.

## FIXED

- Replaced speculative/direct wallet behavior with an upstream wallet request adapter.
- Added fail-closed Search/TO_VERIFY behavior and beginner `I do not know` Case route.
- Added PRIVATE BY DEFAULT local Evidence hashing without upload authority.
- Added fail-closed upstream payment-intent presentation and explicit `tx != Case active` UX.
- Replaced broad PWA caching with explicit shell-only caching and dynamic/private exclusions.
- Made 390px, focus and reduced-motion requirements executable/static-testable.
- Reconciled late CHAT03 1.1.0 proposal without silently changing the active main consumer contract.

## BLOCKED

1. Coordinated CHAT03/CHAT04 version sync is required before PR #3 merge or final composition.
2. Core CI collection failure (`CaseError` export mismatch) must be fixed by CHAT01 before repository CI can certify CHAT04 or CHAT03.
3. CHAT06/07/08/09/10 canonical handoff versions were not discoverable; no contract is invented.
4. Real-origin Chromium is blocked by administrator URL policy; PWA install/offline-reconnect remain NOT_TESTED.
5. MetaMask/TokenPocket/Reown physical/origin acceptance remains HUMAN_GATE.
6. Legacy shared production `public_html` remains DO_NOT_DEPLOY and was not mutated.

## NEXT

CHAT01 restores Core CI → coordinated CHAT03/CHAT04 1.1.0 version sync/compatibility gate → merge/re-read CHAT03 authority → publish missing CHAT06/CHAT10 contracts → rerun full repo CI → real-origin browser/PWA/accessibility → exact serial composition in disposable staging → Stage06 release QA → HUMAN_GATE for wallet-device/real transaction/production cutover.

GLOBAL_RELEASE=NO_GO  
READBACK_REQUIRED=YES
