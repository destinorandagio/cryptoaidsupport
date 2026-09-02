"""CHAT07 Telegram outbound rate safety policy.

This is a conservative local guard for the free Bot API envelope. It does not
create identity, Case, Evidence, payment, or durable notification authority.
The policy applies a per-user abuse limit plus per-chat minute and burst limits
before a user-triggered reply is emitted.
"""
from __future__ import annotations

from collections import defaultdict, deque
import time


class TelegramRateGate:
    """Atomic in-memory multi-scope gate for user-triggered Telegram replies.

    Defaults stay below Telegram's documented group ceiling of 20 messages/minute
    and its guidance to avoid more than one message/second in a single chat.
    The gate is intentionally stricter than the upstream limits.
    """

    def __init__(
        self,
        *,
        user_limit: int = 6,
        chat_limit: int = 18,
        minute_window_seconds: int = 60,
        burst_limit: int = 1,
        burst_window_seconds: float = 1.0,
    ) -> None:
        if min(user_limit, chat_limit, minute_window_seconds, burst_limit) < 1:
            raise ValueError("invalid_rate_limit")
        if burst_window_seconds <= 0:
            raise ValueError("invalid_rate_limit")
        self.user_limit = int(user_limit)
        self.chat_limit = int(chat_limit)
        self.minute_window_seconds = float(minute_window_seconds)
        self.burst_limit = int(burst_limit)
        self.burst_window_seconds = float(burst_window_seconds)
        self._user_events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._chat_events: dict[str, deque[float]] = defaultdict(deque)
        self._burst_events: dict[str, deque[float]] = defaultdict(deque)

    @staticmethod
    def _prune(events: deque[float], cutoff: float) -> None:
        while events and events[0] <= cutoff:
            events.popleft()

    def allow(self, *, chat_id: object, user_id: object, now: float | None = None) -> bool:
        """Consume one reply slot only if every scope permits it.

        Checks are performed before mutation so a denial at one scope does not burn
        capacity in another scope. This is process-local engineering protection;
        CHAT10 still owns durable/distributed transport throttling and retry receipts.
        """
        instant = time.monotonic() if now is None else float(now)
        chat_key = str(chat_id)
        user_key = (chat_key, str(user_id))
        user_events = self._user_events[user_key]
        chat_events = self._chat_events[chat_key]
        burst_events = self._burst_events[chat_key]

        self._prune(user_events, instant - self.minute_window_seconds)
        self._prune(chat_events, instant - self.minute_window_seconds)
        self._prune(burst_events, instant - self.burst_window_seconds)

        if len(user_events) >= self.user_limit:
            return False
        if len(chat_events) >= self.chat_limit:
            return False
        if len(burst_events) >= self.burst_limit:
            return False

        user_events.append(instant)
        chat_events.append(instant)
        burst_events.append(instant)
        return True
