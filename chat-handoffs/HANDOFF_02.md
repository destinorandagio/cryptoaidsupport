# CRYPTOAID — HANDOFF_02

## FROM
CHAT01 — Core / User / SIC-ID / Case / Product

## CYCLE
20260902-1210 Core delta, reconciled against HANDOFF_01 1200 and control/latest-state 0.4.1.

## STATUS
Core-owned P0 D0A is fixed and targeted Core tests are green. Repository-wide release remains **NO_GO** because downstream/global gates are still open.

## VERSIONS / HASHES
- REPO CHAT01 HANDOFF: `1.2.0`
- REPO CORE SOURCE COMMIT: `138f5154aabf2f79b296bf40dcf59e9c36a576ab`
- `core/__init__.py` blob: `f1f7b479d4cf1cf7eb34b6921b5b63b83bdcf6d1`
- `core/case_engine.py` blob: `8a5bdc73a53d1a525f7a56ed4e732d9cb9bfc700`
- SCHEMA_VERSION: `chat01-core-1` — unchanged
- API_CONTRACT_VERSION: `v1` — unchanged
- CASE_STATE_VERSION: `1.0` — unchanged
- DRIVE FACTORY CORE authority consumed: `v0.3.13`; this is a separate version namespace and was not overwritten or silently renumbered.

## SYNC INPUTS
Latest persisted HANDOFF_01 1200, control/latest-state 0.4.1, ownership/contracts, CHAT02 1.0.1 / Stage03 0.6.7, CHAT03 main 1.0.0, CHAT04 1.7.0, CHAT06 0.2.0, CHAT07 0.1.0, CHAT08 0.1.0. CHAT09 and CHAT10 current machine handoffs were not persisted at read time.

## CORE DELTA BUILT
1. Restored the stable `CaseError` public contract as an alias of `CoreError` at package and module level.
2. Fixed Case creation so the `core_cases` INSERT supplies exactly the existing 13-column schema contract rather than 14 placeholders.
3. Preserved the existing explicit state machine, optimistic `expected_version` concurrency guard, Case idempotency, tasks/timeline and authorization audit trail.
4. Preserved unknown-project behavior: search miss remains `TO_VERIFY`; CHAT01 never upgrades it to verified truth by itself.
5. Preserved authority boundaries: SIC-ID is the durable principal; wallet is a bound resource; CHAT02 remains sole Evidence/payment/entitlement authority and only emits authorization consumed by Core.

No migration, no economic rule, no MASTER write, no public_html write and no `.htaccess` mutation occurred.

## CONTRACT CHANGES
Stable consumer import is now `from core import CaseEngine, CaseError, CoreError`; direct module import of `CaseError` is also supported. No state, schema, economics or downstream truth ownership changed.

CHAT04/CHAT07/CHAT08 may consume versioned Core projections/commands only. CHAT08/Admin may not mutate Case/auth tables directly. CHAT03 Twin and CHAT06 Knowledge are read/derived inputs only.

## COLLISION DECISIONS
- **ACCEPT** — HANDOFF_01 D0A CaseError + core_cases arity repair: implemented inside CHAT01 ownership.
- **ACCEPT** — CHAT03/CHAT06 read-derived inputs: consume without authority promotion.
- **ACCEPT** — CHAT04/CHAT07/CHAT08 consumer contract exposure: read/versioned commands only.
- **REJECT** — any consumer/Admin direct write to Core Case/auth truth.
- **BLOCKED_CONFLICT** — CHAT02 evidence_records / entitlement_ledger arity defects: not patched here because CHAT02 owns Evidence/payment/entitlement.

## TESTED
Targeted isolated Core harness using the fetched repository `tests/test_core_case_engine.py` contract: **6/6 PASS**. Coverage includes new/returning user and duplicate request, SIC-ID/wallet mismatch, TO_VERIFY and resume, invalid/stale/missing-entitlement transitions, unauthorized Case, product/task/timeline behavior and optimistic concurrency.

GitHub Actions run `33618548123` after the first compatibility fix moved pytest from collection failure to execution; CHAT00 control reconciliation recorded 4 CHAT01 `core_cases` arity failures plus 3 CHAT02 arity failures. Those 4 CHAT01 failures are fixed by source commit `138f5154...`.

GitHub Actions run `33618862842` on `138f5154...`: compile step PASS; pytest step still FAIL and security/token scan SKIPPED. The connector did not expose the detailed pytest log before the run ended/cancelled, so this handoff does **not** claim repository-wide green. Current authoritative control already identifies the remaining known schema-owner defects in CHAT02.

Inherited Drive Factory Core v0.3.13 evidence remains: **373 PASS / 0 FAIL / 1 NOT_RUN**, PHP lint 19/19, Core migrations 001..004 applied twice to a fresh exact MASTER clone with integrity/FK green. This is retained evidence, not falsely relabeled as freshly executed in this runtime.

## BLOCKERS
- Repository-wide CI remains red until CHAT02 fixes its own Evidence/payment schema-engine arity defects and the security scan actually executes.
- CHAT03/CHAT04 exact consumer tuple remains uncertified.
- CHAT09/CHAT10 current machine handoffs were absent at sync time.
- Target production runtime (`pdo_sqlite`, `curl`, `fileinfo`), request-time SIC-ID authority and private Evidence infrastructure are not proven here.
- Final serial package/manifest/rollback/restore and Golden E2E are not complete.
- Real wallet/signing/payment/transaction/deploy/public upload remain HUMAN_GATE / NOT_RUN.

## CONTRACT FOR CHAT02
CHAT02 remains sole authority for Evidence bytes, payment verification and entitlement ledger. Once settlement is durably proven it may emit an authorized `ENTITLEMENT_GRANTED` result consumed by CHAT01; CHAT02 must not mutate Case state directly. Its current schema-engine arity failures must be repaired within CHAT02 ownership before a global green CI can be claimed.

## NEXT
CHAT02 repairs its own D0B failures and reruns full CI through the security scan. CHAT00 then reconciles repo/factory namespaces and source commit `138f5154...`; CHAT03/04 certify their exact tuple; CHAT10 proves target runtime. Only after that: serial disposable candidate -> exact MASTER 001..008 x2/integrity/FK/race regression -> clean package/manifest/rollback -> Golden E2E -> CHAT05 independent QA -> HUMAN go-live gate.

## GO / NO-GO
**NO_GO**
