from bot.ai_provider import enabled, external_ai_safe_user_message, redact


def test_redact_blocks_secret_terms_private_key_and_pii():
    text = "private key 0x" + "a" * 64 + " email alice@example.com phone +39 333 1234567 wallet 0x" + "b" * 40
    out = redact(text)
    assert "private key" not in out.lower()
    assert "0x" + "a" * 64 not in out
    assert "alice@example.com" not in out
    assert "+39 333 1234567" not in out
    assert "0x" + "b" * 40 not in out
    assert "[REDACTED]" in out


def test_enabled_is_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    monkeypatch.delenv("AI_ENABLED", raising=False)
    assert not enabled()
    monkeypatch.setenv("AI_ENABLED", "true")
    assert enabled()
    monkeypatch.setenv("AI_ENABLED", "false")
    assert not enabled()


def test_enabled_requires_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("AI_ENABLED", "true")
    assert not enabled()


def test_raw_mnemonic_like_input_fails_external_ai_gate():
    phrase = "abandon ability able about above absent absorb abstract absurd abuse access accident"
    assert not external_ai_safe_user_message(phrase)


def test_case_evidence_and_identifiers_fail_external_ai_gate():
    assert not external_ai_safe_user_message("I was scammed and need a recovery case")
    assert not external_ai_safe_user_message("check https://example.invalid/path")
    assert not external_ai_safe_user_message("email me at alice@example.com")
    assert not external_ai_safe_user_message("wallet 0x" + "b" * 40)
    assert not external_ai_safe_user_message("tx 0x" + "c" * 64)


def test_short_generic_question_can_use_opt_in_ai():
    assert external_ai_safe_user_message("What is CryptoAID and how does it work?")


def test_long_or_blank_input_fails_external_ai_gate():
    assert not external_ai_safe_user_message("")
    assert not external_ai_safe_user_message("x" * 501)
