"""Applies and reverts Postgres migrations with Alembic."""

import asyncio

from alembic import command
from alembic.config import Config
from alembic.util import CommandError

from spanport_server.core.config import DatabaseSettings
from spanport_server.core.constants import (
    ALEMBIC_CONFIG_PATH,
    ALEMBIC_LATEST_REVISION,
    ALEMBIC_PREVIOUS_REVISION,
)
from spanport_server.core.errors import InvalidRequestError


class PostgresSchemaRepository:
    """Runs Alembic against the configured database."""

    def __init__(self, settings: DatabaseSettings) -> None:
        """Create the repository.

        Args:
            settings: Connection settings, passed to db/postgres/migrations/env.py.
        """
        self._settings = settings

    async def upgrade_to_latest(self) -> None:
        """Apply every pending Postgres migration."""
        # Alembic runs its own event loop in env.py, so it needs a thread without one.
        await asyncio.to_thread(command.upgrade, self._alembic_config(), ALEMBIC_LATEST_REVISION)

    async def downgrade_one(self) -> None:
        """Revert the latest applied Postgres migration.

        Raises:
            InvalidRequestError: Nothing to revert, or Alembic refused (its message says why).
        """
        try:
            await asyncio.to_thread(
                command.downgrade, self._alembic_config(), ALEMBIC_PREVIOUS_REVISION
            )
        except CommandError as error:
            raise InvalidRequestError(f"Postgres rollback failed: {error}") from error

    def _alembic_config(self) -> Config:
        """Alembic config for db/postgres, carrying the connection settings to env.py."""
        config = Config(str(ALEMBIC_CONFIG_PATH))
        config.attributes["settings"] = self._settings
        return config
