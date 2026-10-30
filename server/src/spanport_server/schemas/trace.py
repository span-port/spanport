"""Trace search (the Requests list) and one trace's spans (the waterfall)."""

from dataclasses import dataclass
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from spanport_server.core.constants import (
    DEFAULT_TRACE_SEARCH_LIMIT,
    MAX_ROUTE_FILTER_LENGTH,
    MAX_TRACE_SEARCH_LIMIT,
)
from spanport_server.core.ids import UuidV7


class TraceSearchRequest(BaseModel):
    """Incoming requests of one project in a time range, with optional filters."""

    model_config = ConfigDict(extra="forbid")

    project_id: UuidV7
    start: AwareDatetime
    end: AwareDatetime
    service: str = Field(default="", max_length=MAX_ROUTE_FILTER_LENGTH)
    # Part of the route or span name, e.g. "/users".
    route: str = Field(default="", max_length=MAX_ROUTE_FILTER_LENGTH)
    min_duration_ms: int = Field(default=0, ge=0)
    errors_only: bool = False
    limit: int = Field(default=DEFAULT_TRACE_SEARCH_LIMIT, ge=1, le=MAX_TRACE_SEARCH_LIMIT)
    cursor: str | None = None


class RequestItem(BaseModel):
    """One incoming request: the entry span of a trace in one service."""

    trace_id: str
    span_id: str
    service: str
    name: str
    http_method: str
    http_route: str
    http_status: int
    error: bool
    start_ts: datetime
    duration_ms: float


class TraceSearchResponse(BaseModel):
    """A page of requests, newest first. Pass `next_cursor` back for older ones."""

    data: list[RequestItem]
    next_cursor: str | None
    has_more: bool


class SpanItem(BaseModel):
    """One step of a trace, for the waterfall.

    `label` is the span's category, with client calls split into `service_call` (another of
    your services answered) and `external`. `self_ms` is time not covered by child spans.
    """

    span_id: str
    parent_span_id: str
    service: str
    name: str
    kind: str
    label: str
    start_ts: datetime
    offset_ms: float
    duration_ms: float
    self_ms: float
    status_code: str
    status_message: str
    http_method: str
    http_route: str
    http_status: int
    attributes: dict[str, str]


class TraceDetail(BaseModel):
    """Every stored span of one trace in one project, ordered by start time."""

    trace_id: str
    start_ts: datetime
    duration_ms: float
    spans: list[SpanItem]
    truncated: bool


@dataclass(frozen=True)
class SpanPosition:
    """Where a page of requests ended: the last row's start time and span id."""

    ts: datetime
    span_id: str


@dataclass(frozen=True)
class RequestQuery:
    """A bounded request search for the repository: one org, one project, a time range."""

    org_id: UuidV7
    project_id: UuidV7
    start: datetime
    end: datetime
    service: str
    route: str
    min_duration_ns: int
    errors_only: bool


@dataclass(frozen=True)
class StoredSpan:
    """A span as read from storage, before the waterfall is worked out."""

    span_id: str
    parent_span_id: str
    service: str
    name: str
    kind: str
    category: str
    start_ts: datetime
    duration_ns: int
    status_code: str
    status_message: str
    http_method: str
    http_route: str
    http_status: int
    attributes: dict[str, str]
