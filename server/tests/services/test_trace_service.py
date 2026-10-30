from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeSpanSearchStore, FakeTenantStore

from spanport_server.core.errors import InvalidRequestError, NotFoundError
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.schemas.trace import RequestItem, StoredSpan, TraceSearchRequest
from spanport_server.services.trace_service import TraceService

pytestmark = pytest.mark.anyio

NOW = datetime.now(UTC)
TRACE = "0af7651916cd43dd8448eb211c80319c"


def request_item(minutes_ago: int, span_id: str) -> RequestItem:
    return RequestItem(
        trace_id=TRACE,
        span_id=span_id,
        service="api",
        name="GET /users/:id",
        http_method="GET",
        http_route="/users/:id",
        http_status=200,
        error=False,
        start_ts=NOW - timedelta(minutes=minutes_ago),
        duration_ms=42,
    )


class Setup:
    def __init__(self, tenants: FakeTenantStore, project: ProjectRef) -> None:
        self.project = project
        self.spans = FakeSpanSearchStore()
        self.service = TraceService(tenants, self.spans)
        self.caller = Caller(org_id=project.org_id, label="user=test")

    def search(self, **changes: object) -> TraceSearchRequest:
        fields: dict[str, object] = {
            "project_id": self.project.project_id,
            "start": NOW - timedelta(hours=1),
            "end": NOW,
        }
        return TraceSearchRequest.model_validate(fields | changes)


@pytest.fixture
async def setup() -> Setup:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    return Setup(tenants, project)


async def test_requests_page_newest_first_by_cursor(setup: Setup) -> None:
    setup.spans.requests = [request_item(minutes, f"{minutes:016x}") for minutes in range(3)]

    first = await setup.service.search(setup.caller, setup.search(limit=2))
    rest = await setup.service.search(setup.caller, setup.search(limit=2, cursor=first.next_cursor))

    assert [item.span_id for item in first.data + rest.data] == [
        f"{minutes:016x}" for minutes in range(3)
    ]
    assert first.has_more and not rest.has_more


async def test_filters_reach_the_store_in_nanoseconds(setup: Setup) -> None:
    await setup.service.search(
        setup.caller, setup.search(route="/users", min_duration_ms=500, errors_only=True)
    )

    (query,) = setup.spans.queries
    assert (query.route, query.min_duration_ns, query.errors_only) == ("/users", 500_000_000, True)
    assert (query.org_id, query.project_id) == (setup.project.org_id, setup.project.project_id)


async def test_ranges_are_checked(setup: Setup) -> None:
    with pytest.raises(InvalidRequestError):
        await setup.service.search(setup.caller, setup.search(start=NOW, end=NOW))
    with pytest.raises(InvalidRequestError, match="30 days"):
        await setup.service.search(setup.caller, setup.search(start=NOW - timedelta(days=31)))
    with pytest.raises(InvalidRequestError):
        await setup.service.search(setup.caller, setup.search(cursor="made-up"))


async def test_projects_the_caller_cannot_see_do_not_exist(setup: Setup) -> None:
    limited = Caller(org_id=setup.project.org_id, label="user=x", project_ids=frozenset())

    with pytest.raises(NotFoundError):
        await setup.service.search(limited, setup.search())
    with pytest.raises(NotFoundError):
        await setup.service.get_trace(limited, setup.project.project_id, TRACE)


async def test_a_trace_opens_as_a_waterfall_or_is_not_found(setup: Setup) -> None:
    setup.spans.spans[TRACE] = [
        StoredSpan(
            span_id="b7ad6b7169203331",
            parent_span_id="",
            service="api",
            name="GET /users/:id",
            kind="SERVER",
            category="incoming_request",
            start_ts=NOW,
            duration_ns=42_000_000,
            status_code="UNSET",
            status_message="",
            http_method="GET",
            http_route="/users/:id",
            http_status=200,
            attributes={},
        )
    ]

    detail = await setup.service.get_trace(setup.caller, setup.project.project_id, TRACE)

    assert (detail.duration_ms, len(detail.spans), detail.truncated) == (42, 1, False)
    with pytest.raises(NotFoundError):
        await setup.service.get_trace(setup.caller, setup.project.project_id, "f" * 32)
    with pytest.raises(InvalidRequestError, match="32 hexadecimal"):
        await setup.service.get_trace(setup.caller, setup.project.project_id, "nope")
