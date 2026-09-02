# CryptoAID Web3 Tool Factory

Target: Polygon PoS mainnet (chainId 137), native POL. Brand UI: original CryptoAID logo/assets only; red + white + black; mobile-first.

## Existing core
- NFT Rank / reputation
- Useful Miner / proof-of-contribution
- DUX/DRX staking
- POL + token reward pools

## New modules
1. **CryptoAID Smart Wallet** — ERC-4337-inspired account abstraction: batch actions, recovery, optional sponsored gas. Reference: eth-infinitism/account-abstraction. Do not fork blindly; integrate audited/canonical components.
2. **CryptoAID Swap Radar** — compare routes/quotes then swap. UI must show route, price impact, minimum received, gas and approvals. Reference patterns: Uniswap widgets, DEXTools aggregator widget.
3. **CryptoAID Portfolio X-Ray** — POL/DUX/DRX balances, NFT Rank, staking, miner rewards, positions and transaction timeline.
4. **CryptoAID Stream Vault** — streaming DUX/DRX grants/rewards/partner payouts; contract implemented in `contracts/CryptoAIDStreamVault.sol`.
5. **CryptoAID Boost Lock** — lock DUX/DRX for non-yield utility boost; contract implemented in `contracts/CryptoAIDBoostLock.sol`.
6. **CryptoAID Quest Board** — campaigns and useful-work quests feeding Rank + Miner.
7. **CryptoAID Claim Center** — Merkle epoch claims for scalable DUX/DRX/POL distributions.
8. **CryptoAID Treasury Safe** — multisig/role/timelock-oriented treasury console. Reference patterns: Safe smart account + OpenZeppelin TimelockController.
9. **CryptoAID Governance Arena** — DRX + Rank-weighted proposals/votes, anti-whale modes and Snapshot-compatible signed voting.
10. **CryptoAID Vesting Studio** — create transparent DUX/DRX vesting schedules using OpenZeppelin VestingWallet patterns.
11. **CryptoAID Security Lens** — transaction/approval simulator UI, allowance inventory, revoke links/actions, suspicious-contract warnings. Never claim an address is malicious without evidence.
12. **CryptoAID Rescue Center** — guided asset-recovery workflows for approvals, wrong-network diagnosis, token visibility and evidence collection; no seed/private-key collection.
13. **CryptoAID POL Earn Router** — surface legitimate POL staking/liquid-staking routes with explicit protocol/source/risk disclosure; no fabricated APY.
14. **CryptoAID Achievement Forge** — dynamic badges/NFT visual evolution driven by verified milestones.
15. **CryptoAID Referral Proof** — on-chain attribution codes/events for ecosystem campaigns without custody of user funds.

## UI/UX invariant
Every module imports `ui/cryptoaid-brand.css` and uses official CryptoAID logo assets. No third-party logo may imply sponsorship/partnership. Red is primary action/status accent; white for legibility; black for high-contrast Web3 panels. Responsive cards, large wallet actions, explicit transaction previews, loading/success/failure states and explorer links.

## Security invariant
No private keys or seed phrases in frontend/repo. Mainnet writes require explicit wallet signature. Economic rewards must be funded by real reward pools/protocol yield/fees; never display guaranteed profit or fictitious mining returns.

## Integration contract
Each tool exports: `id`, `name`, `route`, `chainId=137`, `contracts`, `readMethods`, `writeMethods`, `brand`, `riskDisclosure`, `status`. Tools remain plug-and-play for the main CryptoAID dApp.
