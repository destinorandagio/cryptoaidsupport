# HANDOFF_05 — CRYPTO AID UI/UX/PWA — v2.1.5

cycle=20260902-2140
stage=05/06 UI_UX_PWA
owner=CHAT04_UI_UX_PWA
growth_owner=CHAT09_GROWTH_MARKETING_PARTNERSHIP
status=HANDOFF_READY_ENGINEERING_CANDIDATE_NO_GO
release_state=NO_GO_SERIAL_REFRESH_AG_CHAT05_CHAT10
branch=feat/chat04-sicid-login-freshmain-1642
serial_pr48_observed=15a7fdc5822ba1970f72e37e9318284f10b11dcf
runtime_logic_test_head=77216b56b683bff55ac72334a019ef98d696e8cb
ui_version=2.1.1
pwa_shell_version=2.1.4
shared_production_public_html_mutated=NO
production_MASTER_mutated=NO

## P0 CLOSED — QUERY-STRING / OFFLINE ATTRIBUTION CONTAINMENT

The exact serial PR48 correctly preserved CHAT04 PWA 2.1.3 cache namespace and current-cache isolation, but fresh release audit found a remaining PWA reliability blocker. Shell detection compared only URL pathname while `Cache.match(request)` remained query-sensitive by default. A warmed shell URL such as `/?utm_source=telegram` or `/index.html?utm_campaign=mvp` could therefore be classified as a shell request, miss the query-less precache key, call network fetch, and return from the shell branch before the generic navigation offline fallback. Offline reload could fail specifically on query-bearing landing/attribution URLs.

PWA 2.1.4 fixes this owner-safe without adding tracking runtime:

- shell requests are classified only for the Service Worker scope origin;
- a matching shell pathname is resolved to its canonical precached shell URL;
- lookup occurs only inside the current `caid-shell-v2.1.4` cache using that canonical key;
- the browser-visible URL and query string are not rewritten or stripped;
- obsolete-cache deletion remains restricted to the `caid-shell-v` namespace;
- `skipWaiting()` and `clients.claim()` remain;
- `/api/`, `/evidence/`, `/payment` remain excluded from authoritative Cache Storage.

## GOLDEN PATH PRESENTATION

Landing → LIVE SIC-ID request/projection → Search → Twin/TO_VERIFY → +CASE 4-step → local-only Evidence preflight → upstream payment-state presentation → My Recovery → one Next Action → Profile.

Navigation remains HOME | SEARCH | +CASE | RECOVERY | PROFILE. CONNECT WALLET remains persistent and optional. Search/+CASE/Recovery/Profile continue to require LIVE SIC-ID. Recovery/Profile private projection remains scrubbed fail-closed on identity loss. No frontend prices/payment verification/Case truth/Knowledge authority were introduced.

## ENGINEERING EVIDENCE

- runtime/test head: `77216b56b683bff55ac72334a019ef98d696e8cb`;
- local `node --check sw.js` PASS;
- deterministic canonicalization simulation PASS for `/?utm_source=telegram`, `/index.html?utm_campaign=launch`, `/assets/app.js?v=214`;
- cross-origin same-path URL is not classified as CryptoAID shell;
- GitHub Actions CI `33674976135` SUCCESS: checkout, Python setup/deps, compile, full pytest, PHP baseline, staging PWA shell package+restore smoke and token scan PASS;
- Release Candidate Package `33674976134` SUCCESS: exact checkout, PWA validation/package/restore-check, release metadata and verified candidate artifact PASS; production remains human-gated.

## ACCESSIBILITY / PERFORMANCE

No HTML/CSS/app.js redesign or new framework, remote asset, tracker or marketing SDK was introduced in this delta. Existing skip-link, focus-visible, route-heading focus, 44px touch target, 390px overflow guard, aria-live and reduced-motion contracts remain unchanged. Real-browser keyboard/focus and Lighthouse/performance remain factual Antigravity gates.

## AG COORDINATION

Do not credit PR48 or isolated PR17 as final release evidence after this owner delta. CHAT00 must first publish one refreshed exact serial Golden SHA containing PWA 2.1.4 (`77216b5...`) or byte-equivalent. Antigravity must then execute assertions 1-28 on that same exact SHA.

Assertion 28 — QUERYSTRING/OFFLINE ATTRIBUTION: warm the exact candidate online; navigate to a same-origin URL such as `/?utm_source=telegram&utm_campaign=mvp48h` and separately `/index.html?utm_source=telegram`; prove the shell renders and browser query is retained. Force offline and reload; prove the current shell/offline experience remains usable, the visible query is not mutated, the current `caid-shell-v2.1.4` supplies the canonical shell content, and `/api/`, `/evidence/`, `/payment` are absent from authoritative cache. Probe `/assets/app.js?v=214` and prove it resolves to the genuine current cached app.js, not stale/unrelated content. Repeat at 390x844 and 1440x900. Persist exact SHA, OS/browser/version, serve command/URL/timestamp, SW lifecycle/controller, before/after cache keys, network/console, response/cache source evidence, visible query evidence and screenshot filenames + SHA-256.

Assertions 1-27 remain mandatory. No real signing/payment/transaction/deploy is authorized.

## GROWTH

CHAT09 remains v0.4.1 and feature-frozen. No campaign, attribution SDK/runtime, tracker, pricing/payment copy or cosmetic expansion was added. HELP_FIRST, EVIDENCE_FIRST, VALUE_BEFORE_CTA, NO_PURCHASE_NEEDED, OFFICIAL_FREE_PATH_FIRST, no fake urgency/scarcity/testimonials, no recovery guarantee and no ROI remain mandatory.

## GLOBAL BLOCKERS

1. CHAT00 must refresh the exact serial Golden candidate with PWA 2.1.4 or byte-equivalent.
2. Antigravity real-origin assertions 1-28 are absent on that refreshed exact serial SHA.
3. CHAT05 full Golden Journey/privacy/security acceptance is pending.
4. CHAT10 final package/manifest/backup/restore/rollback is pending.
5. Physical wallet/sign/payment/tx/deploy remain HUMAN_GATE/NOT_TESTED.

GO_NO_GO: NO_GO_SERIAL_REFRESH_AG_CHAT05_CHAT10
READBACK_REQUIRED: true
