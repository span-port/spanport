import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spanport_server.core.config import DatabaseSettings
from spanport_server.core.constants import ALEMBIC_CONFIG_PATH
from spanport_server.core.errors import ConflictError, InvalidRequestError
from spanport_server.core.ids import new_id
from spanport_server.core.key_hashing import hash_api_key
from spanport_server.repositories.postgres.api_key_repository import ApiKeyRepository
from spanport_server.repositories.postgres.database import create_postgres_engine
from spanport_server.repositories.postgres.schema_repository import PostgresSchemaRepository
from spanport_server.repositories.postgres.tenant_repository import TenantRepository
from spanport_server.schemas.api_key import KeyType, Scope
from spanport_server.schemas.tenant import ProjectRef

pytestmark = pytest.mark.anyio

RAW_KEY = "sp_ingest_repository-test-key-0000000000a1b2"
ADMIN_RAW_KEY = "sp_admin_repository-test-key-00000000000c3d4"


async def public_tables(settings: DatabaseSettings) -> set[str]:
    engine = create_postgres_engine(settings)
    async with engine.connect() as connection:
        tables = await connection.scalars(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        names = set(tables)
    await engine.dispose()
    return names


async def make_project(sessionmaker: async_sessionmaker[AsyncSession]) -> ProjectRef:
    return await TenantRepository(sessionmaker).get_or_create_project(
        "acme", "northwind", "hr-portal", "production"
    )


async def test_downgrade_one_steps_back_one_migration_at_a_time_then_refuses_at_base(
    postgres_settings: DatabaseSettings,
) -> None:
    schema = PostgresSchemaRepository(postgres_settings)

    await schema.downgrade_one()
    assert "project_members" not in await public_tables(postgres_settings)
    await schema.downgrade_one()
    assert "login_failures" not in await public_tables(postgres_settings)
    await schema.downgrade_one()
    assert "invites" not in await public_tables(postgres_settings)
    await schema.downgrade_one()
    assert {"alert_rules", "alert_events"}.isdisjoint(await public_tables(postgres_settings))
    await schema.downgrade_one()
    await schema.downgrade_one()
    assert "users" in await public_tables(postgres_settings)
    await schema.downgrade_one()
    tables = await public_tables(postgres_settings)
    assert "api_keys" in tables
    assert {"users", "user_sessions", "setup_tokens"}.isdisjoint(tables)
    await schema.downgrade_one()
    assert "api_keys" in await public_tables(postgres_settings)
    await schema.downgrade_one()
    assert await public_tables(postgres_settings) == {"alembic_version"}
    with pytest.raises(InvalidRequestError):
        await schema.downgrade_one()


async def test_get_or_create_project_returns_the_same_ids_every_time(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    tenants = TenantRepository(postgres_sessionmaker)

    first = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    again = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    staging = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "staging")

    assert first == again
    assert staging.org_id == first.org_id
    assert staging.project_id != first.project_id
    assert first.project_id.version == 7


async def test_finds_orgs_and_checks_projects_belong_to_them(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    tenants = TenantRepository(postgres_sessionmaker)
    project = await make_project(postgres_sessionmaker)

    assert await tenants.find_org_id("acme") == project.org_id
    assert await tenants.find_org_id("nobody") is None
    assert await tenants.project_exists(project.org_id, project.project_id) is True
    assert await tenants.project_exists(new_id(), project.project_id) is False


async def test_lists_projects_of_one_org_in_id_order_after_a_cursor(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    tenants = TenantRepository(postgres_sessionmaker)
    production = await make_project(postgres_sessionmaker)
    staging = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "staging")
    await tenants.get_or_create_project("globex", "client", "app", "production")

    everything = await tenants.list_projects(production.org_id, after_id=None, limit=10)
    after_first = await tenants.list_projects(
        production.org_id, after_id=production.project_id, limit=10
    )

    assert [item.id for item in everything] == [production.project_id, staging.project_id]
    assert (everything[0].client, everything[0].project) == ("northwind", "hr-portal")
    assert [item.environment for item in after_first] == ["staging"]


async def test_creates_a_project_once_and_its_client_if_new(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    tenants = TenantRepository(postgres_sessionmaker)
    existing = await make_project(postgres_sessionmaker)

    created = await tenants.create_project(existing.org_id, "globex", "tracking-api", "staging")
    duplicate = await tenants.create_project(existing.org_id, "globex", "tracking-api", "staging")
    listed = await tenants.list_projects(existing.org_id, after_id=None, limit=10)

    assert created is not None
    assert duplicate is None
    assert created in listed
    assert len(listed) == 2


async def test_archiving_a_project_stops_its_data_keys_until_restored(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    tenants = TenantRepository(postgres_sessionmaker)
    keys = ApiKeyRepository(postgres_sessionmaker)
    project = await make_project(postgres_sessionmaker)
    await keys.insert_key(project.org_id, project.project_id, KeyType.INGEST, "data-hash", "a1b2")

    archived = await tenants.set_archived(project.org_id, project.project_id, datetime.now(UTC))
    while_archived = await keys.find_by_hash("data-hash")
    await tenants.set_archived(project.org_id, project.project_id, None)

    assert archived is not None and archived.archived
    assert while_archived is None
    assert await keys.find_by_hash("data-hash") is not None
    assert await tenants.set_archived(new_id(), project.project_id, None) is None


async def test_deleting_a_project_deletes_its_keys_and_only_revoked_keys_can_be_deleted(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    tenants = TenantRepository(postgres_sessionmaker)
    keys = ApiKeyRepository(postgres_sessionmaker)
    project = await make_project(postgres_sessionmaker)
    data_key = await keys.insert_key(
        project.org_id, project.project_id, KeyType.INGEST, "data-hash", "a1b2"
    )
    other = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "staging")
    other_key = await keys.insert_key(
        other.org_id, other.project_id, KeyType.INGEST, "other-hash", "c3d4"
    )

    assert await keys.delete_revoked(other.org_id, other_key.id) is False
    await keys.revoke(other.org_id, other_key.id, datetime.now(UTC))
    assert await keys.delete_revoked(other.org_id, other_key.id) is True
    assert await tenants.delete_project(project.org_id, project.project_id) is True
    assert await tenants.delete_project(project.org_id, project.project_id) is False

    assert await tenants.find_project(project.org_id, project.project_id) is None
    assert await keys.find_by_hash("data-hash") is None
    assert data_key.id not in [key.id for key in await keys.list_for_org(project.org_id)]


async def test_renaming_a_project_to_an_existing_one_is_a_conflict(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    tenants = TenantRepository(postgres_sessionmaker)
    production = await make_project(postgres_sessionmaker)
    await tenants.get_or_create_project("acme", "northwind", "hr-portal", "staging")

    renamed = await tenants.update_project(
        production.org_id, production.project_id, "hr-api", "production"
    )

    assert renamed is not None and renamed.project == "hr-api"
    with pytest.raises(ConflictError):
        await tenants.update_project(
            production.org_id, production.project_id, "hr-portal", "staging"
        )


async def test_keys_have_names_and_page_newest_first(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    keys = ApiKeyRepository(postgres_sessionmaker)
    project = await make_project(postgres_sessionmaker)
    for number in range(3):
        await keys.insert_key(
            project.org_id,
            project.project_id,
            KeyType.INGEST,
            f"hash-{number}",
            f"000{number}",
            name=f"key-{number}",
        )

    first_page = await keys.list_page(project.org_id, None, 2)
    second_page = await keys.list_page(project.org_id, first_page[-1].id, 2)

    assert [key.name for key in first_page] == ["key-2", "key-1"]
    assert [key.name for key in second_page] == ["key-0"]
    assert await keys.list_page(new_id(), None, 10) == []


async def test_stores_a_data_key_and_finds_it_by_hash(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    project = await make_project(postgres_sessionmaker)
    keys = ApiKeyRepository(postgres_sessionmaker)

    stored = await keys.insert_key(
        project.org_id, project.project_id, KeyType.INGEST, hash_api_key(RAW_KEY), "a1b2"
    )
    found = await keys.find_by_hash(hash_api_key(RAW_KEY))

    assert found is not None
    assert found == stored
    assert found.project_id == project.project_id
    assert found.revoked_at is None
    assert await keys.find_by_hash(hash_api_key("sp_ingest_other")) is None


async def test_stores_an_admin_key_with_scopes_and_expiry(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    project = await make_project(postgres_sessionmaker)
    keys = ApiKeyRepository(postgres_sessionmaker)
    expires_at = datetime.now(UTC) + timedelta(days=30)

    stored = await keys.insert_key(
        project.org_id,
        None,
        KeyType.ADMIN,
        hash_api_key(ADMIN_RAW_KEY),
        "c3d4",
        scopes=(Scope.LOGS_READ,),
        expires_at=expires_at,
    )

    assert stored.project_id is None
    assert stored.scopes == (Scope.LOGS_READ,)
    assert stored.expires_at == expires_at


@pytest.mark.parametrize(
    ("project_id_given", "expires_in_days"),
    [(False, None), (False, 91), (True, 30)],
    ids=["admin-without-expiry", "admin-over-90-days", "admin-with-project"],
)
async def test_database_refuses_admin_keys_that_break_the_rules(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
    project_id_given: bool,
    expires_in_days: int | None,
) -> None:
    project = await make_project(postgres_sessionmaker)
    expires_at = (
        None if expires_in_days is None else datetime.now(UTC) + timedelta(days=expires_in_days)
    )

    with pytest.raises(IntegrityError):
        await ApiKeyRepository(postgres_sessionmaker).insert_key(
            project.org_id,
            project.project_id if project_id_given else None,
            KeyType.ADMIN,
            hash_api_key(ADMIN_RAW_KEY),
            "c3d4",
            scopes=(Scope.LOGS_READ,),
            expires_at=expires_at,
        )


async def test_lists_and_revokes_keys_only_within_the_org(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    project = await make_project(postgres_sessionmaker)
    keys = ApiKeyRepository(postgres_sessionmaker)
    stored = await keys.insert_key(
        project.org_id, project.project_id, KeyType.INGEST, hash_api_key(RAW_KEY), "a1b2"
    )
    now = datetime.now(UTC)

    assert [record.id for record in await keys.list_for_org(project.org_id)] == [stored.id]
    assert await keys.revoke(new_id(), stored.id, now) is False
    assert await keys.revoke(project.org_id, stored.id, now) is True
    assert await keys.revoke(project.org_id, stored.id, now) is False
    found = await keys.find_by_hash(hash_api_key(RAW_KEY))
    assert found is not None
    assert found.revoked_at == now


async def test_downgrade_removes_every_table(postgres_settings: DatabaseSettings) -> None:
    config = Config(str(ALEMBIC_CONFIG_PATH))
    config.attributes["settings"] = postgres_settings

    await asyncio.to_thread(command.downgrade, config, "base")

    assert await public_tables(postgres_settings) == {"alembic_version"}
