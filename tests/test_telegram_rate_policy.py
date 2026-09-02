from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from bot.telegram_rate_policy import TelegramRateGate


def test_burst_limit_is_per_chat_and_atomic():
    gate = TelegramRateGate(user_limit=6, chat_limit=18)
    assert gate.allow(chat_id=100, user_id=1, now=0.0)
    assert not gate.allow(chat_id=100, user_id=2, now=0.5)
    # The denied attempt must not burn user 2's minute budget.
    assert gate.allow(chat_id=100, user_id=2, now=1.01)


def test_concurrent_same_chat_same_instant_has_exactly_one_burst_winner():
    gate = TelegramRateGate(user_limit=100, chat_limit=100, burst_limit=1)
    workers = 32
    barrier = Barrier(workers)

    def attempt(user_id):
        barrier.wait()
        return gate.allow(chat_id=-999, user_id=user_id, now=100.0)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(attempt, range(workers)))

    assert sum(results) == 1


def test_concurrent_different_chats_are_independent():
    gate = TelegramRateGate(user_limit=100, chat_limit=100, burst_limit=1)
    workers = 16
    barrier = Barrier(workers)

    def attempt(index):
        barrier.wait()
        return gate.allow(chat_id=f"chat-{index}", user_id=index, now=200.0)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(attempt, range(workers)))

    assert all(results)


def test_per_user_minute_limit_fails_closed():
    gate = TelegramRateGate(user_limit=6, chat_limit=18)
    for index in range(6):
        assert gate.allow(chat_id=200, user_id=7, now=index * 1.01)
    assert not gate.allow(chat_id=200, user_id=7, now=6.06)
    assert gate.allow(chat_id=200, user_id=8, now=6.06)


def test_per_chat_minute_limit_stays_below_telegram_group_ceiling():
    gate = TelegramRateGate(user_limit=30, chat_limit=18)
    for index in range(18):
        assert gate.allow(chat_id=-300, user_id=index, now=index * 1.01)
    assert not gate.allow(chat_id=-300, user_id=99, now=18.18)


def test_minute_capacity_recovers_after_window():
    gate = TelegramRateGate(user_limit=2, chat_limit=2)
    assert gate.allow(chat_id=400, user_id=1, now=0.0)
    assert gate.allow(chat_id=400, user_id=1, now=1.01)
    assert not gate.allow(chat_id=400, user_id=1, now=2.02)
    assert gate.allow(chat_id=400, user_id=1, now=61.02)


def test_invalid_limits_are_rejected():
    for kwargs in (
        {"user_limit": 0},
        {"chat_limit": 0},
        {"minute_window_seconds": 0},
        {"burst_limit": 0},
        {"burst_window_seconds": 0},
    ):
        try:
            TelegramRateGate(**kwargs)
        except ValueError as exc:
            assert str(exc) == "invalid_rate_limit"
        else:
            raise AssertionError(f"expected invalid_rate_limit for {kwargs}")
