from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeStorageStore, FakeTenantStore

from spanport_server.core.ids import new_id
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.storage import ProjectRows
from spanport_server.services.storage_service import StorageService

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


async def test_each_project_gets_its_rows_and_estimated_size_biggest_first() -> None:
    tenants = FakeTenantStore()
    quiet = await tenants.get_or_create_project("acme", "kosha", "frontend", "production")
    busy = await tenants.get_or_create_project("acme", "kosha", "backend", "production")
    storage = FakeStorageStore()
    storage.logs = [ProjectRows(busy.project_id, 1000, NOW - timedelta(days=6), NOW)]
    storage.spans = [ProjectRows(busy.project_id, 200, NOW - timedelta(days=2), NOW)]
    storage.row_bytes = {"logs": 50.0, "spans": 120.0}

    summary = await StorageService(tenants, storage).summary(
        Caller(org_id=busy.org_id, label="user=test")
    )

    first, second = summary.projects
    assert (first.project, first.logs.rows, first.logs.estimated_bytes) == ("backend", 1000, 50_000)
    assert (first.spans.rows, first.spans.estimated_bytes) == (200, 24_000)
    assert (second.project_id, second.logs.rows, second.logs.oldest) == (quiet.project_id, 0, None)
    assert summary.totals["logs"].oldest == NOW - timedelta(days=6)
    assert summary.totals["spans"].estimated_bytes == 24_000
    assert (summary.logs_retention_days, summary.spans_retention_days) == (7, 30)
    assert summary.redis_in_use is False


async def test_rows_of_projects_outside_the_list_are_not_shown() -> None:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "kosha", "backend", "production")
    storage = FakeStorageStore()
    # A project deleted in Postgres a moment ago whose rows are still being removed.
    storage.logs = [ProjectRows(new_id(), 5, NOW, NOW)]

    summary = await StorageService(tenants, storage).summary(
        Caller(org_id=project.org_id, label="user=test")
    )

    assert [item.project_id for item in summary.projects] == [project.project_id]
    assert summary.totals["logs"].rows == 0
