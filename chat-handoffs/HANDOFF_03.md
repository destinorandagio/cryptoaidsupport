# CRYPTOAID — HANDOFF_03

## FROM
CHAT02 — Evidence / Payment / Entitlement / Treasury

## STATUS
Implementation committed on `main`; production remains **NO_GO**.

## VERSIONS
- EVIDENCE_VERSION: 1.0
- PAYMENT_VERSION: 1.0
- ENTITLEMENT_VERSION: 1.0
- TREASURY_CONFIG_VERSION: 1.0

## BUILT
- Private-by-default evidence lifecycle with MIME/size validation, SHA-256, Case/consent/authorization binding, immutable versions and supersession lineage.
- Payment intent and explicit state machine for Polygon 137.
- Verification contract checks chain/from/to/value/asset/receipt/Case/entitlement/tx uniqueness/finality/provider agreement.
- Ambiguity routes to MANUAL_REVIEW.
- Append-only entitlement ledger; settlement is transactionally idempotent.
- Versioned treasury configuration, max 100 treasury IDs, multiple ACTIVE entries supported; canonical current treasury seeded as `0x3C320B3a0917fF44BF6551CDdee44402AFcF250C` for POL.
- No real payment initiation.

## TESTS
Adversarial pytest coverage committed for MIME spoof/mismatch, oversized/unauthorized evidence, wrong chain, provider disagreement, duplicate tx across Cases, duplicate settlement, treasury version history. CI confirmation is still required for the current HEAD.

## DEPENDENCIES / BLOCKERS
- Reconcile CHAT01 Case activation/state contract before end-to-end integration.
- Consume CHAT08 authorized admin/config proposal contract when published.
- Consume CHAT10 provider/runtime configuration when published; secrets must remain runtime-only.
- CHAT05 must independently adversarial-test release behavior.

## NEXT
CHAT03 may consume only the documented payment/evidence outputs and must not create payment, entitlement, Evidence, Case, Twin, or Knowledge parallel authorities.
