from bot.acquisition_engine import assess, stage_for
from bot.event_tracking import make_event
from bot.lead_magnets import route
from bot.poll_engine import choose
from bot.preassessment import PreAssessment, completeness, contains_secret


def test_telegram_signal_scoring_advances_stage():
    x = assess("I lost funds in a scam and I have the transaction hash", ["case_command", "evidence_supplied"])
    assert x.case_intent
    assert x.evidence_signal
    assert x.stage in {"case_ready", "customer"}


def test_wallet_secret_language_is_blocked():
    assert contains_secret("my mnemonic is ...")
    assert assess("here is my private key", []).safety_risk


def test_lead_magnet_router_is_contextual():
    assert route("dead token project", "en")["id"] == "dead-token-survival-guide"
    assert route("rug pull", "it")["id"] == "rug-pull-evidence-checklist"


def test_preassessment_qualifies_only_with_public_evidence():
    incomplete = PreAssessment(project="Example", incident="site disappeared", chain="Polygon")
    assert not completeness(incomplete)["qualified"]
    complete = PreAssessment(project="Example", incident="site disappeared", chain="Polygon", public_tx_hash="0xabc")
    assert completeness(complete)["qualified"]


def test_tracking_is_pseudonymous_and_content_free():
    event = make_event("bot_start", "123456", "telegram_bot")
    assert event["subject"] != "123456"
    assert "text" not in event and "message" not in event


def test_poll_factory_is_bilingual():
    assert choose("en", seed=0).language == "en"
    assert choose("it", seed=0).language == "it"


def test_stage_thresholds_are_stable():
    assert stage_for(0) == "cold"
    assert stage_for(3) == "aware"
    assert stage_for(10) == "engaged"
    assert stage_for(20) == "problem_aware"
    assert stage_for(35) == "case_ready"
    assert stage_for(60) == "customer"
