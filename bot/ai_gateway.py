"""CryptoAID multi-provider AI gateway.

Server-side only. Providers are synthesis accelerators, never authorities.
Keys are read from environment variables only. No provider is required for
CryptoAID to answer: callers must retain deterministic knowledge fallback.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Iterable

import httpx

from .ai_provider import AIResponse, AIUnavailable, redact


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    env_keys: tuple[str, ...]
    url: str
    model_env: str
    default_model: str
    protocol: str = "openai"
    priority: int = 100


@dataclass
class ProviderHealth:
    successes: int = 0
    failures: int = 0
    last_failure_at: float = 0.0

    @property
    def score(self) -> float:
        total = self.successes + self.failures
        if total == 0:
            return 1.0
        return max(0.05, self.successes / total)


PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        name="groq",
        env_keys=("GROQ_API_KEY", "GROQ_API_KEY_01", "GROQ_API_KEY_02", "GROQ_API_KEY_03", "GROQ_API_KEY_04", "GROQ_API_KEY_05", "GROQ_API_KEY_06", "GROQ_API_KEY_07", "GROQ_API_KEY_08", "GROQ_API_KEY_09", "GROQ_API_KEY_10"),
        url="https://api.groq.com/openai/v1/chat/completions",
        model_env="GROQ_MODEL",
        default_model="llama-3.1-8b-instant",
        priority=10,
    ),
    ProviderSpec(
        name="openai",
        env_keys=("OPENAI_API_KEY",),
        url="https://api.openai.com/v1/chat/completions",
        model_env="OPENAI_MODEL",
        default_model="gpt-4.1-mini",
        priority=20,
    ),
    ProviderSpec(
        name="cerebras",
        env_keys=("CEREBRAS_API_KEY",),
        url="https://api.cerebras.ai/v1/chat/completions",
        model_env="CEREBRAS_MODEL",
        default_model="llama3.1-8b",
        priority=30,
    ),
    ProviderSpec(
        name="anthropic",
        env_keys=("ANTHROPIC_API_KEY",),
        url="https://api.anthropic.com/v1/messages",
        model_env="ANTHROPIC_MODEL",
        default_model="claude-3-5-haiku-latest",
        protocol="anthropic",
        priority=40,
    ),
    ProviderSpec(
        name="gemini",
        env_keys=("GEMINI_API_KEY",),
        url="https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        model_env="GEMINI_MODEL",
        default_model="gemini-2.0-flash",
        protocol="gemini",
        priority=50,
    ),
)

_HEALTH: dict[str, ProviderHealth] = {p.name: ProviderHealth() for p in PROVIDERS}


def _configured_keys(spec: ProviderSpec) -> list[str]:
    return [value for name in spec.env_keys if (value := os.getenv(name))]


def provider_inventory() -> dict[str, int]:
    """Return configured key counts without exposing any key values."""
    return {spec.name: len(_configured_keys(spec)) for spec in PROVIDERS}


def enabled() -> bool:
    return os.getenv("AI_ENABLED", "true").lower() == "true" and any(provider_inventory().values())


def _ordered_specs() -> Iterable[ProviderSpec]:
    return sorted(
        (p for p in PROVIDERS if _configured_keys(p)),
        key=lambda p: (p.priority / _HEALTH[p.name].score, p.priority),
    )


def _system_prompt(language: str) -> str:
    return (
        "You are the CryptoAID response synthesizer. Use ONLY the verified context supplied. "
        "Never invent links, partners, contracts, wallet addresses, recovery paths, payment states or guarantees. "
        "Never request or repeat seed phrases, private keys, passwords, OTP or 2FA codes. "
        "If the context is insufficient, explicitly say verification or human support is required. "
        f"Reply in {'Italian' if language == 'it' else 'English'}."
    )


async def _call_openai_compatible(spec: ProviderSpec, key: str, model: str, system: str, body: str) -> str:
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 700,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": body},
        ],
    }
    timeout = httpx.Timeout(float(os.getenv("AI_TIMEOUT_SECONDS", "8")), connect=4.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(spec.url, headers=headers, content=json.dumps(payload))
        r.raise_for_status()
        data = r.json()
    return data["choices"][0]["message"]["content"].strip()


async def _call_anthropic(spec: ProviderSpec, key: str, model: str, system: str, body: str) -> str:
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {"model": model, "max_tokens": 700, "temperature": 0.2, "system": system, "messages": [{"role": "user", "content": body}]}
    timeout = httpx.Timeout(float(os.getenv("AI_TIMEOUT_SECONDS", "8")), connect=4.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(spec.url, headers=headers, content=json.dumps(payload))
        r.raise_for_status()
        data = r.json()
    return "".join(part.get("text", "") for part in data.get("content", []) if part.get("type") == "text").strip()


async def _call_gemini(spec: ProviderSpec, key: str, model: str, system: str, body: str) -> str:
    url = spec.url.format(model=model)
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": body}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700},
    }
    timeout = httpx.Timeout(float(os.getenv("AI_TIMEOUT_SECONDS", "8")), connect=4.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, params={"key": key}, headers={"Content-Type": "application/json"}, content=json.dumps(payload))
        r.raise_for_status()
        data = r.json()
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    return "".join(part.get("text", "") for part in candidates[0].get("content", {}).get("parts", [])).strip()


async def _call(spec: ProviderSpec, key: str, model: str, system: str, body: str) -> str:
    if spec.protocol == "openai":
        return await _call_openai_compatible(spec, key, model, system, body)
    if spec.protocol == "anthropic":
        return await _call_anthropic(spec, key, model, system, body)
    if spec.protocol == "gemini":
        return await _call_gemini(spec, key, model, system, body)
    raise AIUnavailable(f"unsupported_protocol:{spec.protocol}")


async def synthesize(*, verified_context: str, user_message: str, language: str = "en") -> AIResponse:
    if not enabled():
        raise AIUnavailable("ai_gateway_disabled_or_unconfigured")

    system = _system_prompt(language)
    body = f"VERIFIED CONTEXT:\n{redact(verified_context)}\n\nUSER:\n{redact(user_message)}"
    errors: list[str] = []

    for spec in _ordered_specs():
        keys = _configured_keys(spec)
        model = os.getenv(spec.model_env, spec.default_model)
        for index, key in enumerate(keys):
            try:
                text = await _call(spec, key, model, system, body)
                if not text:
                    raise AIUnavailable("empty_response")
                _HEALTH[spec.name].successes += 1
                return AIResponse(text=text, provider=spec.name, model=model)
            except Exception as exc:  # provider/network/quota failure => fail over
                health = _HEALTH[spec.name]
                health.failures += 1
                health.last_failure_at = time.time()
                errors.append(f"{spec.name}[{index}]:{type(exc).__name__}")
                await asyncio.sleep(0)

    raise AIUnavailable("all_providers_failed:" + ",".join(errors[:8]))
