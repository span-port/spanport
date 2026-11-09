"""HTTP errors over time (the Errors screen): 4xx and 5xx answers per interval, and the
failing requests behind one interval with what their code logged.

Same rules as the APIs screen: own org, projects the caller may see, a range within 30 days.
"""

import logging
import time
from dataclasses import replace
from typing import Protocol

from spanport_server.core.constants import (
    END_HTTP_STATUS,
    ERROR_WINDOW_REQUESTS,
    FIRST_CLIENT_ERROR_STATUS,
    FIRST_SERVER_ERROR_STATUS,
    MAX_ENDPOINTS,
    MAX_ERROR_GROUPS,
)
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.endpoint import EndpointQuery
from spanport_server.schemas.errors import (
    ErrorApi,
    ErrorBucket,
    ErrorGroup,
    ErrorShow,
    ErrorSummaryRequest,
    ErrorSummaryResponse,
    ErrorTotals,
    ErrorWindowRequest,
    ErrorWindowResponse,
    FailedRequest,
    StatusRange,
)
from spanport_server.services.endpoint_detail_service import bucket_seconds
from spanport_server.services.log_search_service import ProjectLookup
from spanport_server.services.trace_service import check_visible_project, span_range

logger = logging.getLogger(__name__)


class ErrorStore(Protocol):
    """Stored requests and log lines, read for HTTP errors."""

    async def buckets(self, query: EndpointQuery, bucket_seconds: int) -> list[ErrorBucket]:
        """Requests, 4xx and 5xx per interval."""
        ...

    async def failing_apis(self, query: EndpointQuery, limit: int) -> list[ErrorApi]:
        """APIs with any 4xx or 5xx, most errors first."""
        ...

    async def window_total(self, query: EndpointQuery, statuses: StatusRange) -> int:
        """How many requests answered a status in the range."""
        ...

    async def groups(
        self, query: EndpointQuery, statuses: StatusRange, limit: int
    ) -> list[ErrorGroup]:
        """Failing requests per status and API."""
        ...

    async def failed_requests(
        self, query: EndpointQuery, statuses: StatusRange, limit: int
    ) -> list[FailedRequest]:
        """The newest failing requests."""
        ...

    async def logged_lines(self, query: EndpointQuery, trace_ids: list[str]) -> dict[str, str]:
        """Each trace's most severe log line."""
        ...


def status_range(show: ErrorShow) -> StatusRange:
    """The HTTP statuses a choice of "show" covers."""
    match show:
        case ErrorShow.ALL:
            return StatusRange(FIRST_CLIENT_ERROR_STATUS, END_HTTP_STATUS)
        case ErrorShow.SERVER:
            return StatusRange(FIRST_SERVER_ERROR_STATUS, END_HTTP_STATUS)
        case ErrorShow.CLIENT:
            return StatusRange(FIRST_CLIENT_ERROR_STATUS, FIRST_SERVER_ERROR_STATUS)


def error_totals(buckets: list[ErrorBucket]) -> ErrorTotals:
    """The range's sums, and its interval with the most 5xx (the earliest among equals)."""
    worst = max(buckets, key=lambda bucket: bucket.server_errors, default=None)
    return ErrorTotals(
        requests=sum(bucket.requests for bucket in buckets),
        client_errors=sum(bucket.client_errors for bucket in buckets),
        server_errors=sum(bucket.server_errors for bucket in buckets),
        worst_server=worst if worst and worst.server_errors else None,
    )


class ErrorService:
    """Builds the Errors screen from stored requests and logs."""

    def __init__(self, projects: ProjectLookup, errors: ErrorStore) -> None:
        """Create the service.

        Args:
            projects: Project ownership checks (Postgres).
            errors: Stored requests and log lines (ClickHouse).
        """
        self._projects = projects
        self._errors = errors

    async def summary(self, caller: Caller, request: ErrorSummaryRequest) -> ErrorSummaryResponse:
        """4xx and 5xx per interval over the range, the totals and the failing APIs (always
        over every API, so the API filter can switch between them).

        Raises:
            NotFoundError: The project isn't in the caller's org or not visible to them.
            InvalidRequestError: Bad range (backwards or older than 30 days).
            StorageUnavailableError: ClickHouse is down.
        """
        started = time.perf_counter()
        query = await self._query(caller, request)
        interval = bucket_seconds(query.end - query.start)
        buckets = await self._errors.buckets(query, interval)
        every_api = replace(query, service="", http_method="", route="")
        apis = await self._errors.failing_apis(every_api, MAX_ENDPOINTS)
        totals = error_totals(buckets)
        logger.info(
            "error summary %s project=%s range_minutes=%d requests=%d 4xx=%d 5xx=%d duration_ms=%d",
            caller.label,
            request.project_id,
            (query.end - query.start).total_seconds() // 60,
            totals.requests,
            totals.client_errors,
            totals.server_errors,
            (time.perf_counter() - started) * 1000,
        )
        return ErrorSummaryResponse(
            bucket_seconds=interval, buckets=buckets, totals=totals, apis=apis
        )

    async def window(self, caller: Caller, request: ErrorWindowRequest) -> ErrorWindowResponse:
        """One interval's failing requests: by status and API, the newest ones with what
        their code logged, and how many in all.

        Raises:
            NotFoundError: The project isn't in the caller's org or not visible to them.
            InvalidRequestError: Bad range (backwards or older than 30 days).
            StorageUnavailableError: ClickHouse is down.
        """
        started = time.perf_counter()
        query = await self._query(caller, request)
        statuses = status_range(request.show)
        total = await self._errors.window_total(query, statuses)
        groups = await self._errors.groups(query, statuses, MAX_ERROR_GROUPS)
        failed = await self._errors.failed_requests(query, statuses, ERROR_WINDOW_REQUESTS)
        logged = await self._errors.logged_lines(query, [r.trace_id for r in failed])
        logger.info(
            "error window %s project=%s show=%s failed=%d groups=%d duration_ms=%d",
            caller.label,
            request.project_id,
            request.show,
            total,
            len(groups),
            (time.perf_counter() - started) * 1000,
        )
        return ErrorWindowResponse(
            total=total,
            groups=groups,
            requests=[
                failed_request.model_copy(
                    update={"logged": logged.get(failed_request.trace_id, "")}
                )
                for failed_request in failed
            ],
        )

    async def _query(self, caller: Caller, request: ErrorSummaryRequest) -> EndpointQuery:
        await check_visible_project(caller, request.project_id, self._projects)
        start, end = span_range(request.start, request.end)
        return EndpointQuery(
            org_id=caller.org_id,
            project_id=request.project_id,
            start=start,
            end=end,
            service=request.service,
            http_method=request.http_method,
            route=request.route,
        )
