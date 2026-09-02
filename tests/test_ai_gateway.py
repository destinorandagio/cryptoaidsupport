import pytest

from bot import ai_gateway
from bot.ai_provider import AIUnavailable


def clear_provider_keys(monkeypatch):
    for spec in ai_gateway.PROVIDERS:
        for key in spec.env_keys:
            monkeypatch.delenv(key, raising=False)


def test_provider_inventory_never_exposes_values(monkeypatch):
    clear_provider_keys(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "secret-a")
    monkeypatch.setenv("GROQ_API_KEY_01", "secret-b")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-c")
    inventory = ai_gateway.provider_inventory()
    assert inventory["groq"] == 2
    assert inventory["openai"] == 1
    assert "secret-a" not in repr(inventory)
    assert "secret-b" not in repr(inventory)
    assert "secret-c" not in repr(inventory)


def test_gateway_is_explicit_opt_in_even_with_keys(monkeypatch):
    clear_provider_keys(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.delenv("AI_ENABLED", raising=False)
    assert ai_gateway.enabled() is False
    monkeypatch.setenv("AI_ENABLED", "true")
    assert ai_gateway.enabled() is True


def test_gateway_disabled_without_keys(monkeypatch):
    clear_provider_keys(monkeypatch)
    monkeypatch.setenv("AI_ENABLED", "true")
    assert ai_gateway.enabled() is False


@pytest.mark.asyncio
async def test_sensitive_input_rejected_before_provider_call(monkeypatch):
    clear_provider_keys(monkeypatch)
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    called = False

    async def fake_call(*args, **kwargs):
        nonlocal called
        called = True
        return "should-not-run"

    monkeypatch.setattr(ai_gateway, "_call", fake_call)
    with pytest.raises(AIUnavailable, match="sensitive_or_case_like_input"):
        await ai_gateway.synthesize(
            verified_context="verified facts",
            user_message="My recovery case is linked to alice@example.com",
            language="en",
        )
    assert called is False


@pytest.mark.asyncio
async def test_mnemonic_like_input_rejected_before_provider_call(monkeypatch):
    clear_provider_keys(monkeypatch)
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    called = False

    async def fake_call(*args, **kwargs):
        nonlocal called
        called = True
        return "should-not-run"

    monkeypatch.setattr(ai_gateway, "_call", fake_call)
    with pytest.raises(AIUnavailable, match="sensitive_or_case_like_input"):
        await ai_gateway.synthesize(
            verified_context="verified facts",
            user_message="abandon ability able about above absent absorb abstract absurd abuse access accident",
            language="en",
        )
    assert called is False


@pytest.mark.asyncio
async def test_failover_uses_second_provider_for_generic_opt_in(monkeypatch):
    clear_provider_keys(monkeypatch)
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
        user_message="What is CryptoAID?",
        language="en",
    )
    assert result.provider == "openai"
    assert result.text == "grounded response"
    assert calls[:2] == ["groq", "openai"]
