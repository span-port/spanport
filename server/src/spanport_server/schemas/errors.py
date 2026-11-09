"""HTTP errors over time: how many requests answered 4xx (the request was wrong) or 5xx (the
server failed), per interval, and the requests behind one interval.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from spanport_server.core.constants import (
    MAX_HTTP_METHOD_LENGTH,
    MAX_ROUTE_FILTER_LENGTH,
    ROUTE_REQUIRES_SERVICE_DETAIL,
)
from spanport_server.core.ids import UuidV7


class ErrorShow(StrEnum):
    """Which failing requests a chosen interval lists."""

    ALL = "all"
    SERVER = "5xx"
    CLIENT = "4xx"


class ErrorSummaryRequest(BaseModel):
    """One project's requests in a time range (at most 30 days back), optionally one API
    (service, method and route) or one service.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: UuidV7
    start: AwareDatetime
    end: AwareDatetime
    service: str = Field(default="", max_length=MAX_ROUTE_FILTER_LENGTH)
    http_method: str = Field(default="", max_length=MAX_HTTP_METHOD_LENGTH)
    route: str = Field(default="", max_length=MAX_ROUTE_FILTER_LENGTH)

    @model_validator(mode="after")
    def route_has_service(self) -> Self:
        """An API is named by its service too."""
        if self.route and not self.service:
            raise ValueError(ROUTE_REQUIRES_SERVICE_DETAIL)
        return self


class ErrorWindowRequest(ErrorSummaryRequest):
    """One interval (a chart bar): `start` and `end` are its edges."""

    show: ErrorShow = ErrorShow.ALL


class ErrorBucket(BaseModel):
    """Requests, 4xx and 5xx answers in the interval starting at `at`."""

    at: datetime
    requests: int
    client_errors: int
    server_errors: int


class ErrorTotals(BaseModel):
    """Every request in the range, and the interval with the most 5xx (None without any)."""

    requests: int
    client_errors: int
    server_errors: int
    worst_server: ErrorBucket | None


class ErrorApi(BaseModel):
    """An API that failed in the range, for the API filter."""

    service: str
    http_method: str
    route: str
    errors: int


class ErrorSummaryResponse(BaseModel):
    """The chart (empty intervals left out, oldest first), the totals and the failing APIs
    (most errors first).
    """

    bucket_seconds: int
    buckets: list[ErrorBucket]
    totals: ErrorTotals
    apis: list[ErrorApi]


class ErrorGroup(BaseModel):
    """How many requests to one API answered this status in the interval."""

    status: int
    service: str
    http_method: str
    route: str
    requests: int


class FailedRequest(BaseModel):
    """One failing request, to open as a waterfall. `logged` is its most severe log line."""

    trace_id: str
    span_id: str
    start_ts: datetime
    service: str
    http_method: str
    route: str
    http_status: int
    duration_ms: float
    client_ip: str
    logged: str


class ErrorWindowResponse(BaseModel):
    """One interval's failing requests: by status and API (most first), the newest ones, and
    how many there were in all.
    """

    total: int
    groups: list[ErrorGroup]
    requests: list[FailedRequest]


@dataclass(frozen=True)
class StatusRange:
    """HTTP statuses from `first` up to, not including, `end`."""

    first: int
    end: int
