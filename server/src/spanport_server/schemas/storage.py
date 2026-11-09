"""Setup -> Data -> Storage: how much each project of the organization keeps in ClickHouse."""

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel

from spanport_server.core.ids import UuidV7


class TableUsage(BaseModel):
    """Rows of one kind (log lines or request steps), their estimated size and time span."""

    rows: int
    estimated_bytes: int
    oldest: datetime | None
    newest: datetime | None


class ProjectStorage(BaseModel):
    """One project's stored logs and traces."""

    project_id: UuidV7
    client: str
    project: str
    environment: str
    logs: TableUsage
    spans: TableUsage


class StorageResponse(BaseModel):
    """The organization's stored data per project, with totals and how long each kind is kept.

    One page holds every project; projects without data are listed with zeros.
    `redis_in_use` is false until the LLM gateway (which uses Redis) is running.
    """

    logs_retention_days: int
    spans_retention_days: int
    totals: dict[str, TableUsage]
    projects: list[ProjectStorage]
    redis_in_use: bool = False


@dataclass(frozen=True)
class ProjectRows:
    """One project's row count and oldest and newest timestamps in a table."""

    project_id: UuidV7
    rows: int
    oldest: datetime
    newest: datetime
