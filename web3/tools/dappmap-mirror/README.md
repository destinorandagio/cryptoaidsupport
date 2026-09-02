# CryptoAID DAPPMAP — powered by MIRROR-B+

## Purpose
DAPPMAP is the visual discovery, research and gamified exploration service inside CryptoAID.
MIRROR-B+ is the canonical acquisition, verification and Digital Twin protocol/data layer. DAPPMAP is the user-facing product.

## Canonical source
- Master DB: MIRROR-B+_DAPPMAP.sqlite
- Historical registry: MIRROR-B+_Registro_Mondiale_dApp_2012-2026.xlsx
- Canonical universe: 17,604 dApps/projects and 494 indexed chains at latest project checkpoint.
- Never create a new SIC-ID when an entity already has one.
- One dApp = one SIC-ID-DAPP; multichain deployments are relationships, not duplicate dApps.

## User experience
SEARCH → DISCOVER → EXPLORE → OPEN CARD → FOLLOW GRAPH → PLAY QUEST → VERIFY → EARN XP/DRX → RANK UP

### Main views
1. **Global DAPPMAP** — interactive 2D/3D graph/map of projects, chains, tokens, contracts, events and relationships.
2. **Dead Zone** — abandoned/dead/inactive dApps and historical projects.
3. **Token Graveyard** — dead, delisted, abandoned or illiquid tokens with evidence-based status.
4. **Time Machine** — timeline 2012→today; explore births, peaks, incidents, migrations and shutdowns.
5. **Project Card / Digital Twin** — complete evidence-backed entity sheet.
6. **Chain Explorer** — filter projects by chain and deployment history.
7. **Relationship Graph** — dApp→chain→deployment→contract→token→event→community/source.
8. **Recovery Lens** — historical/recovery-relevant projects without making unsupported legal claims.
9. **Play / Quest Mode** — discovery missions linked to CryptoAID Useful Miner and NFT Rank.
10. **Compare Mode** — compare up to 4 projects/tokens on status, chain, age, evidence, incidents and activity.

## Project Card fields
- Original logo / icon / wordmark where licensed/available
- Name, SIC-ID, aliases, ticker(s)
- Evidence-based lifecycle status
- Category/subcategory
- Launch/last-known activity dates
- Chains and chain IDs
- Deployment and verified contract addresses
- Tokens/NFTs
- Historical websites and archived links
- Official/current and historical communities
- GitHub/documentation/whitepaper sources
- Known migrations/rebrands/forks
- Security incidents/exploits with dates and sources
- Market/liquidity status where verified
- Digital Twin version
- Source confidence and last verification timestamp
- Related entities graph

## Status language
Never label a project scam/dead solely from community allegations. Use evidence-graded states such as ACTIVE, MONITORING, IMPAIRED, INACTIVE, ABANDONED, DEAD/CONFIRMED-CLOSED, MIGRATED, REBRANDED, UNKNOWN, plus claim confidence: VERIFIED, PARTIALLY_VERIFIED, NOT_INDEPENDENTLY_VERIFIABLE, CONTRADICTED_BY_EVIDENCE, NO_LONGER_CURRENT, PENDING_INVESTIGATION.

## Gamification
DAPPMAP integrates with CryptoAID Useful Miner + NFT Rank:
- Discover a project
- Complete history quiz
- Locate a verified historical source
- Validate a contract/deployment candidate
- Find a duplicate/alias candidate
- Explore a chain collection
- Complete themed expeditions (DeFi Graveyard, GameFi Ghost Town, Node Era, Stablecoin Crashes, etc.)

Rewards are XP/DRX/achievements by default. Any POL/DUX reward must come from an explicitly funded reward pool and verified mission rules.

## Visual design
Mandatory CryptoAID design system:
- primary red #ff202e
- black #050505 / #0b0b0e
- white #ffffff
- red glow / glass panels / high contrast
- original CryptoAID logo from canonical assets only
- historical project logos must remain original and must never imply partnership

Map semantics:
- nodes = entities
- edges = verified/graded relationships
- node halo = confidence/activity state
- timeline pulse = historical events
- hover = quick facts
- click = Digital Twin card

## Architecture
`MIRROR-B+ DB → normalized API/search index → DAPPMAP UI → Digital Twin cards → graph/time/map layers → Quest Adapter → Useful Miner → NFT Rank`

The public UI must be read-oriented. Contribution/verification actions go through a review/verification pipeline before canonical DB mutation.
