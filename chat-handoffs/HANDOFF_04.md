# HANDOFF_04 — CHAT03 DIGITAL TWIN / SEARCH / WALLET / DAPPMAP

Repository: `destinorandagio/cryptoaidsupport`  
Branch: `main`

## Authority boundary

CHAT03 owns the Digital Twin **read model**, search/entity resolution, wallet connectivity contracts and DAPPMAP data contracts. It does not own Case, Evidence, Payment, financial truth, or Knowledge authority.

## Versions

- TWIN_SCHEMA_VERSION: `1.0.0`
- KNOWLEDGE_VERSION_CONSUMED: `UNPINNED_EXISTING_MASTER`
- WALLET_MATRIX_VERSION: `1.0.0`
- DAPPMAP_CONTRACT_VERSION: `1.0.0`

## Built

- `twin/engine.py`: deterministic project/dApp/token/contract/alias resolution primitives.
- Twin states: KNOWN / VERIFIED / SUPPORTED / TO_VERIFY / UNKNOWN.
- Every provenance object carries source, source_date, observed_at, confidence, freshness and version.
- Search miss returns TO_VERIFY + Case availability and never self-promotes to VERIFIED.
- Same-name collisions require chain/contract disambiguation; no arbitrary merge.
- `twin/contracts.py`: Polygon chainId 137, non-custodial wallet invariants, EIP-6963 / MetaMask / TokenPocket / WalletConnect-Reown target matrix.
- DAPPMAP graph contract for projects, chains, contracts, assets, wallets, evidence and case relevance.
- `tests/test_twin_engine.py`: deterministic safety/invariant tests.

## Tested status

Tests are committed but must not be reported as passed until GitHub CI observes this commit. Runtime browser/mobile wallet flows are not yet testable because CHAT04 owns frontend presentation and has not exposed that integration surface here.

## Blocked / dependencies

1. CHAT06 must publish a versioned knowledge context-pack contract; candidate knowledge must remain distinct from VERIFIED.
2. CHAT10 must provide RPC health/config contract; degraded RPC must never be represented as healthy/LIVE.
3. CHAT04 must consume the wallet/search/DAPPMAP contracts and implement browser/mobile presentation/runtime adapters.
4. CHAT05 must independently exercise collision, stale Twin, knowledge conflict, wallet disconnect/account/chain changes, WalletConnect failure and RPC outage.

## Next

Observe CI → fix any failures → pin CHAT06 knowledge version → integrate CHAT10 RPC health → expose contracts to CHAT04 → execute full wallet/browser/mobile and DAPPMAP integration matrix.
