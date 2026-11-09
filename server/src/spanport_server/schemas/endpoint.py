"""API monitoring: per endpoint, how many requests, how fast, how many failed, and where the
time went (your code, database, outgoing calls, LLM).
"""

from dataclasses import dataclass
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from spanport_server.core.constants import MAX_HTTP_METHOD_LENGTH, MAX_ROUTE_FILTER_LENGTH
from spanport_server.core.ids import UuidV7


class EndpointSummaryRequest(BaseModel):
    """One project's endpoints in a time range (at most 30 days back), optionally one service."""

    model_config = ConfigDict(extra="forbid")

    project_id: UuidV7
    start: AwareDatetime
    end: AwareDatetime
    service: str = Field(default="", max_length=MAX_ROUTE_FILTER_LENGTH)


class EndpointLayers(BaseModel):
    """Average milliseconds per request in each kind of step. They add up to `avg_ms`."""

    code_ms: float
    db_ms: float
    external_ms: float
    llm_ms: float


class EndpointStats(BaseModel):
    """One endpoint (service, method and route) over the range."""

    service: str
    http_method: str
    route: str
    requests: int
    errors: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    layers: EndpointLayers
    # The slow-5% time in the period of the same length just before; None without requests then.
    previous_p95_ms: float | None = None


class EndpointTotals(BaseModel):
    """Every request of the project (or service) in the range, and the slow-5% time before it."""

    requests: int
    errors: int
    p95_ms: float
    previous_p95_ms: float | None = None


class SlowQuery(BaseModel):
    """A database query an endpoint runs, with how often per request and how long."""

    statement: str
    service: str
    http_method: str
    route: str
    calls: int
    calls_per_request: float
    avg_ms: float
    p95_ms: float
    total_ms: float


class EndpointSummaryResponse(BaseModel):
    """The totals, the busiest endpoints (most requests first) and the database queries with
    the most total time.

    An aggregate, not a stored list: there is no next page. `has_more` says more endpoints
    exist than are listed; narrow by service to see them.
    """

    totals: EndpointTotals
    data: list[EndpointStats]
    slow_queries: list[SlowQuery] = []
    next_cursor: None = None
    has_more: bool


class EndpointDetailRequest(BaseModel):
    """One endpoint (service, method and route, as the APIs list shows them) in a time range."""

    model_config = ConfigDict(extra="forbid")

    project_id: UuidV7
    start: AwareDatetime
    end: AwareDatetime
    service: str = Field(min_length=1, max_length=MAX_ROUTE_FILTER_LENGTH)
    http_method: str = Field(default="", max_length=MAX_HTTP_METHOD_LENGTH)
    route: str = Field(min_length=1, max_length=MAX_ROUTE_FILTER_LENGTH)


class TimelinePoint(BaseModel):
    """Requests, failures and the slow-5% time in one interval starting at `at`."""

    at: datetime
    requests: int
    errors: int
    p95_ms: float


class StatusCount(BaseModel):
    """How many requests answered with this HTTP status (0: no status recorded)."""

    status: int
    requests: int


class StepStats(BaseModel):
    """One step the endpoint makes (a query, an outgoing call, an LLM call, a method), over
    the range: how often per request, how long, and its share of all step time.
    """

    kind: str
    name: str
    calls: int
    calls_per_request: float
    avg_ms: float
    p95_ms: float
    total_ms: float


class SlowRequest(BaseModel):
    """One of the endpoint's slowest requests, to open as a waterfall."""

    trace_id: str
    span_id: str
    start_ts: datetime
    duration_ms: float
    http_status: int
    error: bool


class EndpointDetailResponse(BaseModel):
    """One endpoint over the range. `summary` is None when it had no requests then."""

    summary: EndpointStats | None
    bucket_seconds: int
    timeline: list[TimelinePoint]
    statuses: list[StatusCount]
    steps: list[StepStats]
    slowest: list[SlowRequest]


@dataclass(frozen=True)
class EndpointQuery:
    """A bounded endpoint summary for the repository: one org, one project, a time range,
    optionally one service, and for the detail page one method and route.
    """

    org_id: UuidV7
    project_id: UuidV7
    start: datetime
    end: datetime
    service: str
    http_method: str = ""
    route: str = ""


@dataclass(frozen=True)
class TimelineRow:
    """One interval's requests, failures and slow-5% time, in nanoseconds."""

    at: datetime
    requests: int
    errors: int
    p95_ns: float


@dataclass(frozen=True)
class StepRow:
    """One step's calls and times over the endpoint's requests, in nanoseconds."""

    category: str
    name: str
    calls: int
    avg_ns: float
    p95_ns: float
    total_ns: int


@dataclass(frozen=True)
class EndpointRow:
    """One endpoint's sums from storage, in nanoseconds. Step times are summed over the
    endpoint's requests and may overlap each other (parallel calls).
    """

    service: str
    http_method: str
    route: str
    requests: int
    errors: int
    p50_ns: float
    p95_ns: float
    p99_ns: float
    total_ns: int
    db_ns: int
    external_ns: int
    llm_ns: int


@dataclass(frozen=True)
class QueryRow:
    """One database query of one endpoint over the range, in nanoseconds."""

    service: str
    http_method: str
    route: str
    statement: str
    calls: int
    requests: int
    avg_ns: float
    p95_ns: float
    total_ns: int


@dataclass(frozen=True)
class TotalsRow:
    """Request count, failures and the slow-5% time over every request in the range."""

    requests: int
    errors: int
    p95_ns: float
