# CRYPTOAID — HANDOFF_02

## FROM
CHAT01 — Core / User / SIC-ID / Case / Product

## STATUS
Core authority materialized on `main`. Production remains **NO_GO**.

## VERSIONS
- VERSION: 1.0
- SCHEMA_VERSION: chat01-core-1
- API_CONTRACT_VERSION: v1
- CASE_STATE_VERSION: 1.0

## BUILT
USER → SIC-ID → WALLET BINDING → CASE → TRIAGE → PRODUCT → TASK/NEXT ACTION primitives → RESULT workflow states.

Case state is explicit and every transition records Case, actor, previous/new state, reason, timestamp, request ID, idempotency key, authorization, audit event and optimistic Case version.

SEARCH MISS produces `TO_VERIFY` and does not block Case creation. CHAT01 never upgrades TO_VERIFY to verified truth.

Product architecture accepts FREE, ACTIVATION, ONE_SHOT, CASE, MEMBERSHIP, RECURRING, UPGRADE, DOWNGRADE, RENEWAL and CANCELLATION, but contains no invented commercial offers or duplicated frontend prices.

Activation into `ACTIVE` requires an authorization contract from the external entitlement/payment authority (`ENTITLEMENT_GRANTED`) or an explicitly authorized FREE product path. CHAT01 does not verify payment and does not write entitlement ledger truth.

## TEST COVERAGE COMMITTED
New/returning user, duplicate request, wallet mismatch, SIC-ID mismatch, unauthorized Case, Case resume, TO_VERIFY, invalid transition, stale/concurrent transition, missing entitlement, product/task/timeline behavior.

CI confirmation for the current HEAD remains pending.

## BLOCKERS
- HANDOFF_01 was not found in repository at execution time.
- CHAT06/08/10 handoffs not yet available for reconciliation.
- HTTP/API transport/auth-session endpoints still need contract-first exposure and malformed-request tests.
- CHAT02 integration and independent CHAT05 QA are required before release.

## CONTRACT FOR CHAT02
CHAT02 remains sole authority for Evidence bytes, payment verification and entitlement ledger. When settlement is durably proven, it may emit an authorized entitlement result consumed by CHAT01 to transition the Case; it must not mutate Case state directly.

## NEXT
Reconcile CHAT01 + CHAT02 contracts, expose versioned API surface, run CI/adversarial suite, then continue toward CHAT03/CHAT05 integration. No autonomous GO-LIVE.
