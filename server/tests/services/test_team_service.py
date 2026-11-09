from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeApiKeyStore, FakeSessionStore, FakeTeamStore, FakeUserStore

from spanport_server.core.constants import ACCOUNT_EXISTS_DETAIL, NOT_INVITABLE_DETAIL
from spanport_server.core.errors import (
    ConflictError,
    InvalidRequestError,
    InviteLinkError,
    NotAllowedError,
    NotFoundError,
)
from spanport_server.schemas.api_key import CreateKeyRequest, KeyType, Scope
from spanport_server.schemas.auth import Caller, Role, UserRecord
from spanport_server.schemas.team import AcceptInviteRequest, InviteRequest
from spanport_server.services.api_key_service import ApiKeyService
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
        self.keys = FakeApiKeyStore()
        self.store = FakeTeamStore(self.users, keys=self.keys)
        self.team = TeamService(self.store, self.sessions, lambda: self.now)
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


async def make_keys(team: Team, by: UserRecord) -> None:
    """An admin key and a data key created by `by` in the UI."""
    keys = ApiKeyService(team.store.tenants, team.keys)
    team.store.tenants.org_ids["acme"] = by.org_id
    project = await team.store.tenants.get_or_create_project("acme", "web", "shop", "production")
    await keys.create_key(
        team.caller(by),
        CreateKeyRequest(name="ci", key_type=KeyType.ADMIN, scopes=[Scope.LOGS_READ]),
    )
    await keys.create_key(
        team.caller(by),
        CreateKeyRequest(name="app", key_type=KeyType.INGEST, project_id=project.project_id),
    )


def revoked_types(team: Team) -> dict[KeyType, bool]:
    return {
        record.key_type: record.revoked_at is not None
        for record in team.keys.records_by_hash.values()
    }


async def test_removing_a_user_cancels_their_invites_and_admin_keys(
    team: Team, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO")
    token = await team.invite("new@example.com", by=team.admin)
    owners_token = await team.invite("other@example.com")
    await make_keys(team, team.admin)

    await team.team.remove_user(team.caller(team.owner), team.admin.id)

    with pytest.raises(InviteLinkError):
        await team.auth.inspect_invite(token)
    assert (await team.auth.inspect_invite(owners_token)).email == "other@example.com"
    assert revoked_types(team) == {KeyType.ADMIN: True, KeyType.INGEST: False}
    assert "invites_cancelled=1 keys_revoked=1" in caplog.text


async def test_demoting_an_admin_takes_back_their_invites_and_admin_keys(team: Team) -> None:
    token = await team.invite("new@example.com", by=team.admin)
    await make_keys(team, team.admin)

    await team.team.change_role(team.caller(team.owner), team.admin.id, Role.MEMBER)

    with pytest.raises(InviteLinkError):
        await team.auth.inspect_invite(token)
    assert revoked_types(team)[KeyType.ADMIN] is True


async def test_promoting_an_admin_keeps_their_invites_and_keys(team: Team) -> None:
    token = await team.invite("new@example.com", by=team.admin)
    await make_keys(team, team.admin)

    await team.team.change_role(team.caller(team.owner), team.admin.id, Role.OWNER)

    assert (await team.auth.inspect_invite(token)).email == "new@example.com"
    assert revoked_types(team) == {KeyType.ADMIN: False, KeyType.INGEST: False}


async def test_a_role_that_changed_meanwhile_is_not_overwritten(team: Team) -> None:
    member = team.users.add_user("m@example.com", "hash", Role.MEMBER, org_id=team.owner.org_id)
    # An owner made them an owner after the admin's page was loaded.
    team.store.role_changed_meanwhile = Role.OWNER

    with pytest.raises(ConflictError, match="changed meanwhile"):
        await team.team.change_role(team.caller(team.admin), member.id, Role.VIEWER)
    assert team.users.users[member.id][0].role is Role.OWNER

    # Now an owner removes them, but meanwhile someone made them a viewer.
    team.store.role_changed_meanwhile = Role.VIEWER
    with pytest.raises(ConflictError, match="changed meanwhile"):
        await team.team.remove_user(team.caller(team.owner), member.id)
    assert member.id not in team.users.disabled


async def test_an_account_elsewhere_is_refused_without_saying_it_exists(team: Team) -> None:
    team.users.add_user("someone@elsewhere.com", "hash", Role.OWNER)

    with pytest.raises(ConflictError) as elsewhere:
        await team.invite("someone@elsewhere.com")
    with pytest.raises(ConflictError) as here:
        await team.invite("admin@example.com")

    assert elsewhere.value.detail == NOT_INVITABLE_DETAIL
    assert "account" not in elsewhere.value.detail
    assert here.value.detail == ACCOUNT_EXISTS_DETAIL
    assert elsewhere.value.code == here.value.code
