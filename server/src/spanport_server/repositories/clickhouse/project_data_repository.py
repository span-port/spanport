"""Deletes everything ClickHouse holds for a deleted project: its logs and its spans."""

from clickhouse_connect.driver.asyncclient import AsyncClient

from spanport_server.core.ids import UuidV7
from spanport_server.repositories.clickhouse.log_repository import LogRepository
from spanport_server.repositories.clickhouse.span_repository import SpanRepository


class ProjectDataRepository:
    """A project's telemetry across the ClickHouse tables."""

    def __init__(self, client: AsyncClient) -> None:
        """Create the repository.

        Args:
            client: ClickHouse client.
        """
        self._logs = LogRepository(client)
        self._spans = SpanRepository(client)

    async def delete_project_data(self, org_id: UuidV7, project_id: UuidV7) -> None:
        """Delete the project's logs, then its spans.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached; the project is kept, so the
                delete can simply be retried.
        """
        await self._logs.delete_project_logs(org_id, project_id)
        await self._spans.delete_project_spans(org_id, project_id)
