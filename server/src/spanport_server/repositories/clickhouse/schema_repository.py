"""Applies ClickHouse migrations: db/clickhouse/migrations/<NNNN_name>/up.sql and down.sql.

Each file holds one statement. Applied versions are recorded in schema_migrations.
"""

from pathlib import Path

from clickhouse_connect.driver.asyncclient import AsyncClient

from spanport_server.core.constants import (
    CLICKHOUSE_DOWN_FILE,
    CLICKHOUSE_MIGRATIONS_DIR,
    CLICKHOUSE_UP_FILE,
)

CREATE_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations
(
    version String,
    applied_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY version
"""
SELECT_APPLIED = "SELECT version FROM schema_migrations ORDER BY version"
INSERT_APPLIED = "INSERT INTO schema_migrations (version) VALUES ({version:String})"
DELETE_APPLIED = "DELETE FROM schema_migrations WHERE version = {version:String}"


class ClickHouseSchemaRepository:
    """Reads migration files and runs them against ClickHouse."""

    def __init__(
        self, client: AsyncClient, migrations_dir: Path = CLICKHOUSE_MIGRATIONS_DIR
    ) -> None:
        """Create the repository.

        Args:
            client: ClickHouse client for the target database.
            migrations_dir: Folder holding one sub-folder per migration.
        """
        self._client = client
        self._migrations_dir = migrations_dir

    def available_versions(self) -> list[str]:
        """Return every migration folder name, oldest first."""
        return sorted(path.name for path in self._migrations_dir.iterdir() if path.is_dir())

    async def applied_versions(self) -> list[str]:
        """Return the versions already applied, oldest first."""
        await self._client.command(CREATE_HISTORY_TABLE)
        result = await self._client.query(SELECT_APPLIED)
        return [row[0] for row in result.result_rows]

    async def apply(self, version: str) -> None:
        """Run a migration's up.sql and record it as applied."""
        await self._client.command(CREATE_HISTORY_TABLE)
        await self._client.command(self._read(version, CLICKHOUSE_UP_FILE))
        await self._client.command(INSERT_APPLIED, parameters={"version": version})

    async def revert(self, version: str) -> None:
        """Run a migration's down.sql and remove its applied record."""
        await self._client.command(CREATE_HISTORY_TABLE)
        await self._client.command(self._read(version, CLICKHOUSE_DOWN_FILE))
        await self._client.command(DELETE_APPLIED, parameters={"version": version})

    def _read(self, version: str, file_name: str) -> str:
        """Read one migration file."""
        return (self._migrations_dir / version / file_name).read_text(encoding="utf-8")
