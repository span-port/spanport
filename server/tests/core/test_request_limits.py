import uuid

import pytest
from fastapi import FastAPI, Request

from spanport_server.core.errors import RateLimitedError
from spanport_server.core.request_limits import (
    ApiLimits,
    client_address,
    install_rate_limits,
    limit_alert_test,
    limit_caller,
    limit_public_routes,
)

pytestmark = pytest.mark.anyio

RULE_ID = uuid.UUID("0192f1c4-0000-7000-8000-000000000001")
USER_ID = uuid.UUID("0192f1c4-0000-7000-8000-000000000002")


def limited_app(**limits: int) -> FastAPI:
    app = FastAPI()
    install_rate_limits(app)
    app.state.api_limits = ApiLimits(**limits)
    return app


def request_to(
    app: FastAPI, path: str, peer: str = "93.184.216.34", headers: dict[str, str] | None = None
) -> Request:
    raw_headers = [
        (name.lower().encode(), value.encode()) for name, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": raw_headers,
        "client": (peer, 50000),
        "app": app,
    }
    return Request(scope)


def test_counts_each_caller_separately() -> None:
    app = limited_app(per_minute=1)

    limit_caller(request_to(app, "/api/v1/projects"), "user:a")
    limit_caller(request_to(app, "/api/v1/projects"), "user:b")
    with pytest.raises(RateLimitedError) as refused:
        limit_caller(request_to(app, "/api/v1/projects"), "user:a")

    assert refused.value.retry_after_seconds == 60
    assert refused.value.code == "rate_limited"


def test_expensive_routes_have_their_own_lower_limit() -> None:
    app = limited_app(per_minute=5, expensive_per_minute=1)

    limit_caller(request_to(app, "/api/v1/logs/search"), "user:a")
    with pytest.raises(RateLimitedError):
        limit_caller(request_to(app, "/api/v1/logs/counts"), "user:a")
    limit_caller(request_to(app, "/api/v1/projects"), "user:a")


def test_ingest_outside_api_v1_is_never_counted() -> None:
    app = limited_app(per_minute=1)

    for _ in range(5):
        limit_caller(request_to(app, "/v1/logs"), "key:a")


async def test_public_routes_are_counted_per_client_address() -> None:
    app = limited_app(public_per_minute=2)

    for _ in range(2):
        await limit_public_routes(request_to(app, "/api/v1/auth/login"))
    with pytest.raises(RateLimitedError):
        await limit_public_routes(request_to(app, "/api/v1/invites/accept"))
    await limit_public_routes(request_to(app, "/api/v1/auth/login", peer="93.184.216.35"))
    for _ in range(5):
        await limit_public_routes(request_to(app, "/health"))


def test_x_real_ip_is_believed_only_from_a_private_network_peer() -> None:
    app = limited_app()
    forwarded = {"X-Real-IP": "198.51.100.4"}

    from_nginx = client_address(request_to(app, "/", peer="172.18.0.5", headers=forwarded))
    from_outside = client_address(request_to(app, "/", peer="93.184.216.34", headers=forwarded))
    without_header = client_address(request_to(app, "/", peer="172.18.0.5"))

    assert from_nginx == "198.51.100.4"
    assert from_outside == "93.184.216.34"
    assert without_header == "172.18.0.5"


def test_alert_tests_once_a_minute_per_rule_and_a_daily_cap_per_person() -> None:
    app = limited_app(alert_tests_per_day=2)
    other_rule = uuid.UUID("0192f1c4-0000-7000-8000-000000000003")
    third_rule = uuid.UUID("0192f1c4-0000-7000-8000-000000000004")

    limit_alert_test(request_to(app, "/"), RULE_ID, USER_ID)
    with pytest.raises(RateLimitedError, match="less than a minute ago"):
        limit_alert_test(request_to(app, "/"), RULE_ID, USER_ID)
    limit_alert_test(request_to(app, "/"), other_rule, USER_ID)
    with pytest.raises(RateLimitedError, match="in the last day"):
        limit_alert_test(request_to(app, "/"), third_rule, USER_ID)
