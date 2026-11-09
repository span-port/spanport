"""The APIs screen: per endpoint, how many requests, how fast, how many failed, and which kind
of step (your code, database, outgoing calls, LLM) the time went to.

Same rules as the Requests screen: own org, projects the caller may see, a range within the
30 days spans are kept.
"""

import logging
import time
from dataclasses import replace
from typing import Protocol

from spanport_server.core.constants import MAX_ENDPOINTS, MAX_SLOW_QUERIES, NANOS_PER_MILLISECOND
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.endpoint import (
    EndpointLayers,
    EndpointQuery,
    EndpointRow,
    EndpointStats,
    EndpointSummaryRequest,
    EndpointSummaryResponse,
    EndpointTotals,
    QueryRow,
    SlowQuery,
    TotalsRow,
)
from spanport_server.services.log_search_service import ProjectLookup
from spanport_server.services.trace_service import check_visible_project, span_range

logger = logging.getLogger(__name__)


class EndpointStatsStore(Protocol):
    """Per-endpoint sums of stored spans."""

    async def endpoint_rows(self, query: EndpointQuery, limit: int) -> list[EndpointRow]:
        """Up to `limit` endpoints, most requests first."""
        ...

    async def endpoint_totals(self, query: EndpointQuery) -> TotalsRow:
        """Every request in the range: count, failures and the slow-5% time."""
        ...

    async def slow_queries(self, query: EndpointQuery, limit: int) -> list[QueryRow]:
        """The database queries with the most total time, per endpoint."""
        ...


type EndpointKey = tuple[str, str, str]


def endpoint_key(row: EndpointRow | QueryRow) -> EndpointKey:
    """Service, method and route: what names one endpoint."""
    return (row.service, row.http_method, row.route)


def slow_query(row: QueryRow) -> SlowQuery:
    """One database query in milliseconds, with how many times a request runs it."""
    return SlowQuery(
        statement=row.statement,
        service=row.service,
        http_method=row.http_method,
        route=row.route,
        calls=row.calls,
        calls_per_request=row.calls / row.requests if row.requests else 0.0,
        avg_ms=as_ms(row.avg_ns),
        p95_ms=as_ms(row.p95_ns),
        total_ms=as_ms(row.total_ns),
    )


def as_ms(nanoseconds: float) -> float:
    """Nanoseconds as milliseconds."""
    return nanoseconds / NANOS_PER_MILLISECOND


def average_layers(row: EndpointRow) -> EndpointLayers:
    """Average time per request in each kind of step; "your code" is what the steps don't cover.

    Steps can run in parallel, so their sum may exceed the requests' time. Then they are scaled
    down to fit and your code gets nothing, so the parts still add up to the average.
    """
    measured_ns = row.db_ns + row.external_ns + row.llm_ns
    scale = min(1.0, row.total_ns / measured_ns) if measured_ns else 1.0
    per_request = row.requests * NANOS_PER_MILLISECOND
    return EndpointLayers(
        code_ms=max(row.total_ns - measured_ns * scale, 0) / per_request,
        db_ms=row.db_ns * scale / per_request,
        external_ms=row.external_ns * scale / per_request,
        llm_ms=row.llm_ns * scale / per_request,
    )


def endpoint_stats(row: EndpointRow, previous_p95_ns: float | None = None) -> EndpointStats:
    """One endpoint as the API shows it, in milliseconds, with its slow-5% time just before."""
    return EndpointStats(
        previous_p95_ms=as_ms(previous_p95_ns) if previous_p95_ns is not None else None,
        service=row.service,
        http_method=row.http_method,
        route=row.route,
        requests=row.requests,
        errors=row.errors,
        p50_ms=as_ms(row.p50_ns),
        p95_ms=as_ms(row.p95_ns),
        p99_ms=as_ms(row.p99_ns),
        avg_ms=as_ms(row.total_ns / row.requests),
        layers=average_layers(row),
    )


class EndpointService:
    """Summarises a project's endpoints from its stored spans."""

    def __init__(self, projects: ProjectLookup, stats: EndpointStatsStore) -> None:
        """Create the service.

        Args:
            projects: Project ownership checks (Postgres).
            stats: Per-endpoint sums (ClickHouse).
        """
        self._projects = projects
        self._stats = stats

    async def summary(
        self, caller: Caller, request: EndpointSummaryRequest
    ) -> EndpointSummaryResponse:
        """The project's totals and its busiest endpoints in the range, each with its slow-5%
        time in the period of the same length just before (to show what changed), and the
        database queries with the most total time.

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
        )
        rows = await self._stats.endpoint_rows(query, MAX_ENDPOINTS + 1)
        totals = await self._stats.endpoint_totals(query)
        # Before: the same length just before the range (it may reach past retention: fewer rows).
        before = replace(query, start=start - (end - start), end=start)
        previous_p95 = {
            endpoint_key(row): row.p95_ns
            for row in await self._stats.endpoint_rows(before, MAX_ENDPOINTS + 1)
        }
        previous_totals = await self._stats.endpoint_totals(before)
        queries = await self._stats.slow_queries(query, MAX_SLOW_QUERIES)
        listed = rows[:MAX_ENDPOINTS]
        logger.info(
            "endpoint summary %s project=%s range_minutes=%d service=%s endpoints=%d "
            "requests=%d duration_ms=%d",
            caller.label,
            request.project_id,
            (end - start).total_seconds() // 60,
            bool(request.service),
            len(listed),
            totals.requests,
            (time.perf_counter() - started) * 1000,
        )
        return EndpointSummaryResponse(
            totals=EndpointTotals(
                requests=totals.requests,
                errors=totals.errors,
                p95_ms=as_ms(totals.p95_ns),
                previous_p95_ms=as_ms(previous_totals.p95_ns) if previous_totals.requests else None,
            ),
            data=[endpoint_stats(row, previous_p95.get(endpoint_key(row))) for row in listed],
            slow_queries=[slow_query(row) for row in queries],
            has_more=len(rows) > MAX_ENDPOINTS,
        )
