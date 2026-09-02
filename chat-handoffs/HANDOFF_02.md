# CRYPTOAID — HANDOFF_02 — CORE + ADMIN MVP

## CYCLE
20260902-1525

## STATUS
**QA05-P0-010 OWNER-CLOSED / CI GREEN / RELEASE NO_GO.** CHAT01 now binds idempotency replay to operation + authenticated subject + canonical logical payload instead of operation alone. CHAT08 minimum Admin has no source expansion and inherits the stronger Core replay boundary. No schema migration, economics change, MASTER mutation, canonical public_html write, `.htaccess` change, private Evidence write or real transaction/deploy occurred.

## FRESH INPUTS
- HANDOFF_01: `20260902-1500 v0.7.0` plus late delta; it explicitly marked QA05-P0-010 as the active CHAT01 blocker and prior PR10 as stale once Core repair advanced main.
- HANDOFF_06: `20260902-1450 v0.6.0`; independent QA reproduced same-operation changed-subject replay and required subject + canonical payload binding.
- Shared ownership: `CAID-LK-0108` owns only Core/Admin/handoff surfaces for this repair; CHAT00/10 integration/control work is disjoint.
- CHAT02 economics/evidence/payment/entitlement remain owner truth and are consumed read-only only.

## EXACT SOURCE / TEST EVIDENCE
- Functional green head: `5f00a3b61c10994eaf92f69c1d2b539183c6448c`
- Core source commit: `67f4bbaaea5a8d9d362e1bd62886417b0149b75b`
- `core/case_engine.py` blob: `dae4075809d4f9cba96e6b1a9b9b13d992a73014`
- Core module version: `1.3`; schema `chat01-core-1`; API `v1`; Case state contract `1.0`
- New fingerprint test commit: `d8d2cfe3fb7af4ffaa782e43afcde3c1cbdcacaa`
- `tests/test_core_idempotency_fingerprint.py` blob: `034787b53014f423ad83fef195a49fc8c52e0064`
- Legacy regression alignment commit: `5f00a3b61c10994eaf92f69c1d2b539183c6448c`
- Admin source remains `admin/ops.py` blob `4c1d050f2f16cebe84dc0b95d00d1ab2a7bdf9cc`, `ADMIN_VERSION=0.3.1`
- GitHub Actions CI run `33635269624` / `#368`: **SUCCESS**
- Full pytest: **85 passed** (previous red run `#367` was `1 failed, 84 passed`; only the stale expected-replay assertion was corrected)
- CI job also passed compile, PHP baseline, PDO SQLite memory, staging PWA-shell package/restore smoke and obvious Telegram-token scan.

The GitHub runner environment is CI evidence only, not target-host evidence.

## CHAT01 1.3.2 HANDOFF — CORE P0 CLOSED
No schema migration. Existing `core_requests.response_json` now stores an internal versioned envelope containing the original response plus a SHA-256 fingerprint of the canonical logical request.

Replay rules:
1. Fingerprint includes `operation` plus security-relevant logical payload.
2. `request_id` is intentionally transport-only and may change on an otherwise identical retry.
3. `register_user` binds SIC-ID + profile.
4. `create_session` binds user + SIC-ID + TTL.
5. `bind_wallet` binds user + SIC-ID + normalized wallet; wallet case normalization is replay-equivalent.
6. `open_case` binds user + SIC-ID + normalized wallet + project reference + search-hit truth + actor.
7. `transition` binds Case + user + target state + actor + reason + authorization + expected version.
8. Same operation/key with any changed bound field fails `IDEMPOTENCY_CONFLICT` 409 before returning a stored response.
9. Legacy/pre-fingerprint stored requests fail closed instead of being replayed without verifiable subject/payload binding.
10. Existing `BEGIN IMMEDIATE` sequencing remains, preserving deterministic same-key concurrency behavior.

Paid `ACTIVE` still requires the durable same-Case CHAT02 settled entitlement effect; CHAT01 does not write payment/evidence/entitlement truth.

## CHAT08 0.3.2 HANDOFF — ADMIN P0
No Admin source delta. Minimum feature freeze remains intact.

- `ADMIN_CASE_REVIEWER` RBAC remains mandatory.
- actor/reason/request_id/idempotency_key attribution remains required before mutation.
- Case queue, user lookup, manual-review projection and CRM timeline remain privacy-minimized.
- all Admin Case mutation remains routed through CHAT01 Core.
- because transition fingerprint now includes actor/reason/authorization/expected version, a previously-used Admin idempotency key cannot be replayed under changed review semantics.
- `ADMIN_REVIEW` still cannot self-authorize a paid Case to `ACTIVE`.

## TESTED
PASS:
- first + returning user;
- SIC-ID session create/replay/resume/mismatch/revoke;
- Case create/idempotency/resume;
- unknown project -> `TO_VERIFY`;
- invalid/stale/concurrent transition guards;
- changed SIC-ID/profile/session subject/TTL/wallet/project/search-hit/authorization under same operation/key -> 409 conflict;
- identical logical replay with new transport request_id -> same response;
- same-key same-payload Case race -> one truth/replay;
- same-key different-payload Case race -> one side effect + conflict;
- Evidence refs and CHAT02 owner contract integration regressions;
- forged paid authorization rejected; settled same-Case effect permits `ACTIVE`;
- one Next Action;
- Admin RBAC/manual review/audit/user lookup/CRM regressions;
- Admin cannot bypass paid ACTIVE guard.

FIXED DURING RETEST:
- CI `#367` failed because `tests/test_core_case_engine.py::test_new_returning_user_and_duplicate_request` still asserted the insecure historical behavior (`OTHER` SIC-ID replay under the original key). The regression was corrected to require `IDEMPOTENCY_CONFLICT`; CI `#368` is green.

## OWNERSHIP / COLLISIONS
- ACCEPT: QA05-P0-010 -> implemented by CHAT01 owner; state `OWNER_CLOSED_PENDING_INDEPENDENT_CHAT05_RETEST`.
- ACCEPT: CHAT02 settlement/entitlement effect -> read-only consumer boundary only.
- REJECT: same-key changed subject/payload replay.
- REJECT: any CHAT08 direct Case/payment/entitlement truth mutation.
- REJECT: any second authoritative DB/Case engine.
- No production MASTER/public_html/.htaccess write.

## ANTIGRAVITY
New exact-head same-Drive task:
- Task ID: `AG-CRYPTOAID-CORE-ADMIN-P0-010-20260902-1525`
- Drive document: `14Z2J-K9lxlHkDDoontePH80FQtvikpI0aLVSQuSkKuk`

It requires exact hashes, targeted/full pytest, >=8-worker same/different-payload race evidence, SQLite `integrity_check`/`foreign_key_check`, runtime versions/commands/timestamps/exit codes and protected Admin browser/accessibility checks only if the exact composed route actually exists.

Current AG acceptance: **NOT_RETURNED / NOT_ACCEPTED**. A task pack is not runtime evidence.

## GOLDEN PATH STAGE
Backend Core/Admin Golden-path contracts are **GREEN on source/CI**. The previous PR10 serial runtime candidate is stale relative to this Core fix and must be rebuilt by CHAT00/10 on fresh main before AG/CHAT05 can accept a full Golden Journey.

## BLOCKED / NOT TESTED
- independent CHAT05 retest of QA05-P0-010 on the exact new Core blob;
- rebuilt exact serial candidate including accepted CHAT02/03/04/07/10 inputs;
- CHAT02 finalized-boundary production settlement proof;
- target-host PHP/request-time SIC-ID/private Evidence runtime evidence;
- protected Admin browser route + real-origin 390x844/desktop accessibility/PWA acceptance;
- durable authenticated Case-linked Support/Admin delivery evidence;
- final clean canonical public_html package + recursive audit + manifest/backup/restore/rollback;
- physical wallet/signature, real payment/transaction and production deploy: HUMAN_GATE/NOT_TESTED.

## NEXT
1. CHAT05 retest QA05-P0-010 on `dae40758...` and mark ACCEPT/REJECT independently.
2. CHAT00/10 rebuild the serial Golden candidate from fresh main after this handoff, then rerun exact-head CI and issue/update AG runtime task against that exact candidate.
3. Close CHAT02 finalized-boundary settlement, execute real-origin Golden Journey, then final package/restore and independent release QA.

## GO / NO-GO
**NO_GO**
