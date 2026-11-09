"""Who sees colleagues' emails in the alert assignee list: owners and admins only."""

import pytest
from fakes import FakeAlertEventStore, FakeAssigneeStore, FakeTenantStore

from spanport_server.core.ids import new_id
from spanport_server.schemas.alert import AssigneeItem
from spanport_server.schemas.auth import Caller, Role
from spanport_server.services.alert_event_service import AlertEventService
from spanport_server.services.alert_notifier import AlertNotifier

pytestmark = pytest.mark.anyio


async def list_as(role: Role) -> list[str | None]:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "web", "shop", "production")
    assignees = FakeAssigneeStore()
    assignees.people.append(AssigneeItem(id=new_id(), name="Priya", email="priya@example.com"))
    service = AlertEventService(FakeAlertEventStore(), tenants, assignees, AlertNotifier(None))
    caller = Caller(org_id=project.org_id, label="user=test", user_id=new_id(), role=role)

    listed = await service.list_assignees(caller, project.project_id)

    assert [person.name for person in listed.data] == ["Priya"]
    return [person.email for person in listed.data]


@pytest.mark.parametrize("role", [Role.OWNER, Role.ADMIN])
async def test_owners_and_admins_see_assignee_emails(role: Role) -> None:
    assert await list_as(role) == ["priya@example.com"]


@pytest.mark.parametrize("role", [Role.MEMBER, Role.VIEWER])
async def test_members_and_viewers_see_names_only(role: Role) -> None:
    assert await list_as(role) == [None]
