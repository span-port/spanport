"""Alembic entry point: runs migrations on the async Postgres engine."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from spanport_server.core.config import DatabaseSettings, load_settings
from spanport_server.models import Base
from spanport_server.repositories.postgres.database import create_postgres_engine


def run_migrations(connection: Connection) -> None:
    """Run pending migrations in one transaction on an open connection."""
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations(settings: DatabaseSettings) -> None:
    """Open the engine, run the migrations, close the engine even if a migration fails."""
    engine = create_postgres_engine(settings)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


# Callers such as the migrate command pass settings in; the alembic CLI reads the environment.
migration_settings = context.config.attributes.get("settings") or load_settings(DatabaseSettings)
asyncio.run(run_async_migrations(migration_settings))
