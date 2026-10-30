"""Brings the Postgres and ClickHouse schemas up to date, or rolls either back one step."""

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class PostgresSchema(Protocol):
    """Runs Postgres migrations."""

    async def upgrade_to_latest(self) -> None:
        """Apply every pending Postgres migration."""
        ...

    async def downgrade_one(self) -> None:
        """Revert the latest applied Postgres migration."""
        ...


class ClickHouseSchema(Protocol):
    """Runs ClickHouse migrations."""

    def available_versions(self) -> list[str]:
        """Every migration version, oldest first."""
        ...

    async def applied_versions(self) -> list[str]:
        """Versions already applied, oldest first."""
        ...

    async def apply(self, version: str) -> None:
        """Run a migration's up step."""
        ...

    async def revert(self, version: str) -> None:
        """Run a migration's down step."""
        ...


class SchemaMigrationService:
    """Orders and runs schema migrations."""

    def __init__(self, postgres: PostgresSchema, clickhouse: ClickHouseSchema) -> None:
        """Create the service.

        Args:
            postgres: Postgres migrations.
            clickhouse: ClickHouse migrations.
        """
        self._postgres = postgres
        self._clickhouse = clickhouse

    async def upgrade(self) -> list[str]:
        """Apply pending Postgres migrations, then pending ClickHouse migrations in order.

        Returns:
            The ClickHouse versions applied.
        """
        await self._postgres.upgrade_to_latest()
        applied = set(await self._clickhouse.applied_versions())
        pending = [v for v in self._clickhouse.available_versions() if v not in applied]
        for version in pending:
            await self._clickhouse.apply(version)
            logger.info("clickhouse migration applied version=%s", version)
        logger.info("migrations done postgres=latest clickhouse_applied=%d", len(pending))
        return pending

    async def rollback_clickhouse(self) -> str | None:
        """Revert the latest applied ClickHouse migration.

        Returns:
            The version reverted, or None if none was applied.
        """
        applied = await self._clickhouse.applied_versions()
        if not applied:
            logger.info("clickhouse rollback skipped: no migrations applied")
            return None
        latest = applied[-1]
        await self._clickhouse.revert(latest)
        logger.info("clickhouse migration reverted version=%s", latest)
        return latest

    async def rollback_postgres(self) -> None:
        """Revert the latest applied Postgres migration.

        Raises:
            InvalidRequestError: Nothing to revert, or Alembic refused.
        """
        await self._postgres.downgrade_one()
        logger.info("postgres migration reverted one step")
