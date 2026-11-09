"""The API detail page: one endpoint over a time range. Its numbers, how they changed over
time, its status codes, every step it makes (queries, outgoing calls, LLM calls, methods)
and its slowest requests.

Same rules as the APIs list: own org, projects the caller may see, a range within 30 days.
"""

import logging
import math
import time
from datetime import timedelta
from typing import Protocol

from spanport_server.core.constants import (
    MAX_ENDPOINT_STEPS,
    MIN_BUCKET_SECONDS,
    SLOWEST_REQUESTS,
    SPAN_CATEGORY_CLIENT,
    SPAN_CATEGORY_DB,
    SPAN_CATEGORY_LLM,
    STEP_KIND_CODE,
    STEP_KIND_EXTERNAL,
    TIMELINE_POINTS,
)
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.endpoint import (
    EndpointDetailRequest,
    EndpointDetailResponse,
    EndpointQuery,
    EndpointRow,
    SlowRequest,
    StatusCount,
    StepRow,
    StepStats,
    TimelinePoint,
    TimelineRow,
)
from spanport_server.services.endpoint_service import as_ms, endpoint_stats
from spanport_server.services.log_search_service import ProjectLookup
from spanport_server.services.trace_service import check_visible_project, span_range

logger = logging.getLogger(__name__)


class EndpointDetailStore(Protocol):
    """One endpoint's stored requests and steps."""

    async def summary_row(self, query: EndpointQuery) -> EndpointRow | None:
        """The endpoint's sums; None without requests."""
        ...

    async def timeline(self, query: EndpointQuery, bucket_seconds: int) -> list[TimelineRow]:
        """Per-interval requests, failures and slow-5% time."""
        ...

    async def statuses(self, query: EndpointQuery) -> list[tuple[int, int]]:
        """(HTTP status, requests) pairs."""
        ...

    async def steps(self, query: EndpointQuery, limit: int) -> list[StepRow]:
        """The steps its requests make, most total time first."""
        ...

    async def slowest(self, query: EndpointQuery, limit: int) -> list[SlowRequest]:
        """Its slowest requests."""
        ...


def bucket_seconds(range_length: timedelta) -> int:
    """The chart's interval: about TIMELINE_POINTS per range, in whole minutes, at least one."""
    seconds = range_length.total_seconds() / TIMELINE_POINTS
    return max(MIN_BUCKET_SECONDS, math.ceil(seconds / MIN_BUCKET_SECONDS) * MIN_BUCKET_SECONDS)


def step_kind(category: str) -> str:
    """The kind of step, as the waterfall and the APIs list name it (a client call is
    "external"; anything else that isn't a query or LLM call is your code).
    """
    if category == SPAN_CATEGORY_CLIENT:
        return STEP_KIND_EXTERNAL
    if category in (SPAN_CATEGORY_DB, SPAN_CATEGORY_LLM):
        return category
    return STEP_KIND_CODE


def step_stats(row: StepRow, requests: int) -> StepStats:
    """One step in milliseconds, with how many times an average request makes it."""
    return StepStats(
        kind=step_kind(row.category),
        name=row.name,
        calls=row.calls,
        calls_per_request=row.calls / requests if requests else 0.0,
        avg_ms=as_ms(row.avg_ns),
        p95_ms=as_ms(row.p95_ns),
        total_ms=as_ms(row.total_ns),
    )


class EndpointDetailService:
    """Builds the API detail page from stored spans."""

    def __init__(self, projects: ProjectLookup, details: EndpointDetailStore) -> None:
        """Create the service.

        Args:
            projects: Project ownership checks (Postgres).
            details: One endpoint's stored requests and steps (ClickHouse).
        """
        self._projects = projects
        self._details = details

    async def detail(
        self, caller: Caller, request: EndpointDetailRequest
    ) -> EndpointDetailResponse:
        """One endpoint over the range.

        Raises:
            NotFoundError: The project isn't in the caller's org or not visible to them.
            InvalidRequestError: Bad range (backwards or older than 30 days).
            StorageUnavailableError: ClickHouse is down.
        """
        started = time.perf_counter()
        await check_visible_project(caller, request.project_id, self._projects)
        start, end = span_range(request.start, request.end)
        query = EndpointQuery(
            org_id=caller.org_id,
            project_id=request.project_id,
            start=start,
            end=end,
            service=request.service,
            http_method=request.http_method,
            route=request.route,
        )
        interval = bucket_seconds(end - start)
        summary = await self._details.summary_row(query)
        requests = summary.requests if summary else 0
        timeline = await self._details.timeline(query, interval)
        statuses = await self._details.statuses(query)
        steps = await self._details.steps(query, MAX_ENDPOINT_STEPS)
        slowest = await self._details.slowest(query, SLOWEST_REQUESTS)
        logger.info(
            "endpoint detail %s project=%s range_minutes=%d requests=%d steps=%d duration_ms=%d",
            caller.label,
            request.project_id,
            (end - start).total_seconds() // 60,
            requests,
            len(steps),
            (time.perf_counter() - started) * 1000,
        )
        return EndpointDetailResponse(
            summary=endpoint_stats(summary) if summary else None,
            bucket_seconds=interval,
            timeline=[
                TimelinePoint(
                    at=row.at, requests=row.requests, errors=row.errors, p95_ms=as_ms(row.p95_ns)
                )
                for row in timeline
            ],
            statuses=[StatusCount(status=status, requests=count) for status, count in statuses],
            steps=[step_stats(row, requests) for row in steps],
            slowest=slowest,
        )
