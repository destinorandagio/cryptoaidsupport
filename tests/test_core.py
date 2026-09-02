import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"bot"))
from moderation import classify_message
from content_engine import fingerprint


def test_high_risk_seed_request(): assert classify_message("Send me your seed phrase for support")["level"] >= 4
def test_normal_message_allowed(): assert classify_message("Can you explain Polygon gas fees?")["level"] == 0
def test_shortener_warns(): assert classify_message("check https://bit.ly/example")["level"] >= 2
def test_fingerprint_stable(): assert fingerprint("abc") == fingerprint("abc")
def test_content_valid():
    data=json.loads((ROOT/"content"/"evergreen.json").read_text())
    assert len(data)>=6
    ids=[x["id"] for x in data]
    assert len(ids)==len(set(ids))
    for item in data:
        assert item["destination"] in {"group","channel"}
        assert item["text"].strip()
