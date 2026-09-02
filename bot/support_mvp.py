"""CHAT07 minimum support safety boundary.

Pure, stateless guards only. This module does not own Case truth, Evidence bytes,
SIC-ID authority, payment truth, or a support database. A trusted upstream adapter
must supply the Case ownership verdict before a Case-linked request is accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import time
from collections import defaultdict, deque

_SECRET_PATTERNS = (
    re.compile(r"\b(seed\s*phrase|mnemonic|private\s*key|secret\s*key)\b", re.I),
    re.compile(r"\b(password|passphrase|2fa|otp|one[- ]time\s+code)\b", re.I),
    re.compile(r"\b(?:0x)?[0-9a-f]{64}\b", re.I),
)


class SupportRejected(ValueError):
    """Fail-closed rejection for unsafe/unauthorized support input."""


@dataclass(frozen=True)
class SupportRequest:
    case_id: str
    category: str
    summary: str
    escalate: bool


def contains_secret(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in _SECRET_PATTERNS)


def build_case_support_request(
    *,
    case_id: str,
    summary: str,
    category: str,
    requester_is_case_owner: bool,
    escalate: bool = False,
) -> SupportRequest:
    """Create an ephemeral support command only after upstream ownership auth.

    No Evidence payload is accepted here. The returned object is suitable for an
    owner API/command adapter; this module intentionally persists nothing.
    """
    case_id = (case_id or "").strip()
    summary = (summary or "").strip()
    category = (category or "GENERAL").strip().upper()
    if not requester_is_case_owner:
        raise SupportRejected("unauthorized_case_support")
    if not case_id or len(case_id) > 128:
        raise SupportRejected("invalid_case_id")
    if not summary or len(summary) > 1200:
        raise SupportRejected("invalid_summary")
    if contains_secret(summary):
        raise SupportRejected("secret_or_credential_detected")
    return SupportRequest(case_id=case_id, category=category, summary=summary, escalate=bool(escalate))


class RateLimiter:
    """Small in-memory anti-abuse guard; no identity/support authority is stored."""

    def __init__(self, limit: int = 6, window_seconds: int = 60):
        if limit < 1 or window_seconds < 1:
            raise ValueError("invalid_rate_limit")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else float(now)
        events = self._events[str(key)]
        cutoff = now - self.window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= self.limit:
            return False
        events.append(now)
        return True
