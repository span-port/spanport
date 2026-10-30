"""Postgres connection setup."""

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from spanport_server.core.config import DatabaseSettings
from spanport_server.core.constants import POSTGRES_DRIVER


def create_postgres_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create the async engine (a connection pool) for the configured database.

    Args:
        settings: Connection settings.

    Returns:
        The engine. Call `dispose()` when done.
    """
    url = URL.create(
        POSTGRES_DRIVER,
        username=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
    )
    return create_async_engine(url, pool_pre_ping=True)
