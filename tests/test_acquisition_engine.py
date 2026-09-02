import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bot"))

from acquisition_engine import assess, next_step


def test_case_intent_is_detected():
    x = assess("I lost funds in a rug pull", ["dm_reply"])
    assert x.case_intent
    assert x.score >= 20


def test_public_evidence_increases_intent():
    x = assess("Scam, I have the transaction hash", ["lead_magnet"])
    assert x.evidence_signal
    assert x.stage in {"problem_aware", "case_ready", "customer"}


def test_secrets_trigger_safety_message():
    x = assess("Here is my seed phrase", [])
    assert x.safety_risk
    assert "Never send" in next_step(x, "en")
