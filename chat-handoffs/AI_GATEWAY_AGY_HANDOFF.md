# CRYPTOAID AI GATEWAY — AGY EXECUTION HANDOFF

Repository: destinorandagio/cryptoaidsupport
Branch: main

## Goal
Integrate a server-side AI gateway into the CryptoAID dApp. Groq is primary using the legitimate credential pool available in the shared Drive environment file. Other configured AI providers are fallbacks.

## Read first
- core/ai/gateway_spec.json
- core/ai/env.example
- web3/deploy/polygon-mainnet-manifest.json

## Secret provisioning
1. Read the shared Drive environment file locally.
2. Map the available Groq credentials to GROQ_API_KEY_01..N in the SERVER runtime only.
3. Map available fallback AI credentials to the corresponding server environment names.
4. Do not copy the source environment file into Git, public_html, frontend assets, browser storage, logs or responses.
5. Do not expose credentials to client JavaScript.
6. If credentials have been exposed outside trusted secret storage, rotate them before production use.

## Backend
Implement POST /api/ai/chat using the existing CryptoAID backend/runtime conventions. Do not introduce a second application authority or database.

Request: message plus optional surface, sicIdRef, caseId, publicWeb3Context, locale.

Response: ok, answer, provider, model, requestId, fallbackUsed.

## Provider engine
- Groq primary.
- Credential pool health tracking and circuit breaker.
- Pool is for resilience/failover, not quota circumvention.
- Timeout 25s default.
- Fail closed on malformed provider output.
- Retry a different healthy credential/provider only for operational failures according to provider terms.
- Optional fallbacks: OpenAI, Gemini, Anthropic, OpenRouter when provisioned.

## CryptoAID surfaces
- general assistant
- DAPPMAP investigator
- Case assistant
- Rank/Quest/Miner assistant
- Web3 assistant grounded in polygon-mainnet-manifest.json

## Evidence boundary
Private Evidence is DENY BY DEFAULT for third-party AI. Do not send private files, secrets, wallet credentials, seed phrases, bearer tokens, or unnecessary PII. Only explicitly authorized and minimized text may be sent to an external provider.

## Frontend
Add a CryptoAID-branded AI assistant surface to the existing dApp. Frontend calls only /api/ai/chat. It never calls Groq or another provider directly.

UI states: idle, thinking, answer, provider unavailable, rate limited, offline. Do not display provider credentials or raw backend errors.

## Security
- request size limit
- per-user/IP rate limiting consistent with existing identity architecture
- server-side timeout
- output escaping
- log redaction
- no secrets in telemetry
- no arbitrary URL fetch supplied by model/user without validation
- AI can suggest Web3 actions but cannot sign or submit wallet transactions
- MASTER remains application authority

## Tests
Test primary Groq success, one Groq credential unavailable, provider timeout, fallback provider, all providers unavailable, rate limit, oversized input, malicious prompt asking for secrets, Evidence-private rejection, Web3 manifest grounding, and frontend disconnected/offline behavior.

## Completion report
Return factual status for: AI_GATEWAY, GROQ_POOL, FALLBACKS, SECRET_SCAN, FRONTEND_AI, DAPPMAP_AI, CASE_AI, WEB3_AI, TESTS, BLOCKERS. Never print any API key in the report.
