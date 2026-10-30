"""Log search requests and responses, and the data passed between search service and repository."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from spanport_server.core.constants import (
    DEFAULT_SEARCH_LIMIT,
    FIELD_NAME_PATTERN,
    MAX_FILTER_CHIPS,
    MAX_FILTER_VALUE_LENGTH,
    MAX_QUERY_LENGTH,
    MAX_SEARCH_LIMIT,
)
from spanport_server.core.ids import UuidV7
from spanport_server.core.log_query_model import Condition, Operator

type FilterCombine = Literal["and", "or"]


class FilterChip(BaseModel):
    """One filter chip, e.g. Level = ERROR."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(pattern=FIELD_NAME_PATTERN)
    operator: Operator
    value: str = Field(min_length=1, max_length=MAX_FILTER_VALUE_LENGTH)


class LogTailRequest(BaseModel):
    """Which logs: one project, chips and an optional text query. Live tail uses this as is."""

    model_config = ConfigDict(extra="forbid")

    project_id: UuidV7
    filters: list[FilterChip] = Field(default_factory=list, max_length=MAX_FILTER_CHIPS)
    combine: FilterCombine = "and"
    query: str = Field(default="", max_length=MAX_QUERY_LENGTH)


class LogFilterRequest(LogTailRequest):
    """Which logs, within a time range. Counts use this as is."""

    start: AwareDatetime
    end: AwareDatetime


class LogSearchRequest(LogFilterRequest):
    """A page of matching logs, newest first."""

    limit: int = Field(default=DEFAULT_SEARCH_LIMIT, ge=1, le=MAX_SEARCH_LIMIT)
    cursor: str | None = None


class ExportFormat(StrEnum):
    """CSV for spreadsheets; NDJSON (one JSON object per line, every field) for tools."""

    CSV = "csv"
    NDJSON = "ndjson"


class LogExportRequest(LogFilterRequest):
    """The current search (project, range, filters, query) as a file."""

    format: ExportFormat


class LogItem(BaseModel):
    """One log line in a search result. Times are UTC."""

    log_id: UuidV7
    ts: datetime
    service: str
    level: str
    message: str
    trace_id: str
    span_id: str
    attributes: dict[str, str]


class LogSearchResponse(BaseModel):
    """A page of logs. Pass `next_cursor` back to get the next (older) page."""

    data: list[LogItem]
    next_cursor: str | None
    has_more: bool


class LogCountsResponse(BaseModel):
    """How many logs match, in total and per level."""

    total: int
    by_level: dict[str, int]


@dataclass(frozen=True)
class LogPosition:
    """Where a page ended: the last row's time and id. Rows sort by (ts, log_id)."""

    ts: datetime
    log_id: UuidV7


@dataclass(frozen=True)
class LogQuery:
    """A bounded search for the repository: always one org, one project and a time range."""

    org_id: UuidV7
    project_id: UuidV7
    start: datetime
    end: datetime
    condition: Condition | None
