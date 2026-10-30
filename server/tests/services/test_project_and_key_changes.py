"""Renaming, archiving and restoring projects; renaming keys."""

import pytest
from fakes import FakeApiKeyStore, FakeLogWriter, FakeTenantStore, caller_for

from spanport_server.core.errors import (
    ConflictError,
    InvalidRequestError,
    NotFoundError,
    StorageUnavailableError,
)
from spanport_server.core.ids import new_id
from spanport_server.schemas.api_key import CreateKeyRequest, KeyType
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.tenant import ProjectRef, UpdateProjectRequest
from spanport_server.services.api_key_service import ApiKeyService
from spanport_server.services.project_service import ProjectService

pytestmark = pytest.mark.anyio


async def setup() -> tuple[ProjectService, ApiKeyService, ProjectRef, Caller]:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    await tenants.get_or_create_project("acme", "northwind", "hr-portal", "staging")
    services = ProjectService(tenants, FakeLogWriter()), ApiKeyService(tenants, FakeApiKeyStore())
    return *services, project, caller_for(project.org_id)


async def test_only_archived_projects_are_deleted_logs_first() -> None:
    tenants = FakeTenantStore()
    project = await tenants.get_or_create_project("acme", "northwind", "hr-portal", "production")
    logs, down = FakeLogWriter(), FakeLogWriter(storage_down=True)
    caller = caller_for(project.org_id)

    with pytest.raises(ConflictError, match="Archive"):
        await ProjectService(tenants, logs).delete_project(caller, project.project_id)
    await ProjectService(tenants, logs).set_archived(caller, project.project_id, archived=True)
    with pytest.raises(StorageUnavailableError):
        await ProjectService(tenants, down).delete_project(caller, project.project_id)
    assert await tenants.find_project(project.org_id, project.project_id) is not None
    await ProjectService(tenants, logs).delete_project(caller, project.project_id)

    assert logs.deleted_projects == [(project.org_id, project.project_id)]
    assert await tenants.find_project(project.org_id, project.project_id) is None
    with pytest.raises(NotFoundError):
        await ProjectService(tenants, logs).delete_project(caller, project.project_id)


async def test_only_revoked_keys_are_deleted() -> None:
    _, keys, project, caller = await setup()
    created = await keys.create_key(
        caller, CreateKeyRequest(name="k", key_type=KeyType.INGEST, project_id=project.project_id)
    )

    with pytest.raises(NotFoundError, match="Revoke"):
        await keys.delete_key(caller, created.record.id)
    await keys.revoke_in_org(caller.org_id, created.record.id, caller.label)
    await keys.delete_key(caller, created.record.id)

    assert (await keys.list_page(caller, None, 10)).data == []


async def test_renames_a_project_but_refuses_a_clash() -> None:
    projects, _, project, caller = await setup()

    renamed = await projects.update_project(
        caller, project.project_id, UpdateProjectRequest(project="hr-api", environment="production")
    )

    assert (renamed.client, renamed.project, renamed.environment) == (
        "northwind",
        "hr-api",
        "production",
    )
    with pytest.raises(ConflictError):
        await projects.update_project(
            caller,
            project.project_id,
            UpdateProjectRequest(project="hr-portal", environment="staging"),
        )
    with pytest.raises(NotFoundError):
        await projects.update_project(
            caller_for(new_id()),
            project.project_id,
            UpdateProjectRequest(project="x", environment="production"),
        )


async def test_archived_projects_get_no_new_keys_until_restored() -> None:
    projects, keys, project, caller = await setup()
    data_key = CreateKeyRequest(name="k", key_type=KeyType.INGEST, project_id=project.project_id)

    archived = await projects.set_archived(caller, project.project_id, archived=True)
    with pytest.raises(InvalidRequestError, match="archived"):
        await keys.create_key(caller, data_key)
    restored = await projects.set_archived(caller, project.project_id, archived=False)

    assert archived.archived is True
    assert restored.archived is False
    assert (await keys.create_key(caller, data_key)).record.project_id == project.project_id


async def test_renames_a_key_of_the_org_only() -> None:
    _, keys, project, caller = await setup()
    created = await keys.create_key(
        caller, CreateKeyRequest(name="old", key_type=KeyType.INGEST, project_id=project.project_id)
    )

    renamed = await keys.rename_key(caller, created.record.id, "  new name ")

    assert renamed.name == "new name"
    with pytest.raises(NotFoundError):
        await keys.rename_key(caller_for(new_id()), created.record.id, "x")
