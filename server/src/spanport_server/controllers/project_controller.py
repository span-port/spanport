"""Projects of the caller's organization: list them (switcher); owners and admins also add,
rename, archive and restore them.
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request

from spanport_server.core.constants import (
    ARCHIVE_PROJECT_PATH,
    DEFAULT_PROJECTS_LIMIT,
    MAX_AUTH_BODY_BYTES,
    MAX_PROJECTS_LIMIT,
    PROJECT_PATH,
    PROJECTS_PATH,
    RESTORE_PROJECT_PATH,
)
from spanport_server.core.ids import UuidV7
from spanport_server.core.request_body import parse_json_body
from spanport_server.dependencies import (
    get_project_service,
    require_manager,
    require_projects_reader,
)
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.tenant import (
    CreateProjectRequest,
    ProjectItem,
    ProjectListResponse,
    UpdateProjectRequest,
)
from spanport_server.services.project_service import ProjectService

router = APIRouter()


@router.get(PROJECTS_PATH)
async def list_projects(
    caller: Annotated[Caller, Depends(require_projects_reader)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    limit: Annotated[int, Query(ge=1, le=MAX_PROJECTS_LIMIT)] = DEFAULT_PROJECTS_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
) -> ProjectListResponse:
    """One page of projects, each with its client and environment.

    Returns:
        `data`, `next_cursor` and `has_more`.

    Raises:
        InvalidKeyError / NotSignedInError: No valid admin key or session (401).
        MissingScopeError: The admin key lacks projects:read (403).
        InvalidRequestError: Bad limit or cursor (400).
    """
    return await project_service.list_projects(caller, cursor, limit)


@router.post(PROJECTS_PATH, status_code=HTTPStatus.CREATED)
async def create_project(
    request: Request,
    caller: Annotated[Caller, Depends(require_manager)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    content_type: Annotated[str, Header()] = "",
) -> ProjectItem:
    """Add a project: a client's app in one environment. The client is created if new.

    Returns:
        The new project (201).

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), InvalidRequestError: a part
        is not a slug (400), ConflictError: the project already exists (409).
    """
    body = await parse_json_body(request, content_type, CreateProjectRequest, MAX_AUTH_BODY_BYTES)
    return await project_service.create_project(caller, body)


@router.patch(PROJECT_PATH)
async def update_project(
    project_id: UuidV7,
    request: Request,
    caller: Annotated[Caller, Depends(require_manager)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
    content_type: Annotated[str, Header()] = "",
) -> ProjectItem:
    """Rename a project or change its environment; its keys and logs stay with it.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError (404),
        ConflictError: the client already has that project in that environment (409).
    """
    body = await parse_json_body(request, content_type, UpdateProjectRequest, MAX_AUTH_BODY_BYTES)
    return await project_service.update_project(caller, project_id, body)


@router.delete(PROJECT_PATH, status_code=HTTPStatus.NO_CONTENT)
async def delete_project(
    project_id: UuidV7,
    caller: Annotated[Caller, Depends(require_manager)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> None:
    """Delete an archived project for good, with its keys and all its logs.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError (404),
        ConflictError: the project isn't archived (409), StorageUnavailableError (503).
    """
    await project_service.delete_project(caller, project_id)


@router.post(ARCHIVE_PROJECT_PATH)
async def archive_project(
    project_id: UuidV7,
    caller: Annotated[Caller, Depends(require_manager)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectItem:
    """Archive a project: its data keys stop working now, its logs stay until they expire.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError (404).
    """
    return await project_service.set_archived(caller, project_id, archived=True)


@router.post(RESTORE_PROJECT_PATH)
async def restore_project(
    project_id: UuidV7,
    caller: Annotated[Caller, Depends(require_manager)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectItem:
    """Restore an archived project; its unrevoked data keys work again.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError (404).
    """
    return await project_service.set_archived(caller, project_id, archived=False)
