"""How much the organization keeps in ClickHouse: rows per project, and the average size of a
row in each table. Counts are scoped to one organization; the average row size is the only
table-wide figure, and it reveals nothing about other organizations' data.
"""

from collections.abc import Sequence
from typing import Any

from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.exceptions import OperationalError

from spanport_server.core.constants import LOGS_TABLE, SPANS_TABLE, STORAGE_UNAVAILABLE_DETAIL
from spanport_server.core.errors import StorageUnavailableError
from spanport_server.core.ids import UuidV7
from spanport_server.repositories.clickhouse.log_search_repository import as_utc
from spanport_server.schemas.storage import ProjectRows

# Built only from fixed table and column names; the org is a bound parameter.
LOG_ROWS_SQL = (
    "SELECT project_id, count(), min(ts), max(ts) "  # noqa: S608
    f"FROM {LOGS_TABLE} WHERE org_id = {{org_id:UUID}} GROUP BY project_id"
)
SPAN_ROWS_SQL = (
    "SELECT project_id, count(), min(start_ts), max(start_ts) "  # noqa: S608
    f"FROM {SPANS_TABLE} WHERE org_id = {{org_id:UUID}} GROUP BY project_id"
)
# Compressed bytes on disk per row, over the table's live parts.
BYTES_PER_ROW_SQL = (
    "SELECT if(sum(rows) = 0, 0, sum(bytes_on_disk) / sum(rows)) FROM system.parts "
    "WHERE active AND database = currentDatabase() AND table = {table:String}"
)


class StorageRepository:
    """Row counts and sizes from ClickHouse."""

    def __init__(self, client: AsyncClient) -> None:
        """Create the repository.

        Args:
            client: ClickHouse client.
        """
        self._client = client

    async def log_rows(self, org_id: UuidV7) -> list[ProjectRows]:
        """Log lines per project of the organization.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        return await self._project_rows(LOG_ROWS_SQL, org_id)

    async def span_rows(self, org_id: UuidV7) -> list[ProjectRows]:
        """Request steps (spans) per project of the organization.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        return await self._project_rows(SPAN_ROWS_SQL, org_id)

    async def bytes_per_row(self, table: str) -> float:
        """Average compressed size of a row of `table` on disk; 0 for an empty table.

        Raises:
            StorageUnavailableError: ClickHouse can't be reached.
        """
        rows = await self._rows(BYTES_PER_ROW_SQL, {"table": table})
        return float(rows[0][0])

    async def _project_rows(self, sql: str, org_id: UuidV7) -> list[ProjectRows]:
        rows = await self._rows(sql, {"org_id": org_id})
        return [
            ProjectRows(
                project_id=row[0], rows=row[1], oldest=as_utc(row[2]), newest=as_utc(row[3])
            )
            for row in rows
        ]

    async def _rows(self, sql: str, parameters: dict[str, Any]) -> list[Sequence[Any]]:
        try:
            result = await self._client.query(sql, parameters=parameters)
        except OperationalError as error:
            raise StorageUnavailableError(STORAGE_UNAVAILABLE_DETAIL) from error
        return list(result.result_rows)
