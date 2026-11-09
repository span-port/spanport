"""ClickHouse connection setup."""

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient

from spanport_server.core.config import DatabaseSettings
from spanport_server.core.constants import (
    CLICKHOUSE_MAX_EXECUTION_SETTING,
    CLICKHOUSE_MAX_MEMORY_SETTING,
)


def read_limits(settings: DatabaseSettings) -> dict[str, int]:
    """The per-query time and memory limits every query gets unless it overrides them.

    Writes override them with CLICKHOUSE_WRITE_SETTINGS, so the limits bound reads only.

    Args:
        settings: Where SPANPORT_CLICKHOUSE_MAX_EXECUTION_SECONDS / _MAX_MEMORY_BYTES are read.

    Returns:
        ClickHouse settings by name.
    """
    return {
        CLICKHOUSE_MAX_EXECUTION_SETTING: settings.clickhouse_max_execution_seconds,
        CLICKHOUSE_MAX_MEMORY_SETTING: settings.clickhouse_max_memory_bytes,
    }


async def create_clickhouse_client(settings: DatabaseSettings) -> AsyncClient:
    """Connect to ClickHouse, with the read limits applied to every query.

    Args:
        settings: Connection settings and read limits.

    Returns:
        The async client. Call `close()` when done.
    """
    return await clickhouse_connect.get_async_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password.get_secret_value(),
        database=settings.clickhouse_db,
        settings=read_limits(settings),
    )
