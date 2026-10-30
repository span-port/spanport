from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeSessionStore, FakeTeamStore, FakeUserStore

from spanport_server.core.errors import (
    ConflictError,
    InvalidRequestError,
    InviteLinkError,
    NotAllowedError,
    NotFoundError,
)
from spanport_server.schemas.auth import Caller, Role, UserRecord
from spanport_server.schemas.team import AcceptInviteRequest, InviteRequest
from spanport_server.services.auth_service import AuthService
from spanport_server.services.team_service import TeamService

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
PASSWORD = "a long enough passphrase"


class Team:
    """An org with an owner and an admin, and the services wired to fakes."""

    def __init__(self) -> None:
        self.now = NOW
        self.users = FakeUserStore()
        self.sessions = FakeSessionStore()
        self.owner = self.users.add_user("owner@example.com", "hash", Role.OWNER)
        self.admin = self.users.add_user(
            "admin@example.com", "hash", Role.ADMIN, org_id=self.owner.org_id
        )
        self.team = TeamService(FakeTeamStore(self.users), self.sessions, lambda: self.now)
        self.auth = AuthService(self.users, self.sessions, lambda: self.now)

    def caller(self, user: UserRecord) -> Caller:
        return Caller(org_id=user.org_id, label="user=test", user_id=user.id, role=user.role)

    async def invite(
        self, email: str, role: Role = Role.MEMBER, by: UserRecord | None = None
    ) -> str:
        created = await self.team.create_invite(
            self.caller(by or self.owner), InviteRequest(email=email, role=role)
        )
        return created.token

    async def accept(self, token: str, name: str = "New Person") -> UserRecord:
        signed_in = await self.auth.accept_invite(
            AcceptInviteRequest(token=token, name=name, password=PASSWORD)
        )
        return signed_in.user


@pytest.fixture
def team() -> Team:
    return Team()


async def test_an_invite_grants_nothing_until_it_is_accepted(team: Team) -> None:
    token = await team.invite("New@Example.com")

    assert await team.users.find_for_login("new@example.com") is None
    details = await team.auth.inspect_invite(token)
    user = await team.accept(token)

    assert (details.email, details.role) == ("new@example.com", Role.MEMBER)
    assert (user.email, user.role, user.org_id) == (
        "new@example.com",
        Role.MEMBER,
        team.owner.org_id,
    )
    with pytest.raises(InviteLinkError):
        await team.accept(token)


async def test_a_mistyped_invite_is_cancelled_and_its_link_dies(team: Team) -> None:
    token = await team.invite("nitsh@example.com")
    (pending,) = (await team.team.list_invites(team.caller(team.owner), None, 10)).data

    await team.team.cancel_invite(team.caller(team.owner), pending.id)

    with pytest.raises(InviteLinkError):
        await team.auth.inspect_invite(token)
    assert (await team.team.list_invites(team.caller(team.owner), None, 10)).data == []


async def test_inviting_again_replaces_the_earlier_link(team: Team) -> None:
    first = await team.invite("new@example.com")
    second = await team.invite("new@example.com", Role.VIEWER)

    with pytest.raises(InviteLinkError):
        await team.accept(first)
    assert (await team.accept(second)).role == Role.VIEWER


async def test_invites_expire_after_a_week(team: Team) -> None:
    token = await team.invite("new@example.com")
    team.now = NOW + timedelta(days=7)

    with pytest.raises(InviteLinkError):
        await team.accept(token)


async def test_accepting_needs_a_strong_password(team: Team) -> None:
    token = await team.invite("new@example.com")

    with pytest.raises(InvalidRequestError):
        await team.auth.accept_invite(AcceptInviteRequest(token=token, name="N", password="short"))
    assert (await team.accept(token)).email == "new@example.com"


async def test_an_email_with_an_account_cannot_be_invited(team: Team) -> None:
    with pytest.raises(ConflictError):
        await team.invite("admin@example.com")


async def test_admins_cannot_invite_or_change_owners(team: Team) -> None:
    admin = team.caller(team.admin)

    with pytest.raises(NotAllowedError):
        await team.invite("boss@example.com", Role.OWNER, by=team.admin)
    with pytest.raises(NotAllowedError):
        await team.team.change_role(admin, team.owner.id, Role.MEMBER)
    with pytest.raises(NotAllowedError):
        await team.team.remove_user(admin, team.owner.id)


async def test_nobody_changes_themselves_and_the_last_owner_stays(team: Team) -> None:
    second_owner = team.users.add_user(
        "second@example.com", "hash", Role.OWNER, org_id=team.owner.org_id
    )
    with pytest.raises(NotAllowedError):
        await team.team.change_role(team.caller(team.owner), team.owner.id, Role.ADMIN)

    await team.team.change_role(team.caller(team.owner), second_owner.id, Role.ADMIN)

    with pytest.raises(ConflictError):
        await team.team.change_role(team.caller(second_owner), team.owner.id, Role.ADMIN)


async def test_removing_signs_the_user_out_and_they_can_be_invited_back(team: Team) -> None:
    await team.sessions.insert(team.admin.id, "token-hash", "csrf-hash")

    await team.team.remove_user(team.caller(team.owner), team.admin.id)

    assert team.sessions.sessions["token-hash"].revoked_at is not None
    assert await team.users.find_for_login("admin@example.com") is None
    listed = (await team.team.list_users(team.caller(team.owner), None, 10)).data
    assert [user.email for user in listed] == ["owner@example.com"]
    back = await team.accept(await team.invite("admin@example.com", Role.VIEWER))
    assert back.role == Role.VIEWER


async def test_another_org_cannot_touch_these_users(team: Team) -> None:
    stranger = team.users.add_user("other@example.com", "hash", Role.OWNER)

    with pytest.raises(NotFoundError):
        await team.team.remove_user(team.caller(stranger), team.admin.id)
