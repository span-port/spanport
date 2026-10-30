"""Creating projects and keys from the UI (by the caller's organization and ids)."""

import pytest
from fakes import FakeApiKeyStore, FakeLogWriter, FakeTenantStore, caller_for

from spanport_server.core.errors import ConflictError, InvalidRequestError, NotFoundError
from spanport_server.core.ids import new_id
from spanport_server.schemas.api_key import CreateKeyRequest, KeyType, Scope
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.tenant import CreateProjectRequest
from spanport_server.services.api_key_service import ApiKeyService
from spanport_server.services.project_service import ProjectService

pytestmark = pytest.mark.anyio


async def setup() -> tuple[ApiKeyService, ProjectService, FakeApiKeyStore, Caller]:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    keys = FakeApiKeyStore()
    projects = ProjectService(tenants, FakeLogWriter())
    return ApiKeyService(tenants, keys), projects, keys, caller_for(project.org_id)


def project_request(**overrides: str) -> CreateProjectRequest:
    fields = {"client": "globex", "project": "tracking-api", "environment": "staging"}
    return CreateProjectRequest.model_validate(fields | overrides)


async def test_creates_a_project_once_per_client_name_and_environment() -> None:
    _, projects, _, caller = await setup()

    created = await projects.create_project(caller, project_request())
    other_env = await projects.create_project(caller, project_request(environment="production"))

    assert (created.client, created.project, created.environment) == (
        "globex",
        "tracking-api",
        "staging",
    )
    assert other_env.id != created.id
    with pytest.raises(ConflictError):
        await projects.create_project(caller, project_request())


async def test_data_key_belongs_to_a_project_of_the_callers_org() -> None:
    keys, projects, store, caller = await setup()
    project = await projects.create_project(caller, project_request())

    created = await keys.create_key(
        caller,
        CreateKeyRequest(name=" tracking-prod ", key_type=KeyType.INGEST, project_id=project.id),
    )

    assert created.raw_key.startswith("sp_ingest_")
    assert created.record.name == "tracking-prod"
    assert created.record.project_id == project.id
    assert created.raw_key not in store.records_by_hash
    with pytest.raises(NotFoundError):
        await keys.create_key(
            caller, CreateKeyRequest(name="x", key_type=KeyType.INGEST, project_id=new_id())
        )
    with pytest.raises(InvalidRequestError, match="project_id"):
        await keys.create_key(caller, CreateKeyRequest(name="x", key_type=KeyType.INGEST))


async def test_admin_key_needs_scopes_and_no_project() -> None:
    keys, _, _, caller = await setup()

    created = await keys.create_key(
        caller,
        CreateKeyRequest(
            name="ci",
            key_type=KeyType.ADMIN,
            scopes=[Scope.LOGS_READ, Scope.LOGS_READ],
            expires_in_days=30,
        ),
    )

    assert created.raw_key.startswith("sp_admin_")
    assert created.record.scopes == (Scope.LOGS_READ,)
    assert created.record.expires_at is not None
    with pytest.raises(InvalidRequestError, match="scope"):
        await keys.create_key(caller, CreateKeyRequest(name="ci", key_type=KeyType.ADMIN))
    with pytest.raises(InvalidRequestError, match="whole organization"):
        await keys.create_key(
            caller,
            CreateKeyRequest(
                name="ci", key_type=KeyType.ADMIN, scopes=[Scope.LOGS_READ], project_id=new_id()
            ),
        )


async def test_lists_newest_first_in_pages_and_revokes_only_in_the_org() -> None:
    keys, _, _, caller = await setup()
    for name in ("first", "second", "third"):
        await keys.create_key(
            caller, CreateKeyRequest(name=name, key_type=KeyType.ADMIN, scopes=[Scope.LOGS_READ])
        )

    first_page = await keys.list_page(caller, None, 2)
    second_page = await keys.list_page(caller, first_page.next_cursor, 2)
    newest = first_page.data[0]

    assert [item.name for item in first_page.data] == ["third", "second"]
    assert [item.name for item in second_page.data] == ["first"]
    assert second_page.has_more is False
    assert newest.prefix == "sp_admin_"
    await keys.revoke_in_org(caller.org_id, newest.id, caller.label)
    with pytest.raises(NotFoundError):
        await keys.revoke_in_org(caller.org_id, newest.id, caller.label)
    with pytest.raises(NotFoundError):
        await keys.revoke_in_org(new_id(), first_page.data[1].id, "user=other-org")
