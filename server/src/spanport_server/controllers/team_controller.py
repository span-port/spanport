"""Users and invites: owners and admins see the organization's people, change roles, remove
people and invite new ones. Accepting an invite is in auth_controller (no sign-in needed).
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request

from spanport_server.core.constants import (
    DEFAULT_USERS_LIMIT,
    INVITE_PATH,
    INVITES_PATH,
    MAX_AUTH_BODY_BYTES,
    MAX_USERS_LIMIT,
    USER_PATH,
    USER_PROJECTS_PATH,
    USERS_PATH,
)
from spanport_server.core.ids import UuidV7
from spanport_server.core.request_body import parse_json_body
from spanport_server.dependencies import get_team_service, require_manager
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.team import (
    ChangeRoleRequest,
    CreatedInviteResponse,
    InviteListResponse,
    InviteRequest,
    ProjectAccess,
    UserItem,
    UserListResponse,
)
from spanport_server.services.team_service import TeamService

router = APIRouter()

Limit = Annotated[int, Query(ge=1, le=MAX_USERS_LIMIT)]


@router.get(USERS_PATH)
async def list_users(
    caller: Annotated[Caller, Depends(require_manager)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
    limit: Limit = DEFAULT_USERS_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
) -> UserListResponse:
    """One page of the organization's active users.

    Raises:
        NotSignedInError (401), NotAllowedError (403), InvalidRequestError: cursor (400).
    """
    return await team_service.list_users(caller, cursor, limit)


@router.patch(USER_PATH)
async def change_role(
    user_id: UuidV7,
    request: Request,
    caller: Annotated[Caller, Depends(require_manager)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
    content_type: Annotated[str, Header()] = "",
) -> UserItem:
    """Give a user a new role.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError (404),
        ConflictError: the organization would have no owner (409).
    """
    body = await parse_json_body(request, content_type, ChangeRoleRequest, MAX_AUTH_BODY_BYTES)
    return await team_service.change_role(caller, user_id, body.role)


@router.put(USER_PROJECTS_PATH)
async def set_project_access(
    user_id: UuidV7,
    request: Request,
    caller: Annotated[Caller, Depends(require_manager)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
    content_type: Annotated[str, Header()] = "",
) -> UserItem:
    """Give a member or viewer all projects, or only `project_ids`.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError (404),
        InvalidRequestError: an owner or admin, no project picked, or an unknown project (400).
    """
    body = await parse_json_body(request, content_type, ProjectAccess, MAX_AUTH_BODY_BYTES)
    return await team_service.set_project_access(caller, user_id, body)


@router.delete(USER_PATH, status_code=HTTPStatus.NO_CONTENT)
async def remove_user(
    user_id: UuidV7,
    caller: Annotated[Caller, Depends(require_manager)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
) -> None:
    """Remove a user; they are signed out everywhere and can't sign in again.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError (404),
        ConflictError: they are the last owner (409).
    """
    await team_service.remove_user(caller, user_id)


@router.get(INVITES_PATH)
async def list_invites(
    caller: Annotated[Caller, Depends(require_manager)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
    limit: Limit = DEFAULT_USERS_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
) -> InviteListResponse:
    """One page of invites that are waiting to be accepted.

    Raises:
        NotSignedInError (401), NotAllowedError (403), InvalidRequestError: cursor (400).
    """
    return await team_service.list_invites(caller, cursor, limit)


@router.post(INVITES_PATH, status_code=HTTPStatus.CREATED)
async def create_invite(
    request: Request,
    caller: Annotated[Caller, Depends(require_manager)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
    content_type: Annotated[str, Header()] = "",
) -> CreatedInviteResponse:
    """Invite someone by email with a role; returns the token for the link, once.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403),
        InvalidRequestError: bad email or role (400), ConflictError: email has an account (409).
    """
    body = await parse_json_body(request, content_type, InviteRequest, MAX_AUTH_BODY_BYTES)
    return await team_service.create_invite(caller, body)


@router.delete(INVITE_PATH, status_code=HTTPStatus.NO_CONTENT)
async def cancel_invite(
    invite_id: UuidV7,
    caller: Annotated[Caller, Depends(require_manager)],
    team_service: Annotated[TeamService, Depends(get_team_service)],
) -> None:
    """Cancel a pending invite; its link stops working.

    Raises:
        NotSignedInError (401), NotAllowedError / CsrfError (403), NotFoundError (404).
    """
    await team_service.cancel_invite(caller, invite_id)
