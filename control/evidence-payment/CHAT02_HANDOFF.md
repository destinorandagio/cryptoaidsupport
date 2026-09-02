# CHAT02 — Evidence + Payment — v0.6.7

status=READBACK_VERIFIED_NO_GO
cycle=20260902-1120
owner=CHAT02_EVIDENCE_PAYMENT
sole_truth=evidence_lifecycle,payment_verification,entitlement
parent_h02=Core v0.3.13 Drive 1y6Q0Z57IbF3B6qwMnfBND9OkTuPhYQMn-pCwFVxlw-8
parent_patch_sha256=ffc2974e6f131ffec2050762ed6b70b6be307bb9554fc150572b53eb37b7f56e
handoff03_drive=1IRC3LYNqt3aCVkw1TKysB9JlJjUvbyseMXsOhW79-Nc
chat02_drive=1984TFbwh179AAaRvffbY2n1YjfGGPxG15uVJxvkPjos
ownership_ledger_row=CAID-LK-0087 RELEASED_AFTER_READBACK_NO_GO
stage03_source=UNCHANGED_EXACT_v0.6.2
stage03_package_sha256=6419367f716fac62735b81e97c5a802318c3dcb3e332f7fcc0659ae25e0f3de9
migrations_chat01=001..004
migrations_chat02=005..008

## Frozen configuration

Polygon chainId=137. Treasury=`0x3C320B3a0917fF44BF6551CDdee44402AFcF250C`. SIC-ID is the sole durable principal; wallet is a revocable action/payment resource. Activation is 50 POL once per SIC-ID, yielding FIRST_CASE_CREDIT_50 AVAILABLE→RESERVED; first Case remainder is 450 POL; after CONSUMED, subsequent Cases cost 500 POL. Ambiguous/nonfinal/provider-disputed settlement is MANUAL_REVIEW. Automatic ACCEPTED is disabled. Evidence is private by default and bytes stay outside webroot.

Effective config fingerprint: `f30e2d72441da5d3edcdcf6f0042fb5784dc48178352595ba70a9872daf334ec`.

## Sync decisions

ACCEPT Core v0.3.13 consumer contract declaring CHAT02 ownership of Evidence/payment/entitlement and Core migrations 001..004 only. ACCEPT CHAT04 UX and CHAT07 Telegram/support as state/API consumers only. ACCEPT CHAT08 admin/config only through versioned authorized contracts with no direct truth writes. ACCEPT CHAT10 runtime/config evidence only. ACCEPT CHAT05/H06 independent QA as verifier, not authority owner.

REJECT any parallel Evidence DB/store authority, payment ledger/verifier, entitlement truth, shadow `cryptoaid.sqlite`, consumer direct DB mutation, legacy exact-500-only economics, unversioned treasury/economic changes, or provider observation lacking tx/chain/receipt identity plus legal-operator authority evidence.

## Verification

Core v0.3.13 source patch reconstructed exactly: 11,789 bytes, SHA256 `ffc2974e6f131ffec2050762ed6b70b6be307bb9554fc150572b53eb37b7f56e`. Fresh Core-v0.3.13/Stage03-v0.6.2 compatibility gate: 20/20 PASS. Fresh exact Stage03 contract: 35/35 PASS. Fresh Stage03 static/security: 20/20 PASS. PHP lint: 3/3 PASS. H06 independently proved canonical MASTER + migrations 001..008 x2, integrity ok, FK0, Stage03 schema/adversarial 41/41 and races one winner; that schema suite was not rerun in this cycle.

Adversarial coverage includes wrong amount/chain/treasury/sender/to/value/receipt, replay and tx identity, nonfinal/provider disagreement/incomplete authority, revoked wallet, 50-credit reserve/consume, binary Evidence PII/secret/malware/scanner failure, private-root webroot escape, and no network under writer lock.

## Release truth

No Stage03 source/schema/economic change was required for Core v0.3.13. No real payment/signature/tx/deploy occurred. Production MASTER, `public_html` and `.htaccess` were not mutated. Global release remains NO_GO pending target runtime dependencies, request-time SIC-ID, production private Evidence FS/KMS/scanner/DLP/backup, >=2 approved independent Polygon provider authorities/finality, exact H04/H05 byte composition, clean public package, browser/PWA/device Golden E2E and HUMAN_GO_LIVE_GATE.
