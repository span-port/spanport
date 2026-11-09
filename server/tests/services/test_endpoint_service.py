from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeEndpointStatsStore, FakeTenantStore

from spanport_server.core.constants import MAX_ENDPOINTS
from spanport_server.core.errors import InvalidRequestError, NotFoundError
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.endpoint import (
    EndpointRow,
    EndpointSummaryRequest,
    QueryRow,
    TotalsRow,
)
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.endpoint_service import EndpointService, average_layers

pytestmark = pytest.mark.anyio

NOW = datetime.now(UTC)
MS = 1_000_000


def row(route: str = "/users/:id", **changes: int) -> EndpointRow:
    # 10 requests of 100 ms: 30 ms database and 20 ms external each, the rest your code.
    fields: dict[str, int] = {
        "requests": 10,
        "errors": 1,
        "p50_ns": 80 * MS,
        "p95_ns": 180 * MS,
        "p99_ns": 250 * MS,
        "total_ns": 1000 * MS,
        "db_ns": 300 * MS,
        "external_ns": 200 * MS,
        "llm_ns": 0,
    } | changes
    return EndpointRow(service="api", http_method="GET", route=route, **fields)


class Setup:
    def __init__(self, tenants: FakeTenantStore, project: ProjectRef) -> None:
        self.project = project
        self.stats = FakeEndpointStatsStore()
        self.service = EndpointService(tenants, self.stats)
        self.caller = Caller(org_id=project.org_id, label="user=test")

    def request(self, **changes: object) -> EndpointSummaryRequest:
        fields: dict[str, object] = {
            "project_id": self.project.project_id,
            "start": NOW - timedelta(hours=1),
            "end": NOW,
        }
        return EndpointSummaryRequest.model_validate(fields | changes)


@pytest.fixture
async def setup() -> Setup:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    return Setup(tenants, project)


def test_your_code_is_the_time_the_steps_do_not_cover() -> None:
    layers = average_layers(row())

    assert (layers.code_ms, layers.db_ms, layers.external_ms, layers.llm_ms) == (50, 30, 20, 0)


def test_parallel_steps_are_scaled_to_the_request_time() -> None:
    # 600 ms of database and 400 ms of LLM calls running side by side inside 500 ms requests.
    layers = average_layers(
        row(requests=1, total_ns=500 * MS, db_ns=600 * MS, llm_ns=400 * MS, external_ns=0)
    )

    assert (layers.code_ms, layers.db_ms, layers.llm_ms) == (0, 300, 200)


async def test_summary_in_milliseconds_with_totals(setup: Setup) -> None:
    setup.stats.rows = [row()]
    setup.stats.totals = TotalsRow(requests=10, errors=1, p95_ns=180 * MS)

    summary = await setup.service.summary(setup.caller, setup.request(service="api"))

    (endpoint,) = summary.data
    assert (endpoint.p50_ms, endpoint.p95_ms, endpoint.p99_ms, endpoint.avg_ms) == (
        80,
        180,
        250,
        100,
    )
    assert (summary.totals.requests, summary.totals.p95_ms, summary.has_more) == (10, 180, False)
    assert (endpoint.previous_p95_ms, summary.totals.previous_p95_ms) == (None, None)
    query, before = setup.stats.queries
    assert (query.org_id, query.project_id, query.service) == (
        setup.project.org_id,
        setup.project.project_id,
        "api",
    )
    # The period just before, of the same length.
    assert (before.end, before.end - before.start) == (query.start, query.end - query.start)


async def test_each_endpoint_carries_its_slow_5_percent_time_from_just_before(
    setup: Setup,
) -> None:
    setup.stats.rows = [row("/users/:id", p95_ns=900 * MS), row("/new")]
    setup.stats.previous_rows = [row("/users/:id", p95_ns=300 * MS)]
    setup.stats.totals = TotalsRow(requests=20, errors=0, p95_ns=900 * MS)
    setup.stats.previous_totals = TotalsRow(requests=8, errors=0, p95_ns=250 * MS)

    summary = await setup.service.summary(setup.caller, setup.request())

    assert [item.previous_p95_ms for item in summary.data] == [300, None]
    assert summary.totals.previous_p95_ms == 250


async def test_slow_queries_say_how_often_a_request_runs_them(setup: Setup) -> None:
    setup.stats.query_rows = [
        QueryRow(
            service="api",
            http_method="GET",
            route="/jobs",
            statement="SELECT * FROM applications WHERE candidate_id = $1",
            calls=480,
            requests=10,
            avg_ns=3 * MS,
            p95_ns=7 * MS,
            total_ns=1440 * MS,
        )
    ]

    (query,) = (await setup.service.summary(setup.caller, setup.request())).slow_queries

    assert (query.calls_per_request, query.avg_ms, query.total_ms) == (48, 3, 1440)
    assert query.route == "/jobs"


async def test_only_the_busiest_endpoints_are_listed(setup: Setup) -> None:
    setup.stats.rows = [row(f"/r{index}") for index in range(MAX_ENDPOINTS + 1)]

    summary = await setup.service.summary(setup.caller, setup.request())

    assert len(summary.data) == MAX_ENDPOINTS
    assert summary.has_more


async def test_ranges_and_projects_are_checked(setup: Setup) -> None:
    limited = Caller(org_id=setup.project.org_id, label="user=x", project_ids=frozenset())

    with pytest.raises(InvalidRequestError, match="after start"):
        await setup.service.summary(setup.caller, setup.request(start=NOW, end=NOW))
    with pytest.raises(InvalidRequestError, match="30 days"):
        await setup.service.summary(setup.caller, setup.request(start=NOW - timedelta(days=31)))
    with pytest.raises(NotFoundError):
        await setup.service.summary(limited, setup.request())
