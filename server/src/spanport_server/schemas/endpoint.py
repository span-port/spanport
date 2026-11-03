"""API monitoring: per endpoint, how many requests, how fast, how many failed, and where the
time went (your code, database, outgoing calls, LLM).
"""

from dataclasses import dataclass
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from spanport_server.core.constants import MAX_ROUTE_FILTER_LENGTH
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


class EndpointTotals(BaseModel):
    """Every request of the project (or service) in the range."""

    requests: int
    errors: int
    p95_ms: float


class EndpointSummaryResponse(BaseModel):
    """The totals and the busiest endpoints, most requests first.

    An aggregate, not a stored list: there is no next page. `has_more` says more endpoints
    exist than are listed; narrow by service to see them.
    """

    totals: EndpointTotals
    data: list[EndpointStats]
    next_cursor: None = None
    has_more: bool


@dataclass(frozen=True)
class EndpointQuery:
    """A bounded endpoint summary for the repository: one org, one project, a time range."""

    org_id: UuidV7
    project_id: UuidV7
    start: datetime
    end: datetime
    service: str


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
class TotalsRow:
    """Request count, failures and the slow-5% time over every request in the range."""

    requests: int
    errors: int
    p95_ns: float
