"""Users, sessions and setup tokens against a real Postgres (skipped without the dev stack)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spanport_server.repositories.postgres.session_repository import SessionRepository
from spanport_server.repositories.postgres.tenant_repository import TenantRepository
from spanport_server.repositories.postgres.user_repository import UserRepository
from spanport_server.schemas.auth import Role, UserRecord

pytestmark = pytest.mark.anyio

NOW = datetime.now(UTC)


async def create_owner(users: UserRepository, token_hash: str = "setup-hash") -> UserRecord | None:
    return await users.create_owner(
        token_hash, NOW, "acme", "Nitish", "owner@example.com", "argon2-hash"
    )


async def test_owner_is_created_once_per_valid_token_and_joins_an_existing_org(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    users = UserRepository(postgres_sessionmaker)
    project = await TenantRepository(postgres_sessionmaker).get_or_create_project(
        "acme", "northwind", "hr-portal", "production"
    )
    await users.insert_setup_token("setup-hash", NOW + timedelta(hours=1))
    await users.insert_setup_token("expired-hash", NOW - timedelta(seconds=1))

    assert await create_owner(users, "expired-hash") is None
    assert await create_owner(users, "unknown-hash") is None
    owner = await create_owner(users)
    assert await create_owner(users) is None

    assert owner is not None
    assert (owner.role, owner.org_id, owner.org_slug) == (Role.OWNER, project.org_id, "acme")
    assert await users.count_users() == 1


async def test_second_owner_is_refused_even_with_another_valid_token(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    users = UserRepository(postgres_sessionmaker)
    await users.insert_setup_token("first", NOW + timedelta(hours=1))
    await users.insert_setup_token("second", NOW + timedelta(hours=1))

    assert await create_owner(users, "first") is not None
    assert await create_owner(users, "second") is None


async def test_login_lookup_and_password_change(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    users = UserRepository(postgres_sessionmaker)
    await users.insert_setup_token("setup-hash", NOW + timedelta(hours=1))
    owner = await create_owner(users)
    assert owner is not None

    found = await users.find_for_login("owner@example.com")
    changed = await users.set_password("owner@example.com", "new-hash")

    assert found == (owner, "argon2-hash")
    assert await users.find_by_id(owner.id) == owner
    assert changed == owner.id
    assert await users.find_for_login("owner@example.com") == (owner, "new-hash")
    assert await users.find_for_login("nobody@example.com") is None
    assert await users.set_password("nobody@example.com", "x") is None


async def test_database_refuses_upper_case_emails(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    users = UserRepository(postgres_sessionmaker)
    await users.insert_setup_token("setup-hash", NOW + timedelta(hours=1))

    with pytest.raises(IntegrityError):
        await users.create_owner("setup-hash", NOW, "acme", "N", "Owner@Example.com", "hash")


async def test_sessions_stay_alive_with_use_and_end_on_revoke_or_idleness(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    users = UserRepository(postgres_sessionmaker)
    sessions = SessionRepository(postgres_sessionmaker)
    await users.insert_setup_token("setup-hash", NOW + timedelta(hours=1))
    owner = await create_owner(users)
    assert owner is not None
    await sessions.insert(owner.id, "session-a", "csrf-a")
    await sessions.insert(owner.id, "session-b", "csrf-b")
    later = datetime.now(UTC) + timedelta(hours=1)

    touched = await sessions.touch_active("session-a", later - timedelta(hours=8), later)
    idle = await sessions.touch_active("session-b", later + timedelta(minutes=1), later)
    revoked_user = await sessions.revoke("session-a", later)

    assert touched == (owner.id, "csrf-a")
    assert idle is None
    assert revoked_user == owner.id
    assert await sessions.touch_active("session-a", NOW - timedelta(days=1), later) is None
    assert await sessions.revoke("session-a", later) is None
    assert await sessions.revoke_for_user(owner.id, later) == 1
    assert await sessions.touch_active("session-b", NOW - timedelta(days=1), later) is None
