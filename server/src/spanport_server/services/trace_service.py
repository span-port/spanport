"""The Requests screen: search a project's incoming requests, and open one trace's waterfall.

Same rules as log search: own org, projects the caller may see, a bounded time range (traces
are kept 30 days), newest first, bounded pages.
"""

import logging
import re
import time
from datetime import UTC, datetime
from typing import Protocol

from spanport_server.core.constants import (
    INVALID_REQUEST_TRACE_DETAIL,
    MAX_TRACE_SPANS,
    NANOS_PER_MILLISECOND,
    NO_PROJECT_DETAIL,
    NO_TRACE_DETAIL,
    SPAN_RETENTION,
    TRACE_ID_PATTERN,
    TRACE_RANGE_DETAIL,
)
from spanport_server.core.errors import InvalidRequestError, NotFoundError
from spanport_server.core.ids import UuidV7
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.trace import (
    RequestItem,
    RequestQuery,
    SpanPosition,
    StoredSpan,
    TraceDetail,
    TraceSearchRequest,
    TraceSearchResponse,
)
from spanport_server.services.log_search_service import ProjectLookup
from spanport_server.services.trace_cursor import decode_trace_cursor, encode_trace_cursor
from spanport_server.services.trace_shape import build_trace_detail

logger = logging.getLogger(__name__)


class SpanSearchStore(Protocol):
    """Reads stored spans."""

    async def search_requests(
        self, query: RequestQuery, after: SpanPosition | None, limit: int
    ) -> list[RequestItem]:
        """Up to `limit` matching requests, newest first, after `after`."""
        ...

    async def trace_spans(
        self, org_id: UuidV7, project_id: UuidV7, trace_id: str, since: datetime, limit: int
    ) -> list[StoredSpan]:
        """Up to `limit` spans of the trace in the project since `since`, oldest first."""
        ...


class TraceService:
    """Searches requests and builds trace waterfalls."""

    def __init__(self, projects: ProjectLookup, spans: SpanSearchStore) -> None:
        """Create the service.

        Args:
            projects: Project ownership checks (Postgres).
            spans: Stored spans (ClickHouse).
        """
        self._projects = projects
        self._spans = spans

    async def search(self, caller: Caller, request: TraceSearchRequest) -> TraceSearchResponse:
        """One page of incoming requests, newest first.

        Raises:
            NotFoundError: The project isn't in the caller's org or not visible to them.
            InvalidRequestError: Bad range (backwards or older than 30 days) or cursor.
            StorageUnavailableError: ClickHouse is down.
        """
        started = time.perf_counter()
        await self._check_project(caller, request.project_id)
        start, end = request.start.astimezone(UTC), request.end.astimezone(UTC)
        if end <= start:
            raise InvalidRequestError("end must be after start.")
        if start < datetime.now(UTC) - SPAN_RETENTION:
            raise InvalidRequestError(TRACE_RANGE_DETAIL)
        query = RequestQuery(
            org_id=caller.org_id,
            project_id=request.project_id,
            start=start,
            end=end,
            service=request.service,
            route=request.route,
            min_duration_ns=request.min_duration_ms * NANOS_PER_MILLISECOND,
            errors_only=request.errors_only,
        )
        after = decode_trace_cursor(request.cursor) if request.cursor else None
        rows = await self._spans.search_requests(query, after, request.limit + 1)
        page = rows[: request.limit]
        has_more = len(rows) > request.limit
        next_cursor = (
            encode_trace_cursor(SpanPosition(ts=page[-1].start_ts, span_id=page[-1].span_id))
            if has_more
            else None
        )
        logger.info(
            "trace search %s project=%s range_minutes=%d service=%s route=%s min_ms=%d "
            "errors_only=%s rows=%d duration_ms=%d",
            caller.label,
            request.project_id,
            (end - start).total_seconds() // 60,
            bool(request.service),
            bool(request.route),
            request.min_duration_ms,
            request.errors_only,
            len(page),
            (time.perf_counter() - started) * 1000,
        )
        return TraceSearchResponse(data=page, next_cursor=next_cursor, has_more=has_more)

    async def get_trace(self, caller: Caller, project_id: UuidV7, trace_id: str) -> TraceDetail:
        """One trace's spans in one project, as a waterfall.

        Raises:
            InvalidRequestError: The trace id isn't 32 hex characters.
            NotFoundError: No such project for the caller, or no such trace in 30 days.
            StorageUnavailableError: ClickHouse is down.
        """
        started = time.perf_counter()
        if not re.fullmatch(TRACE_ID_PATTERN, trace_id):
            raise InvalidRequestError(INVALID_REQUEST_TRACE_DETAIL)
        await self._check_project(caller, project_id)
        since = datetime.now(UTC) - SPAN_RETENTION
        spans = await self._spans.trace_spans(
            caller.org_id, project_id, trace_id, since, MAX_TRACE_SPANS + 1
        )
        if not spans:
            raise NotFoundError(NO_TRACE_DETAIL)
        detail = build_trace_detail(
            trace_id, spans[:MAX_TRACE_SPANS], truncated=len(spans) > MAX_TRACE_SPANS
        )
        logger.info(
            "trace opened %s project=%s spans=%d truncated=%s duration_ms=%d",
            caller.label,
            project_id,
            len(detail.spans),
            detail.truncated,
            (time.perf_counter() - started) * 1000,
        )
        return detail

    async def _check_project(self, caller: Caller, project_id: UuidV7) -> None:
        """A project the caller may not see answers like one that doesn't exist."""
        if not caller.can_see(project_id) or not await self._projects.project_exists(
            caller.org_id, project_id
        ):
            raise NotFoundError(NO_PROJECT_DETAIL)
