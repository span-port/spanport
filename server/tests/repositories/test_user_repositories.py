"""Users, sessions and setup tokens against a real Postgres (skipped without the dev stack)."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spanport_server.repositories.postgres.session_repository import SessionRepository
from spanport_server.repositories.postgres.team_repository import TeamRepository
from spanport_server.repositories.postgres.tenant_repository import TenantRepository
from spanport_server.repositories.postgres.user_repository import UserRepository
from spanport_server.schemas.auth import Role, UserRecord
from spanport_server.schemas.team import ProjectAccess

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

    long_ago = NOW - timedelta(days=1)
    touched = await sessions.touch_active("session-a", later - timedelta(hours=8), long_ago, later)
    idle = await sessions.touch_active("session-b", later + timedelta(minutes=1), long_ago, later)
    revoked_user = await sessions.revoke("session-a", later)

    assert touched == (owner.id, "csrf-a")
    assert idle is None
    assert revoked_user == owner.id
    assert await sessions.touch_active("session-a", long_ago, long_ago, later) is None
    assert await sessions.revoke("session-a", later) is None
    assert await sessions.revoke_for_user(owner.id, later) == 1
    assert await sessions.touch_active("session-b", long_ago, long_ago, later) is None


async def test_a_session_ends_at_its_maximum_age_however_active(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    users = UserRepository(postgres_sessionmaker)
    sessions = SessionRepository(postgres_sessionmaker)
    await users.insert_setup_token("setup-hash", NOW + timedelta(hours=1))
    owner = await create_owner(users)
    assert owner is not None
    await sessions.insert(owner.id, "session-a", "csrf-a")
    now = datetime.now(UTC)

    young = await sessions.touch_active(
        "session-a", now - timedelta(hours=8), now - timedelta(hours=1), now
    )
    too_old = await sessions.touch_active(
        "session-a", now - timedelta(hours=8), now + timedelta(seconds=1), now
    )

    assert young == (owner.id, "csrf-a")
    assert too_old is None


async def test_setup_tokens_can_be_checked_and_older_ones_expired(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    users = UserRepository(postgres_sessionmaker)
    await users.insert_setup_token("old", NOW + timedelta(hours=1))
    await users.insert_setup_token("stale", NOW - timedelta(seconds=1))

    assert await users.setup_token_usable("old", NOW)
    assert not await users.setup_token_usable("stale", NOW)
    assert not await users.setup_token_usable("unknown", NOW)
    assert await users.expire_setup_tokens(NOW) == 1
    await users.insert_setup_token("new", NOW + timedelta(hours=1))

    assert not await users.setup_token_usable("old", NOW)
    assert await users.setup_token_usable("new", NOW)
    assert await create_owner(users, "old") is None


async def test_two_setups_at_once_create_one_owner(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    users = UserRepository(postgres_sessionmaker)
    await users.insert_setup_token("first", NOW + timedelta(hours=1))
    await users.insert_setup_token("second", NOW + timedelta(hours=1))

    results = await asyncio.gather(
        users.create_owner("first", NOW, "acme", "A", "a@example.com", "h"),
        users.create_owner("second", NOW, "acme", "B", "b@example.com", "h"),
    )

    assert sum(owner is not None for owner in results) == 1
    assert await users.count_users() == 1


async def test_two_invites_for_one_email_accepted_at_once_make_one_account(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    users = UserRepository(postgres_sessionmaker)
    await users.insert_setup_token("setup-hash", NOW + timedelta(hours=1))
    owner = await create_owner(users)
    assert owner is not None
    other_org = await TenantRepository(postgres_sessionmaker).get_or_create_project(
        "globex", "internal", "tools", "production"
    )
    team = TeamRepository(postgres_sessionmaker)
    expires = NOW + timedelta(days=7)
    for org_id, token in ((owner.org_id, "t1"), (other_org.org_id, "t2")):
        await team.insert_invite(
            org_id, "new@example.com", Role.MEMBER, ProjectAccess(), token, owner.id, NOW, expires
        )

    results = await asyncio.gather(
        users.accept_invite("t1", NOW, "New", "h"),
        users.accept_invite("t2", NOW, "New", "h"),
    )

    assert sum(user is not None for user in results) == 1
