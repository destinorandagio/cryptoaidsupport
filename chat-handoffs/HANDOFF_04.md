# HANDOFF_04 — CHAT03 DIGITAL TWIN / SEARCH / WALLET / DAPPMAP — 20260902-1130

status=REVIEW_BLOCKED_UPSTREAM_CI  
release_state=NO_GO  
repository=`destinorandagio/cryptoaidsupport`  
change_branch=`feat/chat03-twin-wallet-sync-v1-1`  
pr=`#3`

## SYNC_INPUTS

- Global ownership/control read: CHAT03 exclusively owns Twin/Search/Wallet read contracts; duplicate Twin/identity authorities are forbidden.
- Core consumer contract: `control/core/CORE_CONSUMER_CONTRACT_v0.3.13.json`, Core `0.3.13`, SIC-ID sole durable principal, wallet revocable action/payment resource, Polygon `137`, CHAT03 read/derived only.
- HANDOFF_03 verified from `control/evidence-payment/HANDOFF_03.md`: cycle `20260902-1120`, v`0.6.7`, `SOURCE_PRESERVING_PARENT_CERT_READBACK_VERIFIED`; Stage03 source unchanged, parent drift to Core v0.3.13 closed.
- CHAT05 QA input: Drive `1QsNr--zg5qsnxGJnxz7PgYvrjxE8LHawxdC5sdT0ns0`, cycle `20260902-1050`, NO_GO; exact H04/H05 runtime bytes remain unavailable to QA composition.
- CHAT06 separate versioned context-pack handoff: **NOT DISCOVERED** in canonical repo/Drive searches. Existing `knowledge/cryptoaid_master.json` is consumed only as derived context, never as Twin/financial authority.
- CHAT10 separate RPC/runtime/observability handoff: **NOT DISCOVERED**. RPC health therefore remains contract-only/TO_VERIFY and cannot be labeled LIVE.
- Prior Stage04 runtime authority: Drive H04 `1lyxxemsDf0ONnxsFkVOXJ0VMhLiUbhUqc1VZlYC4i9Q` v1.6.0 parent recert over exact v1.5.0 package SHA-256 `5199a8c9f35a53d4e7d12d8cf744a415e64c1456b5a7b2d3b9d88cba6f53d894`.

## KNOWLEDGE_VERSION

`knowledge/cryptoaid_master.json` blob `f6e45315782f42982e5a20aa31318ef6a3663542`, mode=`DERIVED_CONTEXT_ONLY`.

CHAT06 context packs are accepted only with `pack_id + version + status + provenance + generated_at`. `CANDIDATE` and `UNVERIFIED` are forced to `TO_VERIFY`; CHAT03 cannot promote them to VERIFIED. No separate CHAT06 pack version is invented.

## TWIN_VERSION

- Twin read schema: `1.1.0`
- DAPPMAP contract: `1.1.0`
- Core consumer boundary: `0.3.13`
- Runtime Stage04 source authority remains v1.5.0 bytes / H04 v1.6.0 lineage certificate until a byte-real downstream composition is exposed.

Read-model invariants:

- states only `KNOWN / VERIFIED / SUPPORTED / TO_VERIFY / UNKNOWN`;
- VERIFIED Twin requires provenance;
- alias/ticker/family/contract/chain resolution is deterministic;
- ambiguity fails closed and requires disambiguation;
- unknown project produces noncanonical `USER_SUBMITTED_TO_VERIFY`, remains `TO_VERIFY`, and Case continuation is allowed;
- every numeric fact requires `value + source + source_date + confidence + cache_state + truth_label + version`;
- `LIVE` requires actual fresh/request-time evidence and `cache_state=FRESH`; cached RUN020/derived knowledge is never relabeled LIVE.

## WALLET_MATRIX

Version `1.1.0`, Polygon chainId `137` / `0x89`.

| Provider/path | Contract status | Runtime truth |
| --- | --- | --- |
| EIP-6963 | explicit user selection; untrusted metadata; no first-provider auto-pick | deterministic contract built; real extension browser HUMAN_GATE |
| MetaMask injected/mobile | EIP-6963/injected target | NOT_TESTED_REAL_DEVICE |
| TokenPocket extension/mobile/in-app | EIP-6963/injected/mobile target | NOT_TESTED_REAL_DEVICE |
| WalletConnect/Reown external wallet | QR/deeplink, non-secret client config only | NOT_TESTED_REAL_DEVICE/AUTHORIZATION |
| Polygon137 RPC health | CHAT10-owned request-time health evidence required | TO_VERIFY until CHAT10 contract/actual health observation exists |

Wallet safety:

- NON_CUSTODIAL; no seed/mnemonic/private key/raw signing material backend storage;
- wallet connect is not SIC-ID authentication;
- `personal_sign` only with readable challenge + explicit user confirmation;
- `eth_sendTransaction` only from exact persisted intent + explicit user confirmation;
- `eth_sendRawTransaction` is forbidden for the dApp contract;
- `accountsChanged`, `chainChanged`, `disconnect`, provider replacement invalidate/revalidate action authority;
- successful chain-switch call is insufficient: post-verify `eth_chainId == 0x89` is mandatory;
- browser tx remains `TO_VERIFY`; no Case/economic effect until authoritative Stage03 settlement certificate.

## COLLISIONS

- REJECT competing Twin authority or second identity registry.
- REJECT wallet as durable identity; SIC-ID remains sole durable principal.
- REJECT CHAT03 direct Core/Case/Evidence/payment/entitlement writes.
- REJECT derived/CANDIDATE/UNVERIFIED knowledge promotion.
- REJECT RPC/data marked LIVE without current health/observation evidence.
- REJECT legacy shared `wallet.js/twins.php` as authority where it conflicts with H04 exact source lineage.
- REJECT blind `public_html` merge: exact H04/H05 bytes + serial Stage06 composition remain mandatory.

## BUILT

PR #3 adds a scoped CHAT03 control/read-model delta:

- `twin/contracts.py`: Core 0.3.13 boundary, epistemic truth/cache labels, CHAT06 context contract, CHAT10 RPC health contract, hardened wallet/provider/session matrix.
- `twin/engine.py`: VERIFIED provenance enforcement, numeric fact evidence contract, ticker/family resolution, safe context-pack ingestion, explicit TO_VERIFY candidate contract.
- `tests/test_twin_engine.py`: expanded deterministic contract/adversarial checks.
- `.github/workflows/chat03-twin-wallet-contract.yml`: scoped CHAT03 CI gate prepared for default-branch activation.

No `BLOCKCHAINPLUS-MASTER.sqlite`, shared `public_html`, `.htaccess`, payment, Evidence, entitlement, Case truth, real signature or real transaction was mutated.

## TESTED

- Isolated deterministic harness reproducing the committed CHAT03 logic: **15/15 PASS**.
- Fresh official standards verification: EIP-1193 event/session semantics and EIP-6963 multi-provider discovery remain compatible with the contract.
- Plugin catalog search for browser/MetaMask/TokenPocket/WalletConnect/Reown test capability returned no installable match; nothing installed.
- PR full CI **FAILED before CHAT03 tests** on a pre-existing/concurrent CHAT01-owned collection regression: `core/__init__.py` imports `CaseError`, but `core/case_engine.py` does not expose it.
- Main at HANDOFF_03 v0.6.7 is likewise CI red for the same Core regression; this is not attributed to CHAT03.

## FIXED

- EIP-6963 provider selection contract changed from implicit/ambiguous to explicit user selection.
- LIVE classification now fails closed unless fresh request-time evidence exists.
- chain-switch success now requires post-verification to `0x89`.
- wallet connect is explicitly separated from durable authentication.
- CHAT06 candidate/unverified context is forcibly downgraded to TO_VERIFY and cannot alter Twin authority.
- scoped secret guard was corrected to avoid flagging policy strings while still rejecting committed wallet-secret material.

## BLOCKED

1. **UPSTREAM CI / CHAT01 ownership:** `CaseError` public import regression blocks full-suite green. CHAT03 did not patch another owner's Core source.
2. CHAT06 versioned context-pack handoff not discovered; knowledge pack cannot be pinned beyond current master blob SHA.
3. CHAT10 RPC/runtime/observability handoff not discovered; no RPC endpoint/health is declared LIVE.
4. Exact Stage04 v1.5.0 runtime package bytes remain unavailable to this execution runtime; H04 v1.6.0 is lineage/prose authority only here.
5. Stage05/Stage06 exact serial byte composition, clean deploy tree, browser/PWA Golden E2E remain NO_GO.
6. MetaMask, TokenPocket, Reown, real sign/payment/transaction/deploy remain HUMAN_GATE and were not run.

## NEXT

1. CHAT01 owner restores/versions the Core Python public import contract; rerun main/PR CI.
2. When PR #3 full CI is green, merge the CHAT03 scoped read-contract delta; the new scoped workflow then becomes available on main.
3. Consume a future CHAT06 pack only after provenance/status/version validation; never promote CANDIDATE/UNVERIFIED.
4. Consume CHAT10 Polygon137 RPC-health/provider matrix when published; actual health must be observed before LIVE.
5. Stage05 consumes this handoff + H03 v0.6.7; Stage06 serial-composes exact H02/H03/H04/H05 bytes and runs all-file/security/browser/PWA QA.
6. Only after autonomous P0 gates are green proceed to HUMAN_GATE real wallets/sign/payment/tx/deploy.

GLOBAL_RELEASE=NO_GO
