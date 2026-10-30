from datetime import UTC, datetime, timedelta

import pytest
from fakes import (
    FakeAlertEventStore,
    FakeAlertRuleStore,
    FakeLogSearchStore,
    FakeLogWriter,
    FakeSessionStore,
    FakeTeamStore,
    FakeTenantStore,
    FakeUserStore,
)

from spanport_server.core.errors import InvalidRequestError, NotFoundError
from spanport_server.core.ids import UuidV7
from spanport_server.schemas.alert import AlertRuleFields
from spanport_server.schemas.auth import Caller, Role, UserRecord
from spanport_server.schemas.log_search import LogSearchRequest
from spanport_server.schemas.team import AcceptInviteRequest, InviteRequest, ProjectAccess
from spanport_server.schemas.tenant import ProjectRef
from spanport_server.services.alert_event_service import AlertEventService
from spanport_server.services.auth_service import AuthService
from spanport_server.services.log_search_service import LogSearchService
from spanport_server.services.project_service import ProjectService
from spanport_server.services.team_service import TeamService

pytestmark = pytest.mark.anyio

PASSWORD = "a long enough passphrase"


def caller_of(user: UserRecord) -> Caller:
    return Caller(
        org_id=user.org_id,
        label="user=test",
        user_id=user.id,
        role=user.role,
        project_ids=user.project_ids,
    )


class Org:
    """An org with two projects, an owner, and the services wired to fakes."""

    def __init__(self, tenants: FakeTenantStore, northwind: ProjectRef, globex: ProjectRef) -> None:
        self.tenants = tenants
        self.northwind = northwind.project_id
        self.globex = globex.project_id
        self.users = FakeUserStore()
        self.owner = self.users.add_user("owner@x.com", "h", Role.OWNER, org_id=northwind.org_id)
        sessions = FakeSessionStore()
        self.team = TeamService(FakeTeamStore(self.users, tenants), sessions)
        self.auth = AuthService(self.users, sessions)

    async def join(self, role: Role, access: ProjectAccess) -> UserRecord:
        created = await self.team.create_invite(
            caller_of(self.owner),
            InviteRequest(email=f"{role}@x.com", role=role, **access.model_dump()),
        )
        signed_in = await self.auth.accept_invite(
            AcceptInviteRequest(token=created.token, name="New", password=PASSWORD)
        )
        return signed_in.user

    def only(self, *project_ids: UuidV7) -> ProjectAccess:
        return ProjectAccess(all_projects=False, project_ids=list(project_ids))


@pytest.fixture
async def org() -> Org:
    tenants = FakeTenantStore()
    northwind = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    globex = await tenants.get_or_create_project("acme", "globex", "tracking", "production")
    return Org(tenants, northwind, globex)


def search(project_id: UuidV7) -> LogSearchRequest:
    now = datetime.now(UTC)
    return LogSearchRequest(project_id=project_id, start=now - timedelta(hours=1), end=now)


async def test_a_limited_member_sees_only_their_projects(org: Org) -> None:
    member = await org.join(Role.MEMBER, org.only(org.northwind))
    logs = LogSearchService(org.tenants, FakeLogSearchStore())
    projects = ProjectService(org.tenants, FakeLogWriter())

    listed = await projects.list_projects(caller_of(member), None, 10)
    await logs.search(caller_of(member), search(org.northwind))

    assert [project.id for project in listed.data] == [org.northwind]
    with pytest.raises(NotFoundError):
        await logs.search(caller_of(member), search(org.globex))


async def test_all_projects_and_admins_see_everything(org: Org) -> None:
    viewer = await org.join(Role.VIEWER, ProjectAccess())
    # An admin invite ignores a project limit: admins always see every project.
    admin = await org.join(Role.ADMIN, org.only(org.northwind))

    assert viewer.project_ids is None
    assert admin.project_ids is None


async def test_limited_access_needs_real_projects_of_the_org(org: Org) -> None:
    with pytest.raises(InvalidRequestError):
        await org.join(Role.MEMBER, org.only())
    with pytest.raises(InvalidRequestError):
        await org.join(Role.MEMBER, org.only(org.owner.id))


async def test_access_can_be_changed_for_members_but_not_admins(org: Org) -> None:
    member = await org.join(Role.MEMBER, ProjectAccess())
    admin = await org.join(Role.ADMIN, ProjectAccess())

    changed = await org.team.set_project_access(
        caller_of(org.owner), member.id, org.only(org.globex)
    )

    assert (changed.all_projects, changed.project_ids) == (False, [org.globex])
    with pytest.raises(InvalidRequestError):
        await org.team.set_project_access(caller_of(org.owner), admin.id, org.only(org.globex))


async def test_alerts_of_other_projects_cannot_be_seen_or_acknowledged(org: Org) -> None:
    member = await org.join(Role.MEMBER, org.only(org.northwind))
    rules = FakeAlertRuleStore()
    alerts = FakeAlertEventStore(rules)
    settings = AlertRuleFields(
        name="Errors", threshold=0, window_minutes=5, email_recipients=["a@x.com"]
    )
    rule = await rules.insert_rule(org.owner.org_id, org.globex, settings, datetime.now(UTC))
    opened = await alerts.open_alert(org.owner.org_id, rule.id, 3)
    assert opened is not None
    events = AlertEventService(alerts, org.tenants)

    with pytest.raises(NotFoundError):
        await events.list_events(caller_of(member), org.globex, None, 10)
    with pytest.raises(NotFoundError):
        await events.acknowledge(caller_of(member), opened.id)
