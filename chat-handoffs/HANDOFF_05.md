# HANDOFF_05 — CRYPTO AID SUPER UI/UX/PWA — v1.7.0

cycle=20260902-1140  
stage=05/06 UI_UX_PWA  
owner=CHAT04_UI_UX_PWA  
status=HANDOFF_READY_NO_GO  
release_state=NO_GO_PARENT_RECERT_CI_ORIGIN_DEVICE_SERIAL_GATES  
shared_public_html_mutated=NO  
production_MASTER_mutated=NO

## Parent / sync truth

Global control-plane ownership was read before write. Current Core consumer contract is v0.3.13; current CHAT02 Evidence+Payment is v0.6.7. CHAT03 repository contracts remain Twin schema 1.0.0 / Wallet matrix 1.0.0 / DAPPMAP 1.0.0. Drive HANDOFF_04 v1.6.0 is verified as a source-preserving recertification on the older Core v0.3.12 + H03 v0.6.6 parent and is therefore stale-by-parent for final release after Core v0.3.13/H03 v0.6.7 arrived. CHAT04 consumes the stable read contract only; it does not self-certify CHAT03.

No separately discoverable canonical CHAT06/07/08/09/10 handoff documents were available in the upstream fresh sync. Knowledge MASTER V1 is present and consumed only as an upstream baseline; no public Knowledge claim is promoted by UI.

## Candidate

Repo-native isolated frontend candidate: `frontend/public_html/`.

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

Frontend contract version: `1.7.0`.

## Contract versions

- Core: `0.3.13`.
- Evidence/Payment: `0.6.7`.
- Twin: `1.0.0`.
- Wallet matrix: `1.0.0`.
- DAPPMAP: `1.0.0`.
- Knowledge baseline: `CRYPTOAID_KNOWLEDGE_MASTER_V1`, INGESTED; CHAT06 context-pack version unpinned/unavailable.
- CHAT07/08/09/10: no separate canonical handoff version discovered; no contract invented.

## Boundary proof

Static tests assert no frontend economic truth (`50 POL`, `450 POL`, `500 POL` absent), no `window.ethereum`, no `personal_sign`, no generic `eth_sendTransaction`. UI receives Case/SIC-ID/next-action/payment-intent state through projections/adapters. Payment display requires upstream `persisted=true`, `verified=true`, `expired=false`, plus upstream display amount/purpose. Transaction submission is explicitly not Case activation. Evidence is PRIVATE BY DEFAULT and only locally hashed here.

## Browser / accessibility / performance evidence

Local static contract suite: 9/9 PASS. JS/SW syntax PASS. Manifest parse PASS.

Chromium injected-document probe PASS at 390×844 and 1440×900: no horizontal overflow (`scrollWidth` exactly viewport width); CONNECT top-right and 44px tall; +CASE 58×58; exact 5-item nav; Search miss visibly TO_VERIFY; Case route visible; focus outline 3px. Reduced-motion Chromium reports motion animation `none`.

Real origin: `NOT_TESTED_RUNTIME_BLOCKED_CHROMIUM_URL_POLICY_ERR_BLOCKED_BY_ADMINISTRATOR`; therefore actual Service Worker registration, installability and offline→reconnect remain NOT_TESTED. Physical MetaMask/TokenPocket/Reown remains HUMAN_GATE.

A11Y evidence: skip link; labels/fieldset/legend; aria-live status; keyboard focus and radio focus; route heading focus; ≥44px controls; reduced-motion; 390px no overflow. Contrast on white: red ≈6.96:1, main ink ≈18.45:1, muted ≈6.06:1. Automated real-origin axe audit NOT_TESTED.

Performance/static budget: 7 runtime files, 31,357 bytes total, 0 external runtime HTTP assets. SHA-256 list: `frontend/SOURCE_MANIFEST.sha256`.

## CI / collision

GitHub CI run 33616070813 reached pytest and failed during collection on pre-existing/upstream Core contract drift: `tests/test_core_case_engine.py` imports `CaseError`, but current `core.case_engine` does not expose that name. CHAT04 did not modify CHAT01-owned Core. Repository CI therefore cannot yet certify the new CHAT04 test despite local 9/9 PASS.

Other collisions: shared legacy production public_html remains blocked/DO_NOT_DEPLOY and was not touched; existing legacy dark `web3/ui/cryptoaid-brand.css` was not treated as current white-dominant CHAT04 authority; CHAT00-owned `control/latest-state.json` remains stale and was not overwritten.

## Gate

GLOBAL_RELEASE=NO_GO.

Required next sequence: CHAT01 restores Core CI → CHAT03 re-certifies H04 on Core v0.3.13/H03 v0.6.7 → publish missing CHAT06/CHAT10 versioned contracts → rerun CI → real-origin browser/PWA/accessibility → exact serial composition in disposable staging → Stage06 release QA → HUMAN_GATE for wallet-device/real transaction/production cutover.

READBACK_REQUIRED=YES
