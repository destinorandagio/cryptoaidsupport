# HANDOFF_07 — CHAT06 GLOBAL KNOWLEDGE / WEB3 INTELLIGENCE — v0.1.0

cycle=20260902-1153  
stage=07 GLOBAL_KNOWLEDGE_WEB3_INTELLIGENCE  
owner=CHAT06_GLOBAL_KNOWLEDGE  
status=ACTIVE_BOOTSTRAP  
release_state=NO_GO

## Authority boundary

CHAT06 is a derived knowledge layer. It owns provenance-aware Web3 knowledge, recovery intelligence, claim classification, entity relationships, Case Context Packs and versioned DAPPMAP relationship releases.

CHAT06 does not own MASTER, Case state, payment truth, entitlement ledger, financial truth or Digital Twin authority.

## Repository readback

Existing knowledge surfaces are reused, not duplicated:

- `knowledge/cryptoaid_master.json`
- `knowledge/global/KNOWLEDGE_GLOBAL_MANIFEST.json`
- `knowledge/global/DAPPMAP_MIRROR_REGISTRY.json`
- `knowledge/hyperz/`
- `knowledge/recovery/`
- `knowledge/web3/`

The current global manifest already enforces evidence-first/no-hallucinated-facts principles, public-answer allow/deny rules and private-evidence isolation. CHAT06 will extend this non-destructively.

## Mandatory semantic rules

- Dead != scam
- Offline != dead
- TVL 0 != dead
- Allegation != conviction
- Wallet relation != person attribution
- Migration != collapse

Knowledge states required by CHAT06:

`VERIFIED`, `SUPPORTED`, `UNVERIFIED`, `ANALYSIS`, `COMMUNITY_REPORT`, `CONTRADICTED`, `UNKNOWN`.

Existing manifest verification vocabulary remains authoritative for existing consumers until a tested compatibility mapping is introduced. No blind migration is allowed.

## Pipeline

DISCOVER → INGEST → NORMALIZE → ENTITY_RESOLVE → SOURCE → CLAIM → EVIDENCE → VERIFY → CLASSIFY → RELATE → SCORE → RELEASE → TWIN → DAPPMAP → CASE_CONTEXT.

## Release contract

Every CHAT06 release must publish:

- KNOWLEDGE_VERSION
- SOURCE_DELTA
- CLAIMS_DELTA
- VERIFIED
- CONTRADICTED
- TO_VERIFY
- AFFECTED_TWINS
- AFFECTED_CASE_CONTEXT
- BLOCKERS

Consumers:

- CHAT03 consumes versioned Twin/DAPPMAP releases.
- CHAT01 may consume Case Context Packs.
- CHAT07 may consume verified FAQ/knowledge.
- CHAT08 may read operational knowledge analytics.
- CHAT09 may consume only publishable verified claims and must never promote UNVERIFIED material as fact.

## Auto-evolution rule

NEW EVIDENCE → IMPACT GRAPH → AFFECTED CLAIM → NEW VERSION → AFFECTED TWIN/CASE CONTEXT ONLY.

No blind global regeneration.

## Current blockers

1. CHAT05 QA reports global sync finding `QA05-P0-002` because CHAT06-10 release-impacting handoffs were absent at audit start. This handoff begins remediation for CHAT06 only.
2. Repository-wide release remains `NO_GO` under independent QA.
3. Existing knowledge verification vocabulary must be mapped to CHAT06 states without breaking current consumers.

## Next implementation slice

1. Inventory canonical/global/hyperz/recovery/web3 schemas.
2. Define source, claim, evidence, relation and provenance contracts.
3. Define canonical entity + alias/version/migration relation model without duplicate objects.
4. Define Case Context Pack schema.
5. Define DAPPMAP relationship release schema for CHAT03.
6. Add publishability/contradiction/impact-propagation tests.

READBACK_REQUIRED=YES
