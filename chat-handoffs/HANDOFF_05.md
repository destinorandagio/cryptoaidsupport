# HANDOFF_05 — CRYPTO AID SUPER UI/UX/PWA — v1.7.0

cycle=20260902-1140  
stage=05/06 UI_UX_PWA  
owner=CHAT04_UI_UX_PWA  
status=HANDOFF_READY_NO_GO_VERSION_SYNC_PENDING  
release_state=NO_GO_CHAT03_VERSION_SYNC_CI_ORIGIN_DEVICE_SERIAL_GATES  
shared_public_html_mutated=NO  
production_MASTER_mutated=NO

## SYNC_INPUTS

Global control-plane ownership/contracts fresh-read. Current Core consumer contract is v0.3.13; current CHAT02 Evidence+Payment is v0.6.7. Current-main CHAT03 Twin/Wallet/DAPPMAP contracts are 1.0.0. Knowledge MASTER V1 is present and consumed only as upstream baseline. No separately discoverable canonical CHAT06/07/08/09/10 handoff documents were available; no authority was invented.

A late concurrent CHAT03 handoff dated 20260902-1130 was then fresh-read from `feat/chat03-twin-wallet-sync-v1-1` / PR #3. It is readback-verified on GitHub/Drive, closes its Core v0.3.13/H03 v0.6.7 parent drift and proposes Twin/Wallet/DAPPMAP `1.1.0`. It explicitly detects this CHAT04 consumer pin at `1.0.0` and requires `VERSION_SYNC_REQUIRED_BEFORE_MERGE`. CHAT04 therefore does not silently consume the unmerged `1.1.0` contract; current main remains fail-closed on 1.0.0 until coordinated version sync/merge.

## CONTRACT_VERSIONS

- Core: `0.3.13`.
- Evidence/Payment: `0.6.7`.
- Current-main Twin / Wallet matrix / DAPPMAP: `1.0.0`.
- CHAT03 PR #3 proposed Twin / Wallet matrix / DAPPMAP: `1.1.0`, pending coordinated sync.
- Knowledge baseline: `CRYPTOAID_KNOWLEDGE_MASTER_V1`, INGESTED; CHAT06 context-pack version unpinned/unavailable.
- UI: `1.7.0`.

## UX_DELTA

Repo-native isolated candidate: `frontend/public_html/`.

Affected routes/components:

- `#home`: white-dominant 9:16-friendly beginner landing, search-first CTA, safety principles, derived circuit/node/block motion.
- header: persistent `CONNECT WALLET`, request adapter only.
- `#search`: Twin adapter boundary, no-match => TO_VERIFY + +CASE continuation.
- `#case`: four-step Situation/Project/Evidence/Review wizard; UNKNOWN beginner path; local SHA-256 Evidence preflight; no upload authority.
- `#recovery`: Core-projected My Recovery, one primary Next Action, timeline and fail-closed payment-state presentation.
- `#profile`: SIC-ID projection only and motion control.
- bottom nav: exact `HOME | SEARCH | +CASE | RECOVERY | PROFILE`, red 58px central +CASE.
- `sw.js`: explicit shell-only caching; API/Evidence/payment paths excluded.
- `offline.html`: reconnect/resume guidance with no private Case/payment cache.

## OWNERSHIP / SAFETY PROOF

Static tests assert no frontend economic truth (`50 POL`, `450 POL`, `500 POL` absent), no `window.ethereum`, no `personal_sign`, no generic `eth_sendTransaction`. UI receives Case/SIC-ID/next-action/payment-intent state through projections/adapters. Payment display requires upstream `persisted=true`, `verified=true`, `expired=false`, plus upstream display amount/purpose. Transaction submission is explicitly not Case activation. Evidence is PRIVATE BY DEFAULT and only locally hashed here.

## BROWSER_STATUS

Local static contract suite: 9/9 PASS. JS/SW syntax PASS. Manifest parse PASS.

Chromium injected-document probe PASS at 390×844 and 1440×900: no horizontal overflow (`scrollWidth` exactly viewport width); CONNECT top-right and 44px tall; +CASE 58×58; exact 5-item nav; Search miss visibly TO_VERIFY; Case route visible; focus outline 3px. Reduced-motion Chromium reports motion animation `none`.

Real origin: `NOT_TESTED_RUNTIME_BLOCKED_CHROMIUM_URL_POLICY_ERR_BLOCKED_BY_ADMINISTRATOR`; actual Service Worker registration, installability and offline→reconnect remain NOT_TESTED. Physical MetaMask/TokenPocket/Reown remains HUMAN_GATE.

Repository CI run `33616070813` failed before CHAT04 tests could execute because `tests/test_core_case_engine.py` imports `CaseError`, but current `core.case_engine` does not expose it. CHAT03 PR CI fails on the same CHAT01/Core collection regression. CHAT04 did not modify Core.

## A11Y

Skip link; labels/fieldset/legend; aria-live status; keyboard focus and radio focus; route heading focus; ≥44px controls; reduced-motion; 390px no overflow. Contrast on white: red ≈6.96:1, main ink ≈18.45:1, muted ≈6.06:1. Automated real-origin axe audit NOT_TESTED. Plugin catalog returned no matching accessibility/Playwright/PWA plugin; no installation performed.

## PERF

Self-contained runtime: 7 files / 31,357 bytes total; CSS 9,171 B; JS 10,151 B; HTML 9,194 B; SVG 798 B; manifest 338 B; offline 736 B; SW 969 B. External runtime HTTP assets: 0. SHA-256 list is persisted in `frontend/SOURCE_MANIFEST.sha256`.

## COLLISIONS

- CHAT03 PR #3 `1.1.0` proposal vs current-main CHAT04 `1.0.0` consumer pin: explicit version-sync gate.
- CHAT00-owned `control/latest-state.json` is stale versus newer owner handoffs; not overwritten by CHAT04.
- legacy dark `web3/ui/cryptoaid-brand.css` is not used as current white-dominant UI authority.
- shared legacy production `public_html` remains DO_NOT_DEPLOY and untouched.

## FIXED

Frontend now has beginner-first progressive disclosure, upstream-only wallet and payment adapters, fail-closed TO_VERIFY Search, UNKNOWN Case choice, private local Evidence hash UX, one primary Next Action, dynamic truth labels, safe shell-only PWA caching, exact mobile nav, 390px overflow guard, focus-visible and reduced-motion. Late CHAT03 version drift is explicitly recorded instead of silently assumed compatible.

## BLOCKED

1. Coordinated CHAT03/CHAT04 contract version sync before PR #3 merge/final composition.
2. CHAT01 Core `CaseError` public export mismatch keeps repository CI red.
3. CHAT06/07/08/09/10 versioned canonical handoffs not discovered.
4. Real-origin Chromium blocked by administrator URL policy; PWA origin tests remain NOT_TESTED.
5. MetaMask/TokenPocket/Reown physical/origin tests remain HUMAN_GATE.
6. No serial cutover to shared production `public_html`.

## NEXT

CHAT01 restores Core CI → CHAT03/CHAT04 complete 1.1.0 contract sync/compatibility gate → merge and fresh-read CHAT03 authority → publish missing CHAT06/CHAT10 versioned contracts → rerun CI → real-origin browser/PWA/accessibility → exact serial disposable composition → Stage06 release QA → HUMAN_GATE → production cutover only after GO.

GLOBAL_RELEASE=NO_GO  
READBACK_REQUIRED=YES
