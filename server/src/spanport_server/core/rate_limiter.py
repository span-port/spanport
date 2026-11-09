"""In-process rate limits: token buckets for request rates, leases for concurrent streams.

Standard library only, so it can move to packages/core when the gateway needs it. Each server
process keeps its own counts (no Redis yet), so with several replicas a caller's real limit is
the per-process limit times the number of replicas.
Everything here runs on the event loop without awaiting, so no lock is needed.
"""

import itertools
import time
from collections.abc import Callable
from dataclasses import dataclass

from spanport_server.core.constants import RATE_LIMIT_MAX_BUCKETS


@dataclass(frozen=True)
class RateLimit:
    """`requests` per `window_seconds`, refilled smoothly (a burst of `requests` is allowed)."""

    requests: int
    window_seconds: float


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class RateLimiter:
    """Token buckets keyed by caller, e.g. "user:<id>" or "ip:<address>"."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        max_buckets: int = RATE_LIMIT_MAX_BUCKETS,
    ) -> None:
        """Create the limiter.

        Args:
            clock: Seconds from a monotonic clock; tests pass a fake one.
            max_buckets: How many keys to remember before dropping the least recently used.
        """
        self._clock = clock
        self._max_buckets = max_buckets
        self._buckets: dict[str, _Bucket] = {}

    def acquire(self, key: str, limit: RateLimit) -> float:
        """Take one request from the key's bucket.

        Args:
            key: Who is asking.
            limit: The limit for this kind of request.

        Returns:
            0.0 when the request may go ahead, else the seconds until it may be retried.
        """
        now = self._clock()
        refill_per_second = limit.requests / limit.window_seconds
        bucket = self._buckets.pop(key, None) or _Bucket(float(limit.requests), now)
        elapsed = now - bucket.updated_at
        bucket.tokens = min(float(limit.requests), bucket.tokens + elapsed * refill_per_second)
        bucket.updated_at = now
        # Re-inserted at the end, so the dict's order is least recently used first.
        self._buckets[key] = bucket
        self._drop_oldest()
        if bucket.tokens >= 1:
            bucket.tokens -= 1
            return 0.0
        return (1 - bucket.tokens) / refill_per_second

    def _drop_oldest(self) -> None:
        while len(self._buckets) > self._max_buckets:
            del self._buckets[next(iter(self._buckets))]


@dataclass(frozen=True)
class Lease:
    """One held slot; give it back with ConcurrencyLimiter.release."""

    key: str
    lease_id: int


class ConcurrencyLimiter:
    """Caps how many long requests (live tails, exports) one caller runs at once.

    A slot that is never released (a stream torn down before its cleanup ran) expires after its
    lease time, so a caller can't be locked out for good.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        """Create the limiter.

        Args:
            clock: Seconds from a monotonic clock; tests pass a fake one.
        """
        self._clock = clock
        self._lease_ids = itertools.count()
        # key -> lease id -> when the lease expires.
        self._leases: dict[str, dict[int, float]] = {}

    def acquire(self, key: str, limit: int, lease_seconds: float) -> Lease | None:
        """Take a slot if the key holds fewer than `limit`.

        Args:
            key: Who is asking, e.g. "tail:user:<id>".
            limit: Slots allowed at once.
            lease_seconds: How long the slot lasts if it is never released.

        Returns:
            The lease, or None when every slot is taken.
        """
        now = self._clock()
        held = {
            lease_id: expires_at
            for lease_id, expires_at in self._leases.get(key, {}).items()
            if expires_at > now
        }
        if len(held) >= limit:
            self._leases[key] = held
            return None
        lease = Lease(key, next(self._lease_ids))
        held[lease.lease_id] = now + lease_seconds
        self._leases[key] = held
        return lease

    def release(self, lease: Lease) -> None:
        """Give a slot back. Releasing twice, or after it expired, does nothing."""
        held = self._leases.get(lease.key)
        if held is None:
            return
        held.pop(lease.lease_id, None)
        if not held:
            del self._leases[lease.key]
