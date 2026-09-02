import os

import pytest

from bot.ai_provider import AIUnavailable, enabled, redact


def test_redact_blocks_secret_terms_and_raw_private_key_shape():
    text = "seed phrase and 0x" + "a" * 64
    out = redact(text)
    assert "seed phrase" not in out.lower()
    assert "0x" + "a" * 64 not in out
    assert "[REDACTED]" in out


def test_enabled_requires_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("AI_ENABLED", "true")
    assert not enabled()


def test_ai_can_be_disabled_even_with_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    monkeypatch.setenv("AI_ENABLED", "false")
    assert not enabled()
