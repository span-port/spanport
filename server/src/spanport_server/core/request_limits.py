"""Rate limits on /api/v1: which limit a request falls under and who it is counted against.

Signed-in people and admin keys are counted per caller once authenticated (dependencies.py
calls `limit_caller`); the routes open without signing in are counted per client address
(`limit_public_routes`, an app-wide dependency). Health checks and OTLP ingest are never limited.
"""

import ipaddress
import logging
import math
from dataclasses import dataclass

from fastapi import FastAPI, Request

from spanport_server.core.config import Settings
from spanport_server.core.constants import (
    ADDRESS_RATE_KEY,
    ALERT_TEST_RULE_DETAIL,
    ALERT_TEST_RULE_INTERVAL_SECONDS,
    ALERT_TEST_RULE_RATE_KEY,
    ALERT_TEST_USER_RATE_KEY,
    ALERT_TESTS_PER_DAY_DETAIL,
    API_PATH_PREFIX,
    DEFAULT_ALERT_TESTS_PER_DAY,
    DEFAULT_MAX_EXPORTS_PER_CALLER,
    DEFAULT_MAX_TAILS_PER_CALLER,
    DEFAULT_RATE_LIMIT_EXPENSIVE_PER_MINUTE,
    DEFAULT_RATE_LIMIT_PER_MINUTE,
    DEFAULT_RATE_LIMIT_PUBLIC_PER_MINUTE,
    DEFAULT_TAIL_MAX_MINUTES,
    EXPENSIVE_PATHS,
    EXPENSIVE_RATE_KEY,
    PUBLIC_PATHS,
    RATE_LIMIT_WINDOW_SECONDS,
    RATE_LIMITED_DETAIL,
    REAL_IP_HEADER,
    SECONDS_PER_DAY,
    UNKNOWN_CLIENT_ADDRESS,
)
from spanport_server.core.errors import RateLimitedError
from spanport_server.core.ids import UuidV7
from spanport_server.core.rate_limiter import ConcurrencyLimiter, RateLimit, RateLimiter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApiLimits:
    """The SPANPORT_RATE_LIMIT_* and SPANPORT_TAIL_MAX_MINUTES settings."""

    per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE
    expensive_per_minute: int = DEFAULT_RATE_LIMIT_EXPENSIVE_PER_MINUTE
    public_per_minute: int = DEFAULT_RATE_LIMIT_PUBLIC_PER_MINUTE
    alert_tests_per_day: int = DEFAULT_ALERT_TESTS_PER_DAY
    concurrent_tails: int = DEFAULT_MAX_TAILS_PER_CALLER
    concurrent_exports: int = DEFAULT_MAX_EXPORTS_PER_CALLER
    tail_max_minutes: int = DEFAULT_TAIL_MAX_MINUTES


def api_limits(settings: Settings) -> ApiLimits:
    """The API limits from the server's settings."""
    return ApiLimits(
        per_minute=settings.rate_limit_per_minute,
        expensive_per_minute=settings.rate_limit_expensive_per_minute,
        public_per_minute=settings.rate_limit_public_per_minute,
        alert_tests_per_day=settings.rate_limit_alert_tests_per_day,
        concurrent_tails=settings.rate_limit_concurrent_tails,
        concurrent_exports=settings.rate_limit_concurrent_exports,
        tail_max_minutes=settings.tail_max_minutes,
    )


def install_rate_limits(app: FastAPI) -> None:
    """Give the app its limiters, with the default limits until start-up reads the settings.

    One limiter per app, so each test's app starts with empty counts.
    """
    app.state.rate_limiter = RateLimiter()
    app.state.stream_slots = ConcurrencyLimiter()
    app.state.api_limits = ApiLimits()


def per_minute(requests: int) -> RateLimit:
    """`requests` per minute."""
    return RateLimit(requests=requests, window_seconds=RATE_LIMIT_WINDOW_SECONDS)


def enforce(
    request: Request, key: str, limit: RateLimit, detail: str = RATE_LIMITED_DETAIL
) -> None:
    """Count one request against `key`.

    Args:
        request: The request (its app holds the limiter).
        key: Who is counted, e.g. "user:<id>".
        limit: The limit for this kind of request.
        detail: The message, with `{seconds}` for the wait.

    Raises:
        RateLimitedError: Over the limit (429 with Retry-After).
    """
    limiter: RateLimiter = request.app.state.rate_limiter
    wait_seconds = math.ceil(limiter.acquire(key, limit))
    if wait_seconds == 0:
        return
    logger.warning(
        "rate limited method=%s path=%s retry_after_s=%d",
        request.method,
        request.url.path,
        wait_seconds,
    )
    raise RateLimitedError(detail.format(seconds=wait_seconds), retry_after_seconds=wait_seconds)


def limit_caller(request: Request, caller_key: str) -> None:
    """Count an authenticated /api/v1 request against its caller: routes that run large queries
    have their own, lower limit. Requests outside /api/v1 (OTLP ingest) are never counted.

    Raises:
        RateLimitedError: Over the limit.
    """
    path = request.url.path
    if not path.startswith(API_PATH_PREFIX):
        return
    limits: ApiLimits = request.app.state.api_limits
    if path in EXPENSIVE_PATHS:
        key = EXPENSIVE_RATE_KEY.format(caller=caller_key)
        enforce(request, key, per_minute(limits.expensive_per_minute))
        return
    enforce(request, caller_key, per_minute(limits.per_minute))


def client_address(request: Request) -> str:
    """The address a request came from.

    The server's port is published on 127.0.0.1 only, so browsers reach it through nginx (the UI
    container), which sets X-Real-IP from the connection it accepted (a browser can't choose
    it). The header is believed only from a private-network peer such as nginx on the Docker
    network; from any other peer the connection's own address counts.
    """
    peer = request.client.host if request.client else UNKNOWN_CLIENT_ADDRESS
    forwarded = request.headers.get(REAL_IP_HEADER)
    if forwarded and is_private_address(peer):
        return forwarded
    return peer


def is_private_address(address: str) -> bool:
    """Whether the address is loopback or on a private network (not a hostname)."""
    try:
        return ipaddress.ip_address(address).is_private
    except ValueError:
        return False


async def limit_public_routes(request: Request) -> None:
    """App-wide dependency: count setup, sign-in and invite-link requests per client address.

    Raises:
        RateLimitedError: Over the limit.
    """
    if request.url.path not in PUBLIC_PATHS:
        return
    limits: ApiLimits = request.app.state.api_limits
    key = ADDRESS_RATE_KEY.format(address=client_address(request))
    enforce(request, key, per_minute(limits.public_per_minute))


def limit_alert_test(request: Request, rule_id: UuidV7, user_id: UuidV7 | None) -> None:
    """A rule's test email at most once a minute, and a daily cap per person.

    Raises:
        RateLimitedError: Tested too recently, or too many tests today.
    """
    once_a_minute = RateLimit(requests=1, window_seconds=ALERT_TEST_RULE_INTERVAL_SECONDS)
    enforce(
        request,
        ALERT_TEST_RULE_RATE_KEY.format(rule_id=rule_id),
        once_a_minute,
        ALERT_TEST_RULE_DETAIL,
    )
    limits: ApiLimits = request.app.state.api_limits
    per_day = RateLimit(requests=limits.alert_tests_per_day, window_seconds=SECONDS_PER_DAY)
    enforce(
        request,
        ALERT_TEST_USER_RATE_KEY.format(user_id=user_id),
        per_day,
        ALERT_TESTS_PER_DAY_DETAIL.format(limit=limits.alert_tests_per_day),
    )
