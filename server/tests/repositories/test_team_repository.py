"""Team and invite repositories against a real Postgres (skipped without the dev databases)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spanport_server.repositories.postgres.team_repository import TeamRepository
from spanport_server.repositories.postgres.tenant_repository import TenantRepository
from spanport_server.repositories.postgres.user_repository import UserRepository
from spanport_server.schemas.auth import Role, UserRecord
from spanport_server.schemas.team import ProjectAccess, TeamChange

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
EXPIRES = NOW + timedelta(days=7)
ALL = ProjectAccess()


async def make_owner(sessionmaker: async_sessionmaker[AsyncSession]) -> UserRecord:
    users = UserRepository(sessionmaker)
    await users.insert_setup_token("setup-hash", NOW + timedelta(hours=1))
    owner = await users.create_owner("setup-hash", NOW, "acme", "Owner", "owner@example.com", "h")
    assert owner is not None
    return owner


async def test_invite_accept_then_remove_and_invite_back(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    owner = await make_owner(postgres_sessionmaker)
    team = TeamRepository(postgres_sessionmaker)
    users = UserRepository(postgres_sessionmaker)

    await team.insert_invite(
        owner.org_id, "new@example.com", Role.MEMBER, ALL, "t1", owner.id, NOW, EXPIRES
    )
    pending = await team.list_open_invites(owner.org_id, NOW, None, 10)
    joined = await users.accept_invite("t1", NOW, "New", "h")
    used_again = await users.accept_invite("t1", NOW, "New", "h")
    assert joined is not None

    assert [invite.invited_by for invite in pending] == ["Owner"]
    assert used_again is None
    assert await team.disable_user(owner.org_id, joined.id, NOW) is TeamChange.DONE
    assert await users.find_by_id(joined.id) is None
    await team.insert_invite(
        owner.org_id, "new@example.com", Role.VIEWER, ALL, "t2", owner.id, NOW, EXPIRES
    )
    back = await users.accept_invite("t2", NOW, "New Again", "h2")
    assert back is not None and (back.id, back.role) == (joined.id, Role.VIEWER)


async def test_a_limited_invite_gives_only_its_projects_until_changed(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    owner = await make_owner(postgres_sessionmaker)
    tenants = TenantRepository(postgres_sessionmaker)
    northwind = await tenants.get_or_create_project("acme", "northwind", "hr", "production")
    globex = await tenants.get_or_create_project("acme", "globex", "tracking", "production")
    team = TeamRepository(postgres_sessionmaker)
    users = UserRepository(postgres_sessionmaker)
    only_northwind = ProjectAccess(all_projects=False, project_ids=[northwind.project_id])

    await team.insert_invite(
        owner.org_id, "new@example.com", Role.MEMBER, only_northwind, "t1", owner.id, NOW, EXPIRES
    )
    joined = await users.accept_invite("t1", NOW, "New", "h")
    assert joined is not None

    assert joined.project_ids == frozenset({northwind.project_id})
    assert await team.count_org_projects(owner.org_id, [globex.project_id, owner.id]) == 1
    assert await team.set_project_access(owner.org_id, joined.id, False, [globex.project_id])
    reloaded = await users.find_by_id(joined.id)
    assert reloaded is not None and reloaded.project_ids == frozenset({globex.project_id})
    listed = await tenants.list_projects(owner.org_id, None, 10, reloaded.project_ids)
    assert [project.id for project in listed] == [globex.project_id]


async def test_the_last_owner_cannot_be_demoted_or_removed(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    owner = await make_owner(postgres_sessionmaker)
    team = TeamRepository(postgres_sessionmaker)

    assert await team.change_role(owner.org_id, owner.id, Role.ADMIN) is TeamChange.LAST_OWNER
    assert await team.disable_user(owner.org_id, owner.id, NOW) is TeamChange.LAST_OWNER
    assert await team.change_role(owner.org_id, owner.id, Role.OWNER) is TeamChange.DONE


async def test_login_failures_are_counted_per_email_and_forgotten(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    users = UserRepository(postgres_sessionmaker)
    window_start = NOW - timedelta(minutes=15)

    await users.record_login_failure("email-a", NOW - timedelta(minutes=20), window_start)
    await users.record_login_failure("email-a", NOW, window_start)
    await users.record_login_failure("email-b", NOW, window_start)

    assert await users.recent_login_failures("email-a", window_start) == [NOW]
    await users.clear_login_failures("email-a")
    assert await users.recent_login_failures("email-a", window_start) == []
    assert len(await users.recent_login_failures("email-b", window_start)) == 1


async def test_a_cancelled_invite_cannot_be_inspected(
    postgres_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    owner = await make_owner(postgres_sessionmaker)
    team = TeamRepository(postgres_sessionmaker)
    invite = await team.insert_invite(
        owner.org_id, "new@example.com", Role.MEMBER, ALL, "t1", owner.id, NOW, EXPIRES
    )

    assert await team.cancel_invite(owner.org_id, invite.id, NOW)
    assert await UserRepository(postgres_sessionmaker).find_open_invite("t1", NOW) is None
