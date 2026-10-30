from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeLogSearchStore, FakeTenantStore, caller_for

from spanport_server.core.errors import InvalidRequestError, NotFoundError
from spanport_server.core.ids import new_id
from spanport_server.core.log_query_model import FieldMatch, Operator
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.log_search import (
    LogFilterRequest,
    LogItem,
    LogPosition,
    LogSearchRequest,
)
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.log_cursor import decode_cursor, encode_cursor
from spanport_server.services.log_search_service import LogSearchService

pytestmark = pytest.mark.anyio


async def setup() -> tuple[LogSearchService, FakeLogSearchStore, Caller, ProjectRef]:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    store = FakeLogSearchStore()
    return LogSearchService(tenants, store), store, caller_for(project.org_id), project


def log_item(minutes_ago: int) -> LogItem:
    return LogItem(
        log_id=new_id(),
        ts=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        service="hr-portal-api",
        level="ERROR",
        message="Payment failed",
        trace_id="",
        span_id="",
        attributes={},
    )


def search_request(project: ProjectRef, **overrides: object) -> LogSearchRequest:
    now = datetime.now(UTC)
    fields: dict[str, object] = {
        "project_id": project.project_id,
        "start": now - timedelta(hours=1),
        "end": now,
    }
    return LogSearchRequest.model_validate(fields | overrides)


async def test_returns_a_page_and_a_cursor_when_there_are_more_rows() -> None:
    service, store, caller, project = await setup()
    store.rows = [log_item(minutes) for minutes in range(3)]

    response = await service.search(caller, search_request(project, limit=2))

    assert [item.log_id for item in response.data] == [row.log_id for row in store.rows[:2]]
    assert response.has_more is True
    assert response.next_cursor is not None
    position = decode_cursor(response.next_cursor)
    assert position.log_id == store.rows[1].log_id


async def test_last_page_has_no_cursor() -> None:
    service, store, caller, project = await setup()
    store.rows = [log_item(1)]

    response = await service.search(caller, search_request(project, limit=2))

    assert response.has_more is False
    assert response.next_cursor is None


async def test_cursor_continues_after_the_previous_page() -> None:
    service, store, caller, project = await setup()
    position = LogPosition(ts=datetime.now(UTC), log_id=new_id())

    await service.search(caller, search_request(project, cursor=encode_cursor(position)))

    [(_, after, limit)] = store.queries
    assert after == position
    assert limit == 101


async def test_query_is_bounded_to_the_callers_org_and_project_with_the_parsed_condition() -> None:
    service, store, caller, project = await setup()

    await service.search(caller, search_request(project, query="level:error"))

    [(query, _, _)] = store.queries
    assert (query.org_id, query.project_id) == (caller.org_id, project.project_id)
    assert query.condition == FieldMatch("level", Operator.EQUALS, "error")


async def test_project_of_another_org_is_not_found() -> None:
    service, _, caller, _ = await setup()
    other_project = ProjectRef(org_id=new_id(), project_id=new_id())

    with pytest.raises(NotFoundError):
        await service.search(caller, search_request(other_project))


async def test_range_must_start_within_seven_days() -> None:
    service, _, caller, project = await setup()
    now = datetime.now(UTC)

    with pytest.raises(InvalidRequestError, match="within the last 7 days"):
        await service.search(
            caller, search_request(project, start=now - timedelta(days=8), end=now)
        )


async def test_end_must_be_after_start() -> None:
    service, _, caller, project = await setup()
    now = datetime.now(UTC)

    with pytest.raises(InvalidRequestError, match="end must be after start"):
        await service.search(caller, search_request(project, start=now, end=now))


async def test_counts_add_up_the_levels() -> None:
    service, store, caller, project = await setup()
    store.by_level = {"ERROR": 3, "INFO": 7}
    now = datetime.now(UTC)
    request = LogFilterRequest(
        project_id=project.project_id, start=now - timedelta(hours=1), end=now
    )

    response = await service.counts(caller, request)

    assert response.total == 10
    assert response.by_level == {"ERROR": 3, "INFO": 7}


async def test_search_log_line_names_the_caller_but_never_contains_the_query_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO")
    service, _, caller, project = await setup()

    await service.search(caller, search_request(project, query="secret-customer-name"))

    assert "log search" in caplog.text
    assert caller.label in caplog.text
    assert "secret-customer-name" not in caplog.text


def test_cursor_round_trips() -> None:
    position = LogPosition(
        ts=datetime(2026, 10, 29, 7, 27, 38, 832000, tzinfo=UTC), log_id=new_id()
    )

    assert decode_cursor(encode_cursor(position)) == position


@pytest.mark.parametrize(
    "cursor",
    ["not-base64!", "e30=", "eyJ0cyI6ICIyMDI2LTEwLTI5VDA3OjI3OjM4IiwgImxvZ19pZCI6ICJ4In0="],
    ids=["garbage", "empty-json", "bad-uuid-and-naive-time"],
)
def test_tampered_cursor_is_rejected(cursor: str) -> None:
    with pytest.raises(InvalidRequestError, match="cursor is not valid"):
        decode_cursor(cursor)
