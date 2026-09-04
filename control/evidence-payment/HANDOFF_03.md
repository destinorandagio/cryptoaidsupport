# HANDOFF_03 — CHAT02 EVIDENCE / PAYMENT / ENTITLEMENT — v1.5.0-candidate

PUBLISHED: 2026-09-02 20:30 Europe/Rome
STATE: `OWNER_CODE_CI_GREEN_RUNTIME_QA_PENDING_NO_GO`
PR: #46 DRAFT / REVIEW_ONLY
SERIAL_PARENT: PR44 `df61027abea76e7dced3d5f249a9a610a7ed1b03`
CODE_GREEN_HEAD: `114510999c84c887efec30818aa4d8c021f79175`
CODE_GREEN_CI: `33667291726 SUCCESS`

## AUTHORITY CONTRACT
CHAT02 remains the sole writer/authority for Evidence lifecycle, payment verification, settlement certificate/truth, credit and entitlement ledger. Consumers may consume states only. No parallel verifier/ledger/evidence authority is accepted.

## FROZEN ENGINEERING ECONOMICS
Polygon 137. Activation 50 POL once -> credit50. First Case nominal500/payable450 after credit reserve/consume. Subsequent Cases 500. No real payment/sign/tx/deploy in this candidate.

## EVIDENCE GOLDEN CONTRACT
`UPLOAD -> QUARANTINE -> VALIDATE -> SHA256 -> METADATA -> CASE_BINDING -> AUTHORIZATION -> AVAILABLE`.
Private bytes remain outside public webroot. Path/symlink containment and single-successor append-only lineage remain inherited from accepted CHAT02 contracts.

New Evidence Authorization Contract 1.0:
- exact authorizing values: `ALLOW`, `OWNER` only;
- exact, case-sensitive comparison;
- `REVOKED`, `PENDING`, `DENY`, `FALSE`, `0`, padded/lowercase lookalikes, blank and non-string values fail `UNAUTHORIZED` before Evidence bytes/rows;
- blank/non-string consent fails `CONSENT_REQUIRED` before Evidence bytes/rows;
- package canonicalization prevents direct-import bypass of the authorization guard.

Test-first evidence:
- RED head `00a790e2bc4e112b5c007e51bb8620ff4784e2bd`, CI `33666680703 FAILURE` proving the original fail-open gap;
- intermediate strict-ALLOW-only integration CI `33666939576 FAILURE` exposing existing valid `OWNER` Golden semantics;
- final code head `114510999c84c887efec30818aa4d8c021f79175`, CI `33667291726 SUCCESS`.

## PAYMENT GOLDEN CONTRACT — UNCHANGED
Intent persistence/expiry, tx uniqueness, replay rejection, wrong chain/from/to/value/receipt fail-closed, >=2 independent provider agreement, deterministic finalized-boundary, settlement certificate, credit/entitlement idempotency and `TX_SUBMITTED/TX_OBSERVED != SETTLED != CASE_ACTIVE` remain unchanged.

## FILE SHA-256
`authorization_engine.py` = `f72d515a67f0a5d7615c5c5e420cb14b0de485b37ee7330cbaf0b36a59965452`
`__init__.py` = `daccb75a8a77cdaf4b699f3777c67764cf4c69624815b74fdaa1077fed7aee2e`
`test_evidence_authorization_security.py` = `44106aaabe3d2e397aa8fc00677538362b237a29517438b1c09c1003875cc380`

## MANUAL REVIEW / FAIL CLOSED
Provider identity or receipt/block/finality disagreement, wrong payment tuple, duplicate/replay ambiguity, Evidence consent/authorization/privacy/scanner ambiguity and any unrecognized authorization state remain fail-closed/manual-review as applicable.

## BLOCKERS
AG local exact-head evidence; CHAT05 independent acceptance of this new contract on the same serial head; production private Evidence runtime; independent Polygon production authority plumbing; browser/PWA Golden; final serial package/rollback; HUMAN_GATE.

GO_NO_GO: `NO_GO`.
