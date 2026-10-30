"""ClickHouse connection setup."""

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient

from spanport_server.core.config import DatabaseSettings


async def create_clickhouse_client(settings: DatabaseSettings) -> AsyncClient:
    """Connect to ClickHouse.

    Args:
        settings: Connection settings.

    Returns:
        The async client. Call `close()` when done.
    """
    return await clickhouse_connect.get_async_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password.get_secret_value(),
        database=settings.clickhouse_db,
    )
