from bot.community_guard import classify_url, inspect


def test_official_and_external_url_classification():
    assert classify_url("https://cryptoaid.support") == "OFFICIAL"
    assert classify_url("https://t.me/cryptoaidsup") == "TELEGRAM"
    assert classify_url("https://bit.ly/x") == "SHORTENER"
    assert classify_url("https://example.com") == "EXTERNAL"


def test_secret_and_guarantee_language_triggers_review():
    assert inspect("send me your seed phrase").action == "WARN_AND_REVIEW"
    assert inspect("guaranteed recovery, DM me").level == 4


def test_shortener_warns_without_auto_ban():
    d=inspect("look https://bit.ly/example")
    assert d.action == "WARN"
    assert d.level == 2


def test_admin_does_not_bypass_secret_safety():
    assert inspect("private key", is_admin=True).level == 4


def test_clean_discussion_is_allowed():
    assert inspect("How do I verify a transaction hash?").action == "ALLOW"
