# CryptoAID Web3 Tools — Polygon PoS Mainnet

Embeddable Web3 module for CryptoAID. Target chain: Polygon PoS mainnet (`chainId 137`), gas asset POL.

## Modules

- `CryptoAIDRank.sol`: one soulbound evolving rank NFT per wallet; XP, mission count, rank and reward multiplier.
- `CryptoAIDUsefulMiner.sol`: Proof-of-Useful-Work reward pool. A verifier confirms a unique proof; the contract atomically awards XP and funded POL/DUX/DRX rewards. Proof IDs cannot be reused.
- `CryptoAIDStaking.sol`: scalable reward-per-token staking primitive for DUX/DRX pools. Rewards are explicitly pre-funded.
- `frontend/cryptoaid-web3-tools.ts`: ethers v6 adapter intended to be imported into the main CryptoAID dApp.

## Economic safety invariant

No contract creates yield from user deposits. POL/DUX/DRX miner rewards must be pre-funded. Staking rewards must be transferred into the pool before an epoch starts. Deposited principal is not used to pay earlier users.

## Mainnet deployment order

1. Verify canonical Polygon-mainnet DUX and DRX token addresses.
2. Deploy `CryptoAIDRank(initialOwner)`.
3. Deploy `CryptoAIDUsefulMiner(initialOwner, DUX, DRX, rank)`.
4. `rank.setOperator(miner, true)`.
5. Deploy desired staking pools, e.g. DUX→DRX and/or DRX→DUX.
6. Fund miner reward pools with the exact maximum POL/DUX/DRX budget.
7. Configure missions and verifier address(es).
8. Run local/fork tests, static analysis and source verification before broadcasting production transactions.
9. Insert deployed addresses into the dApp configuration and import the frontend adapter.

## Source patterns studied

Architecture was informed by open-source patterns from Polygon sPOL (official Polygon repository), ERC721 staking/reward accounting, and Merkle-style claim systems. Third-party source code is not vendored here; CryptoAID contracts are separate implementations to keep licensing and security review explicit.

## Important

These files are IMPLEMENTED in the repository but are NOT yet VERIFIED/DEPLOYED. Do not label the system live until compilation, tests, security review, token-address verification and Polygon mainnet deployment receipts have been checked.
