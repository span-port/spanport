"""One row of the ClickHouse spans table. Field names match the column names."""

from dataclasses import dataclass
from datetime import datetime

from spanport_server.core.ids import UuidV7


@dataclass(frozen=True)
class SpanRow:
    """A timed step of a request (a span) ready to insert. org_id and project_id always come
    from the data key. `http_*` are empty / 0 for spans that aren't HTTP.
    """

    org_id: UuidV7
    project_id: UuidV7
    trace_id: str
    span_id: str
    parent_span_id: str
    service: str
    name: str
    kind: str
    category: str
    start_ts: datetime
    end_ts: datetime
    duration_ns: int
    status_code: str
    status_message: str
    http_method: str
    http_route: str
    http_status: int
    attributes: dict[str, str]
    resource_attributes: dict[str, str]
