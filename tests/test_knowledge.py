from bot.knowledge_engine import answer, detect_language


def test_language_detection():
    assert detect_language("Come funziona CryptoAID?") == "it"
    assert detect_language("What is CryptoAID?") == "en"


def test_about_it():
    text, confidence, source = answer("Cos'è CryptoAID?", "it")
    assert "CryptoAID" in text
    assert confidence >= 0.28
    assert source in {"master", "faq"}


def test_security_en():
    text, confidence, _ = answer("Should I share my seed phrase with support?", "en")
    assert "seed" in text.lower()
    assert confidence >= 0.28


def test_unknown_escalates():
    text, confidence, source = answer("What is the verified launch date of feature XYZ-NEVER-SEEN?", "en")
    assert confidence == 0.0
    assert source == "escalation"
    assert "human admin" in text.lower()
