"""Real databases for repository tests. Each test gets its own database, dropped afterwards.

Run with the dev stack up: uv run --env-file .env pytest
Without the SPANPORT_ database settings these tests are skipped.
"""

import os
from collections.abc import AsyncIterator

import pytest
from clickhouse_connect.driver.asyncclient import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spanport_server.core.config import DatabaseSettings, load_settings
from spanport_server.core.ids import new_id
from spanport_server.repositories.clickhouse.database import create_clickhouse_client
from spanport_server.repositories.postgres.database import create_postgres_engine
from spanport_server.repositories.postgres.schema_repository import PostgresSchemaRepository


@pytest.fixture
def settings() -> DatabaseSettings:
    if "SPANPORT_POSTGRES_HOST" not in os.environ:
        pytest.skip("needs the dev databases: run uv run --env-file .env pytest")
    return load_settings(DatabaseSettings)


@pytest.fixture
async def postgres_settings(settings: DatabaseSettings) -> AsyncIterator[DatabaseSettings]:
    """Database settings pointing at a fresh, fully migrated Postgres database."""
    test_db = f"spanport_test_{new_id().hex}"
    admin_engine = create_postgres_engine(settings)
    async with admin_engine.connect() as connection:
        autocommit = await connection.execution_options(isolation_level="AUTOCOMMIT")
        await autocommit.execute(text(f'CREATE DATABASE "{test_db}"'))
    test_settings = settings.model_copy(update={"postgres_db": test_db})
    await PostgresSchemaRepository(test_settings).upgrade_to_latest()
    yield test_settings
    async with admin_engine.connect() as connection:
        autocommit = await connection.execution_options(isolation_level="AUTOCOMMIT")
        await autocommit.execute(text(f'DROP DATABASE "{test_db}" WITH (FORCE)'))
    await admin_engine.dispose()


@pytest.fixture
async def postgres_sessionmaker(
    postgres_settings: DatabaseSettings,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_postgres_engine(postgres_settings)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def clickhouse_client(settings: DatabaseSettings) -> AsyncIterator[AsyncClient]:
    """A client on a fresh, empty ClickHouse database."""
    test_db = f"spanport_test_{new_id().hex}"
    admin_client = await create_clickhouse_client(settings)
    await admin_client.command(f"CREATE DATABASE {test_db}")
    client = await create_clickhouse_client(settings.model_copy(update={"clickhouse_db": test_db}))
    yield client
    await client.close()
    await admin_client.command(f"DROP DATABASE {test_db}")
    await admin_client.close()
