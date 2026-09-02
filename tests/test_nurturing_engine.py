from bot.nurturing_engine import can_nurture, cta_url, invite_copy, touch_for_day


def test_onboarding_reaches_advocacy():
    assert touch_for_day("onboarding_7d", 0)["goal"] == "understand_cryptoaid"
    assert touch_for_day("onboarding_7d", 6)["cta"] == "INVITE_ONE_PERSON"


def test_recovery_flow_never_promises_recovery():
    text = invite_copy("it").lower()
    assert "nessuna promessa" in text
    assert "recupero garantito" not in text


def test_nurture_frequency_guard():
    assert can_nurture(touches_today=0, hours_since_last=7)
    assert not can_nurture(touches_today=2, hours_since_last=7)
    assert not can_nurture(touches_today=0, hours_since_last=2)


def test_ctas_use_official_telegram_surfaces():
    assert cta_url("JOIN_GROUP") == "https://t.me/cryptoAIDsupporter"
    assert cta_url("ASK_BOT") == "https://t.me/CryptoAIDsupportBOT"
