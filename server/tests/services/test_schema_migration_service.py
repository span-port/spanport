import pytest
from fakes import FakeClickHouseSchema, FakePostgresSchema

from spanport_server.services.schema_migration_service import SchemaMigrationService

pytestmark = pytest.mark.anyio


async def test_upgrade_runs_postgres_then_pending_clickhouse_in_order() -> None:
    postgres = FakePostgresSchema()
    clickhouse = FakeClickHouseSchema(
        available=["0001_logs", "0002_spans", "0003_rollups"], applied=["0001_logs"]
    )

    applied_now = await SchemaMigrationService(postgres, clickhouse).upgrade()

    assert postgres.upgraded
    assert applied_now == ["0002_spans", "0003_rollups"]
    assert clickhouse.applied == ["0001_logs", "0002_spans", "0003_rollups"]


async def test_upgrade_with_nothing_pending_applies_nothing() -> None:
    clickhouse = FakeClickHouseSchema(available=["0001_logs"], applied=["0001_logs"])

    assert await SchemaMigrationService(FakePostgresSchema(), clickhouse).upgrade() == []


async def test_rollback_reverts_only_the_latest_clickhouse_migration() -> None:
    clickhouse = FakeClickHouseSchema(
        available=["0001_logs", "0002_spans"], applied=["0001_logs", "0002_spans"]
    )

    reverted = await SchemaMigrationService(FakePostgresSchema(), clickhouse).rollback_clickhouse()

    assert reverted == "0002_spans"
    assert clickhouse.applied == ["0001_logs"]


async def test_rollback_with_nothing_applied_does_nothing() -> None:
    clickhouse = FakeClickHouseSchema(available=["0001_logs"], applied=[])

    service = SchemaMigrationService(FakePostgresSchema(), clickhouse)

    assert await service.rollback_clickhouse() is None


async def test_rollback_postgres_reverts_one_step_and_leaves_clickhouse_alone() -> None:
    postgres = FakePostgresSchema()
    clickhouse = FakeClickHouseSchema(available=["0001_logs"], applied=["0001_logs"])

    await SchemaMigrationService(postgres, clickhouse).rollback_postgres()

    assert postgres.downgrades == 1
    assert clickhouse.applied == ["0001_logs"]
