"""Writes rows to the ClickHouse spans table, and deletes a deleted project's spans."""

from collections.abc import Sequence
from dataclasses import fields

from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.exceptions import OperationalError

from spanport_server.core.constants import (
    CLICKHOUSE_INSERT_SETTINGS,
    SPANS_TABLE,
    STORAGE_UNAVAILABLE_DETAIL,
)
from spanport_server.core.errors import StorageUnavailableError
from spanport_server.core.ids import UuidV7
from spanport_server.schemas.span_row import SpanRow

SPAN_COLUMNS = [field.name for field in fields(SpanRow)]
# A lightweight delete: rows vanish from queries at once and are removed when parts merge.
DELETE_PROJECT_SPANS_SQL = (
    f"DELETE FROM {SPANS_TABLE} "  # noqa: S608 - table name is a constant; values are bound
    "WHERE org_id = {org_id:UUID} AND project_id = {project_id:UUID}"
)


class SpanRepository:
    """spans table access."""

    def __init__(self, client: AsyncClient) -> None:
        """Create the repository.

        Args:
            client: ClickHouse client.
        """
        self._client = client

    async def insert_spans(self, rows: Sequence[SpanRow]) -> None:
        """Insert rows and wait until ClickHouse has written them to disk.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached; the caller should retry.
        """
        data = [[getattr(row, column) for column in SPAN_COLUMNS] for row in rows]
        try:
            await self._client.insert(
                SPANS_TABLE, data, column_names=SPAN_COLUMNS, settings=CLICKHOUSE_INSERT_SETTINGS
            )
        except OperationalError as error:
            raise StorageUnavailableError(STORAGE_UNAVAILABLE_DETAIL) from error

    async def delete_project_spans(self, org_id: UuidV7, project_id: UuidV7) -> None:
        """Delete every span of one project of one organization.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached; nothing was deleted.
        """
        try:
            await self._client.command(
                DELETE_PROJECT_SPANS_SQL,
                parameters={"org_id": str(org_id), "project_id": str(project_id)},
            )
        except OperationalError as error:
            raise StorageUnavailableError(STORAGE_UNAVAILABLE_DETAIL) from error
