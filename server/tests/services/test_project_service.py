import pytest
from fakes import FakeLogWriter, FakeTenantStore, caller_for

from spanport_server.core.errors import InvalidRequestError
from spanport_server.core.ids import new_id
from spanport_server.services.project_service import ProjectService

pytestmark = pytest.mark.anyio


async def test_pages_through_only_the_callers_org_projects() -> None:
    tenants = FakeTenantStore()
    production = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    await tenants.get_or_create_project("acme", "northwind", "hr-portal", "staging")
    await tenants.get_or_create_project("globex", "client", "app", "production")
    caller = caller_for(production.org_id)
    service = ProjectService(tenants, FakeLogWriter())

    first = await service.list_projects(caller, cursor=None, limit=1)
    second = await service.list_projects(caller, cursor=first.next_cursor, limit=1)

    assert first.has_more is True
    assert second.has_more is False
    assert second.next_cursor is None
    environments = {item.environment for item in first.data + second.data}
    assert environments == {"production", "staging"}
    assert all(item.client == "northwind" for item in first.data + second.data)


async def test_bad_cursor_is_rejected() -> None:
    with pytest.raises(InvalidRequestError, match="cursor is not valid"):
        await ProjectService(FakeTenantStore(), FakeLogWriter()).list_projects(
            caller_for(new_id()), cursor="nope", limit=10
        )
