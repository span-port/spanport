from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeEndpointDetailStore, FakeTenantStore

from spanport_server.core.errors import InvalidRequestError, NotFoundError
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.endpoint import (
    EndpointDetailRequest,
    EndpointRow,
    StepRow,
    TimelineRow,
)
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.endpoint_detail_service import (
    EndpointDetailService,
    bucket_seconds,
    step_kind,
)

pytestmark = pytest.mark.anyio

NOW = datetime.now(UTC)
MS = 1_000_000
ROUTE = "/api/environments/:environmentId/components/:configId/variables"


class Setup:
    def __init__(self, tenants: FakeTenantStore, project: ProjectRef) -> None:
        self.project = project
        self.store = FakeEndpointDetailStore()
        self.service = EndpointDetailService(tenants, self.store)
        self.caller = Caller(org_id=project.org_id, label="user=test")

    def request(self, **changes: object) -> EndpointDetailRequest:
        fields: dict[str, object] = {
            "project_id": self.project.project_id,
            "start": NOW - timedelta(hours=1),
            "end": NOW,
            "service": "kosha-backend",
            "http_method": "GET",
            "route": ROUTE,
        }
        return EndpointDetailRequest.model_validate(fields | changes)


@pytest.fixture
async def setup() -> Setup:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "kosha", "backend", "production")
    return Setup(tenants, project)


def test_the_chart_interval_is_about_sixty_points_in_whole_minutes() -> None:
    assert bucket_seconds(timedelta(minutes=15)) == 60
    assert bucket_seconds(timedelta(hours=1)) == 60
    assert bucket_seconds(timedelta(days=1)) == 1440
    assert bucket_seconds(timedelta(days=7)) == 10_080


def test_steps_are_named_like_the_waterfall() -> None:
    assert [step_kind(category) for category in ("db", "client", "llm", "code")] == [
        "db",
        "external",
        "llm",
        "code",
    ]


async def test_detail_in_milliseconds_with_calls_per_request(setup: Setup) -> None:
    setup.store.summary = EndpointRow(
        service="kosha-backend",
        http_method="GET",
        route=ROUTE,
        requests=10,
        errors=2,
        p50_ns=150 * MS,
        p95_ns=300 * MS,
        p99_ns=400 * MS,
        total_ns=2000 * MS,
        db_ns=400 * MS,
        external_ns=0,
        llm_ns=0,
    )
    setup.store.timeline_rows = [TimelineRow(at=NOW, requests=10, errors=2, p95_ns=300 * MS)]
    setup.store.status_rows = [(200, 8), (500, 2)]
    setup.store.step_rows = [
        StepRow(
            category="db",
            name="pg.query:SELECT kosha",
            calls=30,
            avg_ns=4 * MS,
            p95_ns=9 * MS,
            total_ns=120 * MS,
        )
    ]

    detail = await setup.service.detail(setup.caller, setup.request())

    assert detail.summary is not None and detail.summary.avg_ms == 200
    assert (detail.timeline[0].p95_ms, detail.bucket_seconds) == (300, 60)
    assert [(item.status, item.requests) for item in detail.statuses] == [(200, 8), (500, 2)]
    (step,) = detail.steps
    assert (step.kind, step.calls_per_request, step.avg_ms, step.total_ms) == ("db", 3, 4, 120)
    (query,) = setup.store.queries
    assert (query.service, query.http_method, query.route) == ("kosha-backend", "GET", ROUTE)


async def test_an_endpoint_without_requests_has_no_summary(setup: Setup) -> None:
    detail = await setup.service.detail(setup.caller, setup.request())

    assert detail.summary is None
    assert detail.steps == [] and detail.slowest == []


async def test_ranges_and_projects_are_checked(setup: Setup) -> None:
    limited = Caller(org_id=setup.project.org_id, label="user=x", project_ids=frozenset())

    with pytest.raises(InvalidRequestError):
        await setup.service.detail(setup.caller, setup.request(start=NOW - timedelta(days=31)))
    with pytest.raises(NotFoundError):
        await setup.service.detail(limited, setup.request())
