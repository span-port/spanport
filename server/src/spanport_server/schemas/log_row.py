"""One row of the ClickHouse logs table. Field names match the column names."""

from dataclasses import dataclass
from datetime import datetime

from spanport_server.core.ids import UuidV7


@dataclass(frozen=True)
class LogRow:
    """A log line ready to insert. org_id and project_id always come from the data key."""

    org_id: UuidV7
    project_id: UuidV7
    log_id: UuidV7
    ts: datetime
    observed_ts: datetime
    service: str
    level: str
    severity_number: int
    message: str
    trace_id: str
    span_id: str
    attributes: dict[str, str]
    resource_attributes: dict[str, str]
