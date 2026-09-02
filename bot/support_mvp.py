"""CHAT07 minimum support safety boundary.

Pure, stateless guards only. This module does not own Case truth, Evidence bytes,
SIC-ID authority, payment truth, or a support database. A trusted upstream adapter
must supply the Case ownership verdict before a Case-linked request is accepted.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlparse

_SECRET_PATTERNS = (
    re.compile(r"\b(seed\s*phrase|mnemonic|private\s*key|secret\s*key)\b", re.I),
    re.compile(r"\b(password|passphrase|2fa|otp|one[- ]time\s+code)\b", re.I),
    re.compile(r"\b(?:0x)?[0-9a-f]{64}\b", re.I),
)
_OFFICIAL_LINKS_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "canonical" / "official_links.json"
_SAFE_NOTIFICATION_COPY = {
    "STATUS_CHANGED": "Your CryptoAID Case status changed. Open the official app to view the current status.",
    "ACTION_REQUIRED": "Your CryptoAID Case has a new action. Open the official app to view the next action.",
    "MANUAL_REVIEW": "Your CryptoAID Case is under human review. Open the official app for the current status.",
}


class SupportRejected(ValueError):
    """Fail-closed rejection for unsafe/unauthorized support input."""


@dataclass(frozen=True)
class SupportRequest:
    case_id: str
    category: str
    summary: str
    escalate: bool


@dataclass(frozen=True)
class SafeCaseNotification:
    """Minimized notification command for an owner-authorized transport adapter.

    It intentionally carries no Evidence, SIC-ID, wallet, payment details or free-form
    user text. ``idempotency_key`` is deterministic for the Case/event/version tuple so
    a durable transport owner can deduplicate retries without creating a CHAT07 DB.
    """

    case_id: str
    event_type: str
    case_version: int
    message: str
    idempotency_key: str


def contains_secret(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in _SECRET_PATTERNS)


def _require_https(value: str, *, telegram_only: bool = False) -> str:
    value = (value or "").strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SupportRejected("invalid_official_link")
    if telegram_only and parsed.netloc.lower() not in {"t.me", "www.t.me"}:
        raise SupportRejected("invalid_official_telegram_link")
    return value


def load_official_links(path: str | Path | None = None) -> dict:
    """Load only the version-controlled VERIFIED official-link registry.

    The command fails closed if the registry is missing, malformed, unverified or
    contains an unexpected transport/domain for Telegram links.
    """
    source = Path(path) if path is not None else _OFFICIAL_LINKS_PATH
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SupportRejected("official_links_unavailable") from exc
    if data.get("status") != "VERIFIED":
        raise SupportRejected("official_links_not_verified")
    telegram = data.get("telegram") or {}
    bot = str(telegram.get("bot") or "").strip()
    if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}", bot):
        raise SupportRejected("invalid_official_telegram_bot")
    return {
        "status": "VERIFIED",
        "website": _require_https(str(data.get("website") or "")),
        "telegram": {
            "bot": bot,
            "group": _require_https(str(telegram.get("group") or ""), telegram_only=True),
            "channel": _require_https(str(telegram.get("channel") or ""), telegram_only=True),
        },
        "github": _require_https(str(data.get("github") or "")),
    }


def render_official_links(language: str = "en", path: str | Path | None = None) -> str:
    links = load_official_links(path)
    tg = links["telegram"]
    title = "🔗 Link ufficiali CryptoAID" if language == "it" else "🔗 Official CryptoAID links"
    warning = (
        "Verifica sempre questi riferimenti prima di interagire."
        if language == "it"
        else "Always verify these references before interacting."
    )
    return "\n".join(
        [
            title,
            f"Website: {links['website']}",
            f"Telegram bot: {tg['bot']}",
            f"Telegram group: {tg['group']}",
            f"Telegram channel: {tg['channel']}",
            f"GitHub: {links['github']}",
            warning,
        ]
    )


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


def build_safe_case_notification(
    *,
    case_id: str,
    event_type: str,
    case_version: int,
    requester_is_case_owner: bool,
) -> SafeCaseNotification:
    """Build a privacy-minimized, deterministic notification command.

    CHAT07 never decides Case truth. ``event_type`` and ``case_version`` must come
    from the authoritative Case adapter, and the adapter must provide an owner verdict.
    The returned key is only a dedupe contract; durable delivery state belongs to the
    transport/infrastructure owner, not to a second CHAT07 database.
    """
    if not requester_is_case_owner:
        raise SupportRejected("unauthorized_case_notification")
    case_id = (case_id or "").strip()
    event_type = (event_type or "").strip().upper()
    if not case_id or len(case_id) > 128:
        raise SupportRejected("invalid_case_id")
    if event_type not in _SAFE_NOTIFICATION_COPY:
        raise SupportRejected("unsupported_notification_event")
    if isinstance(case_version, bool) or not isinstance(case_version, int) or case_version < 1:
        raise SupportRejected("invalid_case_version")
    canonical = f"{case_id}|{event_type}|{case_version}".encode("utf-8")
    idempotency_key = "support-notify-" + hashlib.sha256(canonical).hexdigest()
    return SafeCaseNotification(
        case_id=case_id,
        event_type=event_type,
        case_version=case_version,
        message=_SAFE_NOTIFICATION_COPY[event_type],
        idempotency_key=idempotency_key,
    )


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
