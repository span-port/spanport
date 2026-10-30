import csv
import io
import json
from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeLogSearchStore, FakeTenantStore

from spanport_server.core.errors import InvalidRequestError, NotAllowedError, NotFoundError
from spanport_server.core.ids import new_id
from spanport_server.schemas.auth import Caller, Role
from spanport_server.schemas.log_search import LogExportRequest, LogItem
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services import log_export_service
from spanport_server.services.log_export_service import LogExportService, PreparedExport

pytestmark = pytest.mark.anyio

NOW = datetime.now(UTC)


def item(message: str, minutes_ago: int, **attributes: str) -> LogItem:
    return LogItem(
        log_id=new_id(),
        ts=NOW - timedelta(minutes=minutes_ago),
        service="api",
        level="ERROR",
        message=message,
        trace_id="",
        span_id="",
        attributes=attributes,
    )


class Setup:
    def __init__(self, tenants: FakeTenantStore, project: ProjectRef) -> None:
        self.project = project
        self.logs = FakeLogSearchStore()
        self.service = LogExportService(tenants, self.logs)

    def caller(self, role: Role | None = Role.MEMBER) -> Caller:
        return Caller(org_id=self.project.org_id, label="user=test", role=role)

    def request(self, export_format: str) -> LogExportRequest:
        return LogExportRequest.model_validate(
            {
                "project_id": self.project.project_id,
                "start": NOW - timedelta(hours=1),
                "end": NOW,
                "format": export_format,
            }
        )

    async def export(self, export_format: str) -> tuple[PreparedExport, str]:
        self.logs.by_level = {"ERROR": len(self.logs.rows)}
        prepared = await self.service.prepare(self.caller(), self.request(export_format))
        return prepared, "".join([part async for part in self.service.lines(prepared)])


@pytest.fixture
async def setup() -> Setup:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    return Setup(tenants, project)


async def test_csv_has_a_header_newest_first_and_quotes_commas(setup: Setup) -> None:
    setup.logs.rows = [
        item("older, with a comma", 5, **{"client.ip": "10.0.0.1"}),
        item("newer", 1, **{"user.id": "u42"}),
    ]

    prepared, body = await setup.export("csv")
    rows = list(csv.reader(io.StringIO(body)))

    assert prepared.content_type.startswith("text/csv")
    assert prepared.file_name.startswith("spanport-logs-northwind-hr-portal-production-")
    assert prepared.file_name.endswith(".csv")
    assert rows[0][:4] == ["ts", "level", "service", "message"]
    assert [row[3] for row in rows[1:]] == ["newer", "older, with a comma"]
    assert rows[1][7] == "u42"
    assert rows[2][6] == "10.0.0.1"


async def test_csv_cells_cannot_run_as_spreadsheet_formulas(setup: Setup) -> None:
    setup.logs.rows = [item('=HYPERLINK("http://evil","click")', 1)]

    _, body = await setup.export("csv")

    assert list(csv.reader(io.StringIO(body)))[1][3] == '\'=HYPERLINK("http://evil","click")'


async def test_ndjson_is_one_object_per_line_with_every_field(setup: Setup) -> None:
    setup.logs.rows = [item("boom", 1, **{"order.id": "1042"})]

    prepared, body = await setup.export("ndjson")
    (line,) = body.splitlines()

    assert prepared.content_type == "application/x-ndjson"
    assert json.loads(line)["attributes"] == {"order.id": "1042"}
    assert json.loads(line)["message"] == "boom"


async def test_large_exports_are_read_in_batches_without_repeats(
    setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(log_export_service, "EXPORT_BATCH_SIZE", 2)
    setup.logs.rows = [item(f"line {index}", index) for index in range(5)]

    _, body = await setup.export("ndjson")

    assert [json.loads(line)["message"] for line in body.splitlines()] == [
        f"line {index}" for index in range(5)
    ]


async def test_viewers_cannot_export_and_admin_keys_can(setup: Setup) -> None:
    with pytest.raises(NotAllowedError):
        await setup.service.prepare(setup.caller(Role.VIEWER), setup.request("csv"))

    await setup.service.prepare(setup.caller(role=None), setup.request("csv"))


async def test_more_than_the_limit_is_refused_before_streaming(setup: Setup) -> None:
    setup.logs.by_level = {"INFO": 100_001}

    with pytest.raises(InvalidRequestError, match="100,001 lines"):
        await setup.service.prepare(setup.caller(), setup.request("csv"))


async def test_a_project_the_caller_cannot_see_is_not_found(setup: Setup) -> None:
    limited = Caller(
        org_id=setup.project.org_id, label="user=test", role=Role.MEMBER, project_ids=frozenset()
    )

    with pytest.raises(NotFoundError):
        await setup.service.prepare(limited, setup.request("csv"))
