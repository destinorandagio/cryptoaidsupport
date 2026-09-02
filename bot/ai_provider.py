"""CryptoAID optional AI provider layer.

External AI is an optional synthesis accelerator, never a source of truth.
The 48H MVP keeps it explicit-opt-in and fails closed before network I/O when
user text looks secret, private, identifying, or Case/evidence-like.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import httpx

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_SECRET_TERM_RE = re.compile(
    r"\b(seed\s*phrase|mnemonic|private\s*key|secret\s*key|password|passphrase|2fa|otp|one[- ]time\s+code)\b",
    re.I,
)
_RAW_PRIVATE_KEY_RE = re.compile(r"\b(?:0x)?[0-9a-fA-F]{64}\b")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d .()\/-]{7,}\d(?!\w)")
_WALLET_RE = re.compile(r"\b0x[0-9a-fA-F]{40}\b")
_URL_RE = re.compile(r"https?://\S+", re.I)
_CASE_LIKE_RE = re.compile(
    r"\b(case|incident|evidence|scam(?:med)?|hack(?:ed)?|stolen|"
    r"lost\s+(?:funds|crypto|tokens?)|transaction\s+hash|tx\s+hash|"
    r"recovery\s+(?:case|request))\b",
    re.I,
)
_WORD_RE = re.compile(r"[A-Za-z]+")
_MNEMONIC_LENGTHS = {12, 15, 18, 21, 24}


class AIUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class AIResponse:
    text: str
    provider: str
    model: str


def _looks_like_mnemonic(text: str) -> bool:
    """Conservative fail-closed detector for unlabeled mnemonic-like input.

    It intentionally prefers false positives over forwarding a plausible wallet seed
    to an external provider. Deterministic Knowledge remains available as fallback.
    """
    value = (text or "").strip()
    words = _WORD_RE.findall(value)
    if len(words) not in _MNEMONIC_LENGTHS:
        return False
    non_words = _WORD_RE.sub("", value)
    return not re.search(r"[^\s,;:-]", non_words)


def external_ai_safe_user_message(text: str) -> bool:
    """Return True only for short, generic, non-identifying/non-Case user text."""
    value = (text or "").strip()
    if not value or len(value) > 500:
        return False
    if _SECRET_TERM_RE.search(value) or _RAW_PRIVATE_KEY_RE.search(value):
        return False
    if _looks_like_mnemonic(value):
        return False
    if _EMAIL_RE.search(value) or _PHONE_RE.search(value):
        return False
    if _WALLET_RE.search(value) or _URL_RE.search(value):
        return False
    if _CASE_LIKE_RE.search(value):
        return False
    return True


def redact(text: str) -> str:
    """Defense-in-depth redaction for verified context and allowed generic text."""
    value = text or ""
    for pattern in (_RAW_PRIVATE_KEY_RE, _EMAIL_RE, _PHONE_RE, _WALLET_RE):
        value = pattern.sub("[REDACTED]", value)
    value = _SECRET_TERM_RE.sub("[REDACTED]", value)
    return value[:6000]


def enabled() -> bool:
    """External AI is disabled unless operators explicitly opt in and provide a key."""
    return bool(os.getenv("GROQ_API_KEY")) and os.getenv("AI_ENABLED", "false").lower() == "true"


async def synthesize(*, verified_context: str, user_message: str, language: str = "en") -> AIResponse:
    """Synthesize strictly from verified context, with fail-closed privacy gate."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or not enabled():
        raise AIUnavailable("groq_disabled_or_missing")
    if not external_ai_safe_user_message(user_message):
        raise AIUnavailable("sensitive_or_case_like_input")

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
