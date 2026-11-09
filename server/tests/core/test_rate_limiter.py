import pytest

from spanport_server.core.rate_limiter import ConcurrencyLimiter, RateLimit, RateLimiter

THREE_PER_MINUTE = RateLimit(requests=3, window_seconds=60)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_allows_a_burst_up_to_the_limit_then_says_how_long_to_wait() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock)

    allowed = [limiter.acquire("user:a", THREE_PER_MINUTE) for _ in range(3)]
    refused = limiter.acquire("user:a", THREE_PER_MINUTE)

    assert allowed == [0.0, 0.0, 0.0]
    # One request comes back every 20 s (3 per minute).
    assert refused == pytest.approx(20.0)


def test_refills_smoothly_over_time() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock)
    for _ in range(3):
        limiter.acquire("user:a", THREE_PER_MINUTE)

    clock.now += 10
    too_soon = limiter.acquire("user:a", THREE_PER_MINUTE)
    clock.now += 10
    in_time = limiter.acquire("user:a", THREE_PER_MINUTE)

    assert too_soon == pytest.approx(10.0)
    assert in_time == 0.0


def test_never_saves_up_more_than_the_limit() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock)
    limiter.acquire("user:a", THREE_PER_MINUTE)

    clock.now += 3600
    results = [limiter.acquire("user:a", THREE_PER_MINUTE) for _ in range(4)]

    assert results[:3] == [0.0, 0.0, 0.0]
    assert results[3] > 0


def test_each_key_has_its_own_bucket() -> None:
    limiter = RateLimiter(FakeClock())
    for _ in range(3):
        limiter.acquire("user:a", THREE_PER_MINUTE)

    assert limiter.acquire("user:a", THREE_PER_MINUTE) > 0
    assert limiter.acquire("user:b", THREE_PER_MINUTE) == 0.0


def test_forgets_the_least_recently_seen_key_beyond_its_size() -> None:
    limiter = RateLimiter(FakeClock(), max_buckets=2)
    for _ in range(3):
        limiter.acquire("user:a", THREE_PER_MINUTE)
    limiter.acquire("user:b", THREE_PER_MINUTE)
    limiter.acquire("user:c", THREE_PER_MINUTE)

    # "a" was dropped to make room, so it starts full again.
    assert limiter.acquire("user:a", THREE_PER_MINUTE) == 0.0


def test_concurrency_slots_up_to_the_limit_and_back_on_release() -> None:
    slots = ConcurrencyLimiter(FakeClock())

    first = slots.acquire("tail:a", 2, lease_seconds=60)
    second = slots.acquire("tail:a", 2, lease_seconds=60)
    third = slots.acquire("tail:a", 2, lease_seconds=60)
    other_caller = slots.acquire("tail:b", 2, lease_seconds=60)
    assert first is not None
    slots.release(first)
    slots.release(first)
    after_release = slots.acquire("tail:a", 2, lease_seconds=60)

    assert second is not None
    assert third is None
    assert other_caller is not None
    assert after_release is not None


def test_a_slot_never_released_frees_itself_when_its_lease_ends() -> None:
    clock = FakeClock()
    slots = ConcurrencyLimiter(clock)
    assert slots.acquire("export:a", 1, lease_seconds=60) is not None

    still_held = slots.acquire("export:a", 1, lease_seconds=60)
    clock.now += 61
    expired = slots.acquire("export:a", 1, lease_seconds=60)

    assert still_held is None
    assert expired is not None
