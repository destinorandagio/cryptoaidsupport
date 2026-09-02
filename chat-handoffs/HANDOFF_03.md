# CRYPTOAID — HANDOFF_03

## FROM
CHAT02 — Evidence / Payment / Entitlement / Treasury

## CYCLE
20260902-1241 — 48h MVP kickoff — settlement certificate candidate.

## STATUS
`CANDIDATE_GREEN_PENDING_ANTIGRAVITY_AND_CHAT05` — production remains **NO_GO**.

## VERSIONS / SOURCE
- PR: `#4` — `feat/chat02-settlement-certificate-mvp`
- candidate head at first CI: `1000e991af793264eb37dad094f77733c37534f9`
- `evidence_payment/engine.py` candidate blob: `9dbc6c0ed03bd2cd94efb78b7a6cd157b548c3bf`
- `tests/test_evidence_payment.py` blob: `628d0b81d897d71726a7121927adc3edb717ecc0`
- Evidence: `1.0`
- Payment: `1.1-candidate`
- Entitlement: `1.1-candidate`
- Treasury config: `1.0`
- Factory Stage03 `0.6.7` remains a separate unchanged namespace.

## SYNC_INPUTS
Fresh-read HANDOFF_02 repo v1.2.1 / Core source `138f5154...`, latest CHAT02 v1.1.x, shared ownership ledger and CHAT00 Antigravity Execution Contract v1.0.0. Prior CHAT02 lock was released and no AG_ACTIVE collision was found on the two branch files at kickoff. MASTER, `public_html`, `.htaccess`, economics and treasury truth were not mutated.

## P0 CLOSED AT ENGINEERING-CANDIDATE LEVEL
The Golden Path needs a durable settlement certificate between finality verification and entitlement grant. The prior repo engine granted entitlement on settlement but did not persist a dedicated certificate, and provider agreement did not require distinct provider identities nor exact agreement with the primary observation tuple.

Candidate PR #4 adds:
- additive `settlement_certificates` table;
- certificate binding for intent, Case, entitlement, tx, chain 137, asset, value, treasury, provider IDs/fingerprint and observation SHA-256;
- entitlement lineage containing `settlement_certificate_id`;
- provider quorum requiring at least two distinct non-empty `provider_id` values;
- exact provider agreement with primary `tx_hash` / `block_hash` / `receipt_status`;
- duplicate tx uniqueness races fail closed to `MANUAL_REVIEW`;
- idempotent settlement replay returns the same certificate and never duplicates entitlement.

## ADVERSARIAL TEST DELTA
Candidate tests cover duplicate provider identity, providers agreeing on a wrong tx, insufficient finality, durable certificate/readback, one-certificate/one-entitlement replay, duplicate tx across Cases, wrong chain/provider disagreement, Evidence MIME/size/auth guards and treasury version history.

## CI EVIDENCE
GitHub Actions run `33621006419` / CI #223 on exact head `1000e991...` completed **SUCCESS**. Dependency setup, compile step, `pytest -q` and configured Telegram-token scan all passed. This proves the repository suite green on that candidate snapshot; it does not replace local disposable SQLite/runtime evidence.

## ANTIGRAVITY ACCEPTANCE PACK
Drive task: `1rQuudYg4ApBz6TU5DqAaYiy3FRegRY0H-RlHZSpoSzo`.
Required local proof: evidence/payment compile, targeted/full pytest, disposable SQLite schema + integrity/FK, synthetic settlement/replay and negative duplicate-provider / wrong-provider-tuple / insufficient-finality / duplicate-tx cases. No real payment/sign/tx/deploy.

## PERSISTENCE
- CHAT02 Drive candidate handoff: `1uZO9lUqtETjGvTtGz_NCTRkPG4ufUsl5wESneDAqARk`
- HANDOFF_03 Drive candidate: `1X2rZObH69IF-vXF4j8Imjh78B1NkJvQcYO8Jcr9-PNM`
- ownership ledger: `CAID-LK-0090 HANDOFF_READY_REVIEW_ONLY`

## BLOCKED
PR #4 is intentionally not merged yet. Antigravity factual local runtime evidence and CHAT05 independent acceptance are required before candidate promotion. Production Evidence FS/KMS/scanner/DLP/backup and approved independent Polygon providers remain production/infra gates. Real wallet/sign/payment/tx/deploy/cutover remain HUMAN_GATE.

## NEXT
Antigravity executes the persisted task pack. CHAT05 independently validates the exact candidate and AG evidence. If green, CHAT02 may merge and promote Payment/Entitlement `1.1`; Golden E2E then consumes the durable `settlement_certificate_id` at the Core authorization boundary.
