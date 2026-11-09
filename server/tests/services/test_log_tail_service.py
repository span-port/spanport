from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeLogSearchStore, FakeTenantStore, caller_for

from spanport_server.core.errors import (
    InvalidRequestError,
    NotFoundError,
    NotSignedInError,
    RateLimitedError,
)
from spanport_server.core.ids import new_id
from spanport_server.core.log_query_model import FieldMatch, Operator
from spanport_server.core.rate_limiter import ConcurrencyLimiter
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.log_search import LogItem, LogTailRequest
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.log_tail_service import CallerCheck, LogTailService

pytestmark = pytest.mark.anyio


async def no_wait(seconds: float) -> None:
    return


async def setup() -> tuple[LogTailService, FakeLogSearchStore, Caller, ProjectRef]:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    store = FakeLogSearchStore()
    service = LogTailService(tenants, store, ConcurrencyLimiter(), wait=no_wait)
    return service, store, caller_for(project.org_id), project


def same_caller(caller: Caller) -> CallerCheck:
    async def check() -> Caller:
        return caller

    return check


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

    batches = service.batches(tail, same_caller(caller))
    first = await take(batches, 1)
    store.rows = [log_item("latest", 0), newer, older]
    second = await take(batches, 1)

    assert first == [["older", "newer"]]
    assert second == [["latest"]]


async def test_quiet_polls_give_empty_batches() -> None:
    service, _, caller, project = await setup()
    tail = await service.open(caller, LogTailRequest(project_id=project.project_id))

    assert await take(service.batches(tail, same_caller(caller)), 2) == [[], []]


async def test_each_poll_reads_the_recent_window_with_the_parsed_condition() -> None:
    service, store, caller, project = await setup()
    tail = await service.open(
        caller, LogTailRequest(project_id=project.project_id, query="level:error")
    )

    await take(service.batches(tail, same_caller(caller)), 1)

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


class SteppingClock:
    """A clock that moves forward by each wait, so a tail's minutes pass instantly."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    async def wait(self, seconds: float) -> None:
        self.now += seconds


async def timed_setup(
    max_tails: int = 3, max_minutes: int = 60
) -> tuple[LogTailService, Caller, ProjectRef]:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    clock = SteppingClock()
    service = LogTailService(
        tenants,
        FakeLogSearchStore(),
        ConcurrencyLimiter(clock),
        max_tails=max_tails,
        max_minutes=max_minutes,
        wait=clock.wait,
        clock=clock,
    )
    return service, caller_for(project.org_id), project


async def run_out(batches: AsyncIterator[list[LogItem]]) -> int:
    polls = 0
    async for _ in batches:
        polls += 1
    return polls


async def test_ends_after_the_longest_allowed_run() -> None:
    service, caller, project = await timed_setup(max_minutes=1)
    tail = await service.open(caller, LogTailRequest(project_id=project.project_id))

    polls = await run_out(service.batches(tail, same_caller(caller)))

    # One poll every 2 s for a minute.
    assert polls == 30


async def test_ends_when_the_caller_is_signed_out() -> None:
    service, caller, project = await timed_setup()
    tail = await service.open(caller, LogTailRequest(project_id=project.project_id))

    async def signed_out() -> Caller:
        raise NotSignedInError("Sign in to continue.")

    polls = await run_out(service.batches(tail, signed_out))

    # Access is checked again after a minute, then the stream ends.
    assert polls == 30


async def test_ends_when_the_caller_loses_the_project() -> None:
    service, caller, project = await timed_setup()
    tail = await service.open(caller, LogTailRequest(project_id=project.project_id))
    without_project = replace(caller, project_ids=frozenset({new_id()}))

    polls = await run_out(service.batches(tail, same_caller(without_project)))

    assert polls == 30


async def test_a_caller_runs_a_limited_number_of_tails_and_ending_one_frees_it() -> None:
    service, caller, project = await timed_setup(max_tails=1, max_minutes=1)
    request = LogTailRequest(project_id=project.project_id)
    first = await service.open(caller, request)

    with pytest.raises(RateLimitedError):
        await service.open(caller, request)
    await run_out(service.batches(first, same_caller(caller)))
    again = await service.open(caller, request)

    assert again.project_id == project.project_id
