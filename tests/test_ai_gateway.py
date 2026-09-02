import os

import pytest

from bot import ai_gateway


def test_provider_inventory_never_exposes_values(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "secret-a")
    monkeypatch.setenv("GROQ_API_KEY_01", "secret-b")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-c")
    inventory = ai_gateway.provider_inventory()
    assert inventory["groq"] == 2
    assert inventory["openai"] == 1
    assert "secret-a" not in repr(inventory)
    assert "secret-b" not in repr(inventory)
    assert "secret-c" not in repr(inventory)


def test_gateway_disabled_without_keys(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    for spec in ai_gateway.PROVIDERS:
        for key in spec.env_keys:
            monkeypatch.delenv(key, raising=False)
    assert ai_gateway.enabled() is False


def test_gateway_enabled_with_one_provider(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert ai_gateway.enabled() is True


@pytest.mark.asyncio
async def test_failover_uses_second_provider(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    calls = []

    async def fake_call(spec, key, model, system, body):
        calls.append(spec.name)
        if spec.name == "groq":
            raise RuntimeError("quota")
        return "grounded response"

    monkeypatch.setattr(ai_gateway, "_call", fake_call)
    result = await ai_gateway.synthesize(
        verified_context="verified facts only",
        user_message="question",
        language="en",
    )
    assert result.provider == "openai"
    assert result.text == "grounded response"
    assert calls[:2] == ["groq", "openai"]
