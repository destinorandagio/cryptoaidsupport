import pytest

from bot.support_mvp import RateLimiter, SupportRejected, build_case_support_request, contains_secret


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
