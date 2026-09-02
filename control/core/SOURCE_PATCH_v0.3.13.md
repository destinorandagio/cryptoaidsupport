# Crypto AID Core v0.3.13 source authority pointer

This repository file is a coordination mirror, not a second source authority and not a deploy/runtime mutation.

- Parent: Core v0.3.12, HANDOFF_02 Drive `1-4Obn8FHpU4fLPIEtU_8YiaajXzPzghjr_ld6Ky8mkE`
- Exact lossless source authority: Drive `1XSxblekve42NjhiRGf8dy3bhxsZBICiEBVY9ctom8p8`
- Patch size: `11789` bytes
- Patch SHA-256: `ffc2974e6f131ffec2050762ed6b70b6be307bb9554fc150572b53eb37b7f56e`
- Encoding in Drive authority: deterministic gzip (`mtime=0`, level 9) + base64
- Apply from the exact v0.3.12 root: decode payload, gunzip, then `patch -p1`
- Drive native readback/export was decoded and reproduced the exact patch bytes and SHA-256.

Changed/added source files:

- `_caid_sicid_http_authority.php` → `09f2061312e2ba488ae1076aca0641393d7eb13fc7c502358f329dd66d4a576a`
- `_caid_wallet_binding.php` → `9be7189a9c11b21a550508f0a1ec50d4752183f9737cfa0f757f64415c81f0b7`
- `CORE_INTERFACE_v0313.json` → `38897c0bbf60e53da48cf6df0a872796ae4ecdf918fa1a2078851d7a44b19ce4`
- `CORE_CONSUMER_CONTRACT_v0313.json` → `3354f30a84ff2ca4d40ee7ef7b2aeacc6a6bf17fb30bbc763369bf08d4e871a8`
- `test_hardening_v0313.php` → `880b167c2df7ba1b36b9f1a5c7b5ee61cf8b96e7bb2fbe0802a0df5629373b1e`
- `test_static_v0313.py` → `ecde47b25f5d18ade5e860562ac8918404adf1c41ccc885737939724df4b7b36`
- `run_tests_v0313.sh` → `bb35c76ae30f6620872c19f1de941344f721a7fbe64a7d280baba0060b228aa6`

No Core migration 005 was added. Production `BLOCKCHAINPLUS-MASTER.sqlite`, `public_html`, and `.htaccess` were not modified.
