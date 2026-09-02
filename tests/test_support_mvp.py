import json

import pytest

from bot.support_mvp import (
    RateLimiter,
    SupportRejected,
    build_case_support_request,
    contains_secret,
    load_official_links,
    render_official_links,
)


def test_case_support_requires_owner_and_never_accepts_secrets():
    with pytest.raises(SupportRejected, match="unauthorized_case_support"):
        build_case_support_request(case_id="CASE-1", summary="Need status help", category="STATUS", requester_is_case_owner=False)

    for text in ("my seed phrase is alpha beta", "private key 0x" + "a" * 64, "password is hunter2", "OTP 123456"):
        assert contains_secret(text)
        with pytest.raises(SupportRejected, match="secret_or_credential_detected"):
            build_case_support_request(case_id="CASE-1", summary=text, category="GENERAL", requester_is_case_owner=True)


def test_case_support_is_ephemeral_minimized_command():
    request = build_case_support_request(
        case_id="CASE-123",
        summary="Payment is still under manual review; please escalate status only.",
        category="PAYMENT_STATUS",
        requester_is_case_owner=True,
        escalate=True,
    )
    assert request.case_id == "CASE-123"
    assert request.category == "PAYMENT_STATUS"
    assert request.escalate is True
    assert not hasattr(request, "evidence")
    assert not hasattr(request, "sic_id")


def test_rate_limiter_fails_closed_at_limit_and_recovers_after_window():
    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("tg-user", now=100.0)
    assert limiter.allow("tg-user", now=101.0)
    assert not limiter.allow("tg-user", now=102.0)
    assert limiter.allow("tg-user", now=161.1)


def test_official_links_are_loaded_from_verified_registry_and_rendered():
    links = load_official_links()
    assert links["status"] == "VERIFIED"
    assert links["website"] == "https://cryptoaid.support"
    assert links["telegram"]["bot"] == "@CryptoAIDsupportBOT"
    rendered = render_official_links("en")
    assert "https://cryptoaid.support" in rendered
    assert "https://t.me/cryptoAIDsupporter" in rendered
    assert "https://t.me/cryptoaidsup" in rendered


def test_official_links_fail_closed_on_unverified_or_wrong_telegram_domain(tmp_path):
    candidate = {
        "status": "UNVERIFIED",
        "website": "https://cryptoaid.support",
        "telegram": {"bot": "@CryptoAIDsupportBOT", "group": "https://t.me/cryptoAIDsupporter", "channel": "https://t.me/cryptoaidsup"},
        "github": "https://github.com/destinorandagio/cryptoaidsupport",
    }
    path = tmp_path / "links.json"
    path.write_text(json.dumps(candidate), encoding="utf-8")
    with pytest.raises(SupportRejected, match="official_links_not_verified"):
        load_official_links(path)

    candidate["status"] = "VERIFIED"
    candidate["telegram"]["group"] = "https://example.com/fake-group"
    path.write_text(json.dumps(candidate), encoding="utf-8")
    with pytest.raises(SupportRejected, match="invalid_official_telegram_link"):
        load_official_links(path)
