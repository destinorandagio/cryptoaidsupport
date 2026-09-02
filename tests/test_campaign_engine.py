import pytest
from bot.campaign_engine import Campaign, validate_campaign, next_funnel_step, growth_cta, weekly_report


def test_campaign_validation_and_states():
    c=Campaign("welcome-001","Welcome","Grow community","new users","en","channel","Join the community",status="READY")
    assert validate_campaign(c).status=="READY"
    with pytest.raises(ValueError,match="invalid_campaign_state"):
        validate_campaign(Campaign("x","x","x","x","en","channel","x",status="BROKEN"))


def test_prohibited_recovery_claims_fail_closed():
    with pytest.raises(ValueError,match="prohibited_claim"):
        validate_campaign(Campaign("x","Guaranteed recovery","recovery","users","en","channel","Join"))


def test_growth_funnel_is_deterministic():
    assert next_funnel_step("DISCOVERY")=="CHANNEL"
    assert next_funnel_step("RETENTION")=="ADVOCACY"
    assert next_funnel_step("ADVOCACY")=="ADVOCACY"
    assert next_funnel_step("nonsense")=="DISCOVERY"


def test_ctas_are_official_and_bilingual():
    en,url=growth_cta("CHANNEL","en")
    it,url_it=growth_cta("CHANNEL","it")
    assert "community" in en.lower()
    assert "community" in it.lower()
    assert url==url_it=="https://t.me/cryptoAIDsupporter"


def test_weekly_report_never_invents_unknown_metrics():
    r=weekly_report({"posts_published":12,"new_members":5,"fake_reach":999999})
    assert r["metrics"]["posts_published"]==12
    assert r["metrics"]["new_members"]==5
    assert "fake_reach" not in r["metrics"]
