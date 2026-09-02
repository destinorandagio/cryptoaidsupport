"""Privacy-minimal acquisition event model.
Stores event type and coarse context only; never message bodies or wallet secrets.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib

ALLOWED_EVENTS = {
    "bot_start", "group_join", "question", "security_question", "scam_question",
    "recovery_question", "checklist_request", "case_command", "evidence_supplied",
    "case_started", "case_completed", "paid_case", "referral", "poll_vote",
    "channel_cta", "site_visit"
}

@dataclass(frozen=True)
class Event:
    event: str
    subject: str
    source: str
    timestamp: str
    campaign: str = ""


def pseudonymize(value: str, salt: str = "cryptoaid-public-analytics-v1") -> str:
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:20]


def make_event(event: str, subject_id: str, source: str, campaign: str = "") -> dict:
    if event not in ALLOWED_EVENTS:
        raise ValueError("unsupported event")
    if not subject_id:
        raise ValueError("subject_id required")
    return asdict(Event(
        event=event,
        subject=pseudonymize(str(subject_id)),
        source=source[:40],
        timestamp=datetime.now(timezone.utc).isoformat(),
        campaign=campaign[:80],
    ))
