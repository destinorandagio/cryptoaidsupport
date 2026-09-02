"""CryptoAID optional AI provider layer.

Server-side only. Never expose provider API keys to browser/client code.
The provider is an accelerator for synthesis, not a source of truth.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import httpx

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
SECRET_PATTERNS = [
    re.compile(r"\b(?:seed phrase|private key|password|2fa|otp)\b", re.I),
    re.compile(r"\b0x[a-fA-F0-9]{64}\b"),
]


class AIUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class AIResponse:
    text: str
    provider: str
    model: str


def redact(text: str) -> str:
    value = text or ""
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value[:6000]


def enabled() -> bool:
    return bool(os.getenv("GROQ_API_KEY")) and os.getenv("AI_ENABLED", "true").lower() == "true"


async def synthesize(*, verified_context: str, user_message: str, language: str = "en") -> AIResponse:
    """Synthesize a response strictly from verified context.

    Groq is never allowed to create project facts. If no key exists or provider fails,
    callers must fall back to deterministic knowledge output.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or not enabled():
        raise AIUnavailable("groq_disabled_or_missing")

    safe_context = redact(verified_context)
    safe_user = redact(user_message)
    system = (
        "You are the CryptoAID response synthesizer. Use ONLY the verified context supplied. "
        "Never invent links, partners, contracts, recovery paths, payment states or guarantees. "
        "Never request or repeat seed phrases, private keys, passwords or 2FA codes. "
        "If the context is insufficient, say that verification or human support is required. "
        f"Reply in {'Italian' if language == 'it' else 'English'}."
    )
    payload = {
        "model": DEFAULT_MODEL,
        "temperature": 0.2,
        "max_tokens": 700,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"VERIFIED CONTEXT:\n{safe_context}\n\nUSER:\n{safe_user}"},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    timeout = httpx.Timeout(8.0, connect=4.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(GROQ_URL, headers=headers, content=json.dumps(payload))
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        raise AIUnavailable(type(exc).__name__) from exc
    if not text:
        raise AIUnavailable("empty_response")
    return AIResponse(text=text, provider="groq", model=DEFAULT_MODEL)
