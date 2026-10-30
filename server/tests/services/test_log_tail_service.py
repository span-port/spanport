from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeLogSearchStore, FakeTenantStore, caller_for

from spanport_server.core.errors import InvalidRequestError, NotFoundError
from spanport_server.core.ids import new_id
from spanport_server.core.log_query_model import FieldMatch, Operator
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.log_search import LogItem, LogTailRequest
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.log_tail_service import LogTailService

pytestmark = pytest.mark.anyio


async def no_wait(seconds: float) -> None:
    return


async def setup() -> tuple[LogTailService, FakeLogSearchStore, Caller, ProjectRef]:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    store = FakeLogSearchStore()
    return LogTailService(tenants, store, wait=no_wait), store, caller_for(project.org_id), project


def log_item(message: str, seconds_ago: int = 1) -> LogItem:
    return LogItem(
        log_id=new_id(),
        ts=datetime.now(UTC) - timedelta(seconds=seconds_ago),
        service="hr-portal-api",
        level="ERROR",
        message=message,
        trace_id="",
        span_id="",
        attributes={},
    )


async def take(batches: AsyncIterator[list[LogItem]], count: int) -> list[list[str]]:
    taken: list[list[str]] = []
    async for batch in batches:
        taken.append([item.message for item in batch])
        if len(taken) == count:
            break
    return taken


async def test_sends_each_new_log_once_oldest_first() -> None:
    service, store, caller, project = await setup()
    older, newer = log_item("older", 5), log_item("newer", 1)
    store.rows = [newer, older]
    tail = await service.open(caller, LogTailRequest(project_id=project.project_id))

    batches = service.batches(tail)
    first = await take(batches, 1)
    store.rows = [log_item("latest", 0), newer, older]
    second = await take(batches, 1)

    assert first == [["older", "newer"]]
    assert second == [["latest"]]


async def test_quiet_polls_give_empty_batches() -> None:
    service, _, caller, project = await setup()
    tail = await service.open(caller, LogTailRequest(project_id=project.project_id))

    assert await take(service.batches(tail), 2) == [[], []]


async def test_each_poll_reads_the_recent_window_with_the_parsed_condition() -> None:
    service, store, caller, project = await setup()
    tail = await service.open(
        caller, LogTailRequest(project_id=project.project_id, query="level:error")
    )

    await take(service.batches(tail), 1)

    [(query, after, _)] = store.queries
    assert (query.org_id, query.project_id) == (caller.org_id, project.project_id)
    assert query.condition == FieldMatch("level", Operator.EQUALS, "error")
    assert after is None
    assert timedelta(seconds=29) < datetime.now(UTC) - query.start <= timedelta(seconds=31)


async def test_open_checks_the_project_and_query_before_streaming() -> None:
    service, _, caller, project = await setup()

    with pytest.raises(NotFoundError):
        await service.open(caller, LogTailRequest(project_id=new_id()))
    with pytest.raises(InvalidRequestError):
        await service.open(caller, LogTailRequest(project_id=project.project_id, query="(oops"))
