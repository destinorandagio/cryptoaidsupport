# CryptoAID Global Knowledge Service

## Purpose

This is the single knowledge layer for CryptoAID dApp tools/services and the Telegram assistant.

```text
DAPPMAP / MIRROR-B+ / HyperZ & Family / CryptoAID Core
                         ↓
              Global Knowledge Registry
                         ↓
               Verification / Policy Gate
                         ↓
               Global Knowledge Service
                         ↓
        ┌────────────────┼────────────────┐
        ↓                ↓                ↓
   CryptoAID dApp    Telegram Bot    Tools / Services
```

## Source registry

`knowledge/global/KNOWLEDGE_GLOBAL_MANIFEST.json`

Every knowledge family is registered here with a priority and path. New knowledge modules should be added to the manifest rather than hardcoded into every tool.

## Current families

- CryptoAID Core
- CryptoAID Services
- Official Links
- FAQ
- DAPPMAP / MIRROR-B+
- HyperZ & Hyper Family
- Security
- Recovery
- Web3 glossary

## Evidence gate

Public dApp/bot responses may use:

- `VERIFIED_PRIMARY_SOURCE`
- `VERIFIED`
- `HIGH_CONFIDENCE`

`ANALYSIS` may be surfaced only with an analysis label.

The following are not public facts:

- `DRAFT`
- `UNRESOLVED`
- `CONFLICT`
- `OBSOLETE`

Private/user-owned evidence must never be exposed through public endpoints.

## Python service

`bot/global_knowledge_service.py`

Main methods:

- `SERVICE.health()`
- `SERVICE.domains()`
- `SERVICE.search(query)`
- `SERVICE.query(query)`

The dApp backend and tools should call this service rather than reading arbitrary files independently.

## HTTP adapter

`bot/knowledge_api.py`

Endpoints:

- `GET /knowledge/health`
- `GET /knowledge/domains`
- `GET /knowledge/search?q=...`
- `GET /knowledge/query?q=...`
- `POST /knowledge/query` with `{ "query": "..." }`

The built-in HTTP adapter is intentionally dependency-light. For public production deployment, place it behind the CryptoAID backend/API gateway with TLS, authentication/rate limits where appropriate, CORS policy and observability.

## DAPPMAP data

The registry records the canonical DAPPMAP/MIRROR master asset names and schema rules. The full `MIRROR-B+_DAPPMAP.sqlite` dataset should be mounted/imported into the production backend when available; do not fabricate its 17k+ entity rows from metadata alone.

## Rule

One knowledge truth layer, many consumers. Telegram, dApp cards, search, recovery tools, DAPPMAP tools and future services should resolve knowledge through the same evidence-aware service.
