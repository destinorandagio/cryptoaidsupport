# HANDOFF_06 — CHAT05 INDEPENDENT QA / SECURITY + CHAT07 SUPPORT — v0.3.0

cycle=20260902-1300  
owner=CHAT05_QA_SECURITY_RELEASE  
status=HANDOFF_READY_NO_GO  
ready_for_human_go_live_gate=NO  
independently_tested_source_head=2d58ebbefc7099baef2e471d75820e9011e3e80d  
source_ci=33621762265 SUCCESS

## HANDOFFS_TESTED

CHAT00 0.4.2, CHAT01 1.2.2, CHAT02 1.1.1 + PR4 candidate, CHAT03 current 1.0.0 + open rebase candidate, CHAT04 1.7.0 + open compatibility candidate, CHAT05 prior 0.2.0, CHAT06 0.2.0, CHAT07 prior 0.1.0 then new 0.2.0, CHAT08 0.2.0, CHAT10 0.1.0. CHAT09 remains absent. Global control state is stale versus current green CI and is CHAT00-owned; CHAT05 did not overwrite the serialized control plane while the ownership ledger showed CHAT00 late-delta reconciliation active.

## CURRENT INDEPENDENT EVIDENCE

Repository source commit `2d58ebbefc7099baef2e471d75820e9011e3e80d` is CI green: bot compile PASS, full pytest PASS, configured obvious Telegram token regex PASS. `main` remains unprotected with no required status checks.

CHAT07 minimum support delta added `bot/support_mvp.py` and `tests/test_support_mvp.py`: unauthorized Case-linked support rejects fail-closed, credential-like input is rejected, command data is minimized and contains no Evidence payload/SIC-ID field, and unit anti-abuse rate limiting is tested. The live Telegram runtime does not yet wire these guards, `/links` is not a pinned deterministic official-links contract, and request-time Case-owner/notification integration is unproven.

Canonical Drive `public_html` was freshly scanned at root plus `data`, `_lib`, `assets` and `assets/partners`. Root `.htaccess` is present, SHA256 `417784f69d64c650897c8a37ae0a415d190e183cb5d3c5ac33721980d63b3d1d`, and preserves blocking for `/_lib/` plus HTTPS/security headers. Service worker SHA256 `d9c173f9327736d776d37495985441e0facdf05f45798a96bca3bd3901ed5108` pre-caches shell assets and does not insert runtime responses into cache; real-origin behavior remains NOT_TESTED. No DB snapshot/private Evidence/DEMO-APERTA.flag was observed in the scanned tree, but release package hygiene FAILS because `LEGGIMI.txt`, `_lib/schema.sql`, `assets/partners/LEGGIMI-LOGHI.txt` and `assets/partners/wallet-placeholder.png` are dev/placeholder artifacts inside canonical `public_html`.

CHAT02 PR #4 current head `62efcb016a1577863745b27ab83977c98efb0314` has CI-success checks and static review confirms durable settlement certificate, two distinct provider IDs, exact primary/provider tuple agreement, finality gate, duplicate-tx fail-close and idempotent certificate/entitlement lineage. This is CANDIDATE PASS only. Existing AG task was pinned to stale `1000e991...` and no local command/environment/hash completion was returned. CHAT05 reissued exact-head task in Drive `1ptcQqqQgS-oNmPQnnhFVMhY0pXp_R2CbOa0rLP614WM`.

Broad AG runtime task `AG-CRYPTOAID-MVP-RUNTIME-20260902-1238` remains READY_FOR_EXECUTION with no completion evidence. CHAT07 local acceptance task is Drive `1ul6PIZKqrSwOx6CO5j8xTbWik3nPHrd437egGbErV0w`. No AG self-reported PASS was accepted.

Web3 Security workflow remains red on Slither while compile/test/deployment-bundle jobs pass. No production smart-contract deployment may be approved until findings are classified/closed. Real wallet/sign/payment/tx/deploy remain HUMAN_GATE.

## EXACT QA STATUS

| Stream | Status |
|---|---|
| Q1 static/lint/import | PASS repo CI; final serial PHP/runtime lint NOT_TESTED |
| Q2 MASTER/schema/integrity | PASS disposable evidence; final composed runtime NOT_TESTED |
| Q3 auth/privacy/access | FAIL release gate; final request-time runtime NOT_TESTED |
| Q4 Evidence adversarial | PASS contract; production storage/scanner/backup NOT_TESTED |
| Q5 payment/replay/race | PASS current contract; PR4 candidate static/CI PASS; AG/local runtime NOT_ACCEPTED; live Polygon NOT_TESTED |
| Q6 wallet/Polygon | FAIL release gate; final CHAT03/04 tuple unmerged; physical providers HUMAN_GATE |
| Q7 PWA/390/a11y | PASS isolated/static cache policy; real-origin install/offline/reconnect NOT_TESTED |
| Q8 performance/concurrency | NOT_TESTED final runtime |
| Q9 secrets/dependency/package | FAIL canonical public_html dev/placeholder hygiene; CI token regex PASS but not a full recursive release scan |
| Q10 Golden/Admin/Telegram | FAIL release gate: Admin backend contract tested, support contract tested, final E2E/Telegram runtime NOT_TESTED |
| Q11 Knowledge/Growth | NOT_TESTED release-grade; CHAT09 absent |
| Q12 DevOps/release | FAIL: repo CI green, Web3 Slither red, final package/rollback/restore/runtime absent |

## MANDATORY MATRIX

50 activation contract PASS; 450 first Case contract PASS; 500 subsequent Case contract PASS. Wrong amount/chain/treasury/sender, replay/duplicate, disagreement/finality and private/unauthorized Evidence have contract-level negative coverage. Final first/returning-user Golden Journey, duplicate Case, request-time SIC-ID mismatch, wallet disconnect/change/wrong chain, stale knowledge/fake LIVE, final Admin RBAC browser path, live Telegram auth/rate-limit/API/notification, Evidence Pack, real-origin PWA offline/reconnect and serial backup/rollback/restore are NOT_TESTED or incomplete at final-runtime level and therefore do not pass release.

## SECURITY FINDINGS / BLOCKERS

- `QA05-P0-009` CHAT10/CHAT00: clean serial `public_html` package fails due dev/placeholder artifacts.
- `QA05-P0-010` CHAT02: PR4 exact-head local acceptance not returned; stale AG task superseded by exact-head task.
- `QA05-P0-011` CHAT07/CHAT01/CHAT10: live support authorization/rate-limit/official-links/notification runtime incomplete.
- Existing P0 remains: exact CHAT03/04 tuple, final composed runtime, Golden Journey, package/rollback/restore.
- P1: main unprotected/no required checks; Web3 Slither red is a hard block for production smart-contract deployment.

## RELEASE MANIFEST

Status=`NOT_A_FINAL_DEPLOY_PACKAGE`.

- tested repository source head: `2d58ebbefc7099baef2e471d75820e9011e3e80d`
- CHAT07 support source commit: `9fa727abf28fdc6ffa9304e6702934f6255d7512`
- CHAT07 support tests commit: `2d58ebbefc7099baef2e471d75820e9011e3e80d`
- canonical Drive `.htaccess` SHA256: `417784f69d64c650897c8a37ae0a415d190e183cb5d3c5ac33721980d63b3d1d`
- canonical Drive `sw.js` SHA256: `d9c173f9327736d776d37495985441e0facdf05f45798a96bca3bd3901ed5108`
- PR4 candidate head: `62efcb016a1577863745b27ab83977c98efb0314`
- FINAL_DEPLOY_PACKAGE_SHA256: ABSENT
- FINAL_UPLOAD_MANIFEST_SHA256: ABSENT
- ROLLBACK_PACKAGE_SHA256: ABSENT
- RESTORE_CERTIFICATE: ABSENT

## GO / NO-GO

`GO_NO_GO=NO_GO`  
`CRYPTO AID MVP DAPP — READY FOR HUMAN GO-LIVE GATE=NO`

## NEXT_3

1. Obtain AG exact-head PR4 and broad staging/runtime/browser/package/restore evidence; independently accept or reject it.
2. Close CHAT03/04 exact version tuple and wire CHAT07 safe support guard + pinned official links + Case-owner adapter, then run synthetic Golden E2E.
3. Produce a clean deterministic serial package with no dev/placeholders, run recursive security scan, backup/restore/rollback dry-run, then rerun CHAT05 Q1-Q12.

READBACK_REQUIRED=YES
