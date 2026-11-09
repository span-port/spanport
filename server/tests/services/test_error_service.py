from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeErrorStore, FakeTenantStore

from spanport_server.core.errors import InvalidRequestError, NotFoundError
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.errors import (
    ErrorBucket,
    ErrorShow,
    ErrorSummaryRequest,
    ErrorWindowRequest,
    FailedRequest,
    StatusRange,
)
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.error_service import ErrorService, error_totals, status_range

pytestmark = pytest.mark.anyio

NOW = datetime.now(UTC)
TRACE = "0af7651916cd43dd8448eb211c80319c"


class Setup:
    def __init__(self, tenants: FakeTenantStore, project: ProjectRef) -> None:
        self.project = project
        self.store = FakeErrorStore()
        self.service = ErrorService(tenants, self.store)
        self.caller = Caller(org_id=project.org_id, label="user=test")

    def fields(self, **changes: object) -> dict[str, object]:
        fields: dict[str, object] = {
            "project_id": self.project.project_id,
            "start": NOW - timedelta(hours=1),
            "end": NOW,
        }
        return fields | changes


@pytest.fixture
async def setup() -> Setup:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "kosha", "backend", "production")
    return Setup(tenants, project)


def bucket(minute: int, requests: int, client: int, server: int) -> ErrorBucket:
    return ErrorBucket(
        at=NOW + timedelta(minutes=minute),
        requests=requests,
        client_errors=client,
        server_errors=server,
    )


def test_show_picks_the_status_range() -> None:
    assert status_range(ErrorShow.ALL) == StatusRange(400, 600)
    assert status_range(ErrorShow.SERVER) == StatusRange(500, 600)
    assert status_range(ErrorShow.CLIENT) == StatusRange(400, 500)


def test_totals_name_the_worst_5xx_moment_only_when_there_was_one() -> None:
    totals = error_totals([bucket(0, 10, 2, 1), bucket(1, 20, 0, 6), bucket(2, 5, 1, 6)])

    assert (totals.requests, totals.client_errors, totals.server_errors) == (35, 3, 13)
    assert totals.worst_server == bucket(1, 20, 0, 6)
    assert error_totals([bucket(0, 10, 2, 0)]).worst_server is None
    assert error_totals([]).worst_server is None


async def test_summary_lists_every_failing_api_even_when_one_is_chosen(setup: Setup) -> None:
    setup.store.bucket_rows = [bucket(0, 10, 2, 1)]
    request = ErrorSummaryRequest.model_validate(
        setup.fields(service="api", http_method="GET", route="/users/:id")
    )

    summary = await setup.service.summary(setup.caller, request)

    assert summary.bucket_seconds == 60
    assert summary.totals.server_errors == 1
    chart, apis = setup.store.queries
    assert (chart.service, chart.route) == ("api", "/users/:id")
    assert (apis.service, apis.http_method, apis.route) == ("", "", "")


async def test_window_adds_what_each_request_logged(setup: Setup) -> None:
    failed = FailedRequest(
        trace_id=TRACE,
        span_id="b7ad6b7169203331",
        start_ts=NOW,
        service="api",
        http_method="GET",
        route="/users/:id",
        http_status=500,
        duration_ms=12,
        client_ip="10.0.0.7",
        logged="",
    )
    quiet = failed.model_copy(update={"trace_id": "f" * 32})
    setup.store.failed = [failed, quiet]
    setup.store.logged = {TRACE: "database timeout"}
    setup.store.total = 2

    window = await setup.service.window(
        setup.caller, ErrorWindowRequest.model_validate(setup.fields(show="5xx"))
    )

    assert window.total == 2
    assert [row.logged for row in window.requests] == ["database timeout", ""]
    assert setup.store.status_ranges == [StatusRange(500, 600)]


async def test_ranges_projects_and_routes_are_checked(setup: Setup) -> None:
    limited = Caller(org_id=setup.project.org_id, label="user=x", project_ids=frozenset())
    request = ErrorSummaryRequest.model_validate(setup.fields())

    with pytest.raises(InvalidRequestError):
        await setup.service.summary(
            setup.caller,
            ErrorSummaryRequest.model_validate(setup.fields(start=NOW - timedelta(days=31))),
        )
    with pytest.raises(NotFoundError):
        await setup.service.summary(limited, request)
    with pytest.raises(ValueError, match="service"):
        ErrorSummaryRequest.model_validate(setup.fields(route="/users/:id"))
