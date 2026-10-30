"""The organization's people: list them, change roles, remove them, and invite new ones.

Rules: only owners grant or change the owner role, nobody changes or removes themselves, and an
organization always keeps an active owner. An invite gives nobody access until it is accepted.
"""

import logging
import secrets
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from spanport_server.core.constants import (
    ACCOUNT_EXISTS_DETAIL,
    FULL_ACCESS_ROLE_DETAIL,
    FULL_ACCESS_ROLES,
    INVITE_LIFETIME,
    LAST_OWNER_DETAIL,
    NO_INVITE_DETAIL,
    NO_USER_DETAIL,
    NOT_SIGNED_IN_DETAIL,
    OWNER_ONLY_DETAIL,
    PICK_PROJECTS_DETAIL,
    SELF_CHANGE_DETAIL,
    SESSION_TOKEN_BYTES,
    UNKNOWN_PROJECTS_DETAIL,
)
from spanport_server.core.errors import (
    ConflictError,
    InvalidRequestError,
    NotAllowedError,
    NotFoundError,
    NotSignedInError,
)
from spanport_server.core.ids import UuidV7
from spanport_server.core.key_hashing import hash_api_key
from spanport_server.schemas.auth import Caller, Role
from spanport_server.schemas.team import (
    AccountOwner,
    CreatedInviteResponse,
    InviteItem,
    InviteListResponse,
    InviteRequest,
    ProjectAccess,
    TeamChange,
    UserItem,
    UserListResponse,
)
from spanport_server.services.auth_service import normalize_email, utc_now
from spanport_server.services.id_cursor import parse_id_cursor

logger = logging.getLogger(__name__)


class TeamStore(Protocol):
    """Users and invites of an organization."""

    async def list_users(
        self, org_id: UuidV7, after_id: UuidV7 | None, limit: int
    ) -> list[UserItem]: ...

    async def find_user(self, org_id: UuidV7, user_id: UuidV7) -> UserItem | None: ...

    async def change_role(self, org_id: UuidV7, user_id: UuidV7, role: Role) -> TeamChange: ...

    async def disable_user(self, org_id: UuidV7, user_id: UuidV7, now: datetime) -> TeamChange: ...

    async def find_account(self, email: str) -> AccountOwner | None: ...

    async def set_project_access(
        self, org_id: UuidV7, user_id: UuidV7, all_projects: bool, project_ids: list[UuidV7]
    ) -> bool: ...

    async def count_org_projects(self, org_id: UuidV7, project_ids: list[UuidV7]) -> int: ...

    async def insert_invite(
        self,
        org_id: UuidV7,
        email: str,
        role: Role,
        access: ProjectAccess,
        token_hash: str,
        invited_by: UuidV7,
        now: datetime,
        expires_at: datetime,
    ) -> InviteItem: ...

    async def list_open_invites(
        self, org_id: UuidV7, now: datetime, after_id: UuidV7 | None, limit: int
    ) -> list[InviteItem]: ...

    async def cancel_invite(self, org_id: UuidV7, invite_id: UuidV7, now: datetime) -> bool: ...


class SessionRevoker(Protocol):
    """Signs a user out everywhere."""

    async def revoke_for_user(self, user_id: UuidV7, now: datetime) -> int: ...


class TeamService:
    """Owners and admins manage the organization's people (callers come from require_manager)."""

    def __init__(
        self, team: TeamStore, sessions: SessionRevoker, now: Callable[[], datetime] = utc_now
    ) -> None:
        """Create the service.

        Args:
            team: Users and invites (Postgres).
            sessions: Session storage, to sign removed users out.
            now: The clock; tests pass a fixed one.
        """
        self._team = team
        self._sessions = sessions
        self._now = now

    async def list_users(self, caller: Caller, cursor: str | None, limit: int) -> UserListResponse:
        """One page of the organization's active users.

        Raises:
            InvalidRequestError: The cursor is not valid.
        """
        after_id = parse_id_cursor(cursor) if cursor else None
        rows = await self._team.list_users(caller.org_id, after_id, limit + 1)
        page = rows[:limit]
        has_more = len(rows) > limit
        logger.info("users listed %s rows=%d", caller.label, len(page))
        return UserListResponse(
            data=page, next_cursor=str(page[-1].id) if has_more else None, has_more=has_more
        )

    async def change_role(self, caller: Caller, user_id: UuidV7, role: Role) -> UserItem:
        """Give a user a new role.

        Raises:
            NotFoundError: No such active user in the caller's organization.
            NotAllowedError: Changing oneself, or an admin touching the owner role.
            ConflictError: It would leave the organization without an owner.
        """
        target = await self._changeable(caller, user_id)
        if Role.OWNER in (role, target.role) and caller.role is not Role.OWNER:
            raise NotAllowedError(OWNER_ONLY_DETAIL)
        self._raise_for(await self._team.change_role(caller.org_id, user_id, role))
        if role in FULL_ACCESS_ROLES:
            # Owners and admins see every project; a later demotion keeps that until changed.
            await self._team.set_project_access(caller.org_id, user_id, True, [])
        logger.info(
            "user role changed %s user=%s from=%s to=%s", caller.label, user_id, target.role, role
        )
        return await self._changeable(caller, user_id)

    async def set_project_access(
        self, caller: Caller, user_id: UuidV7, access: ProjectAccess
    ) -> UserItem:
        """Give a member or viewer all projects, or only some.

        Raises:
            NotFoundError, NotAllowedError: As for change_role.
            InvalidRequestError: The user is an owner or admin (they always see every project),
                no project was picked, or a project isn't in the organization.
        """
        target = await self._changeable(caller, user_id)
        if target.role in FULL_ACCESS_ROLES:
            raise InvalidRequestError(FULL_ACCESS_ROLE_DETAIL)
        await self._check_access(caller, access)
        await self._team.set_project_access(
            caller.org_id, user_id, access.all_projects, access.project_ids
        )
        logger.info(
            "user projects changed %s user=%s all_projects=%s projects=%d",
            caller.label,
            user_id,
            access.all_projects,
            len(access.project_ids),
        )
        return await self._changeable(caller, user_id)

    async def remove_user(self, caller: Caller, user_id: UuidV7) -> None:
        """Remove a user: they can't sign in again and are signed out everywhere now.

        Raises:
            NotFoundError, NotAllowedError, ConflictError: As for change_role.
        """
        target = await self._changeable(caller, user_id)
        if target.role is Role.OWNER and caller.role is not Role.OWNER:
            raise NotAllowedError(OWNER_ONLY_DETAIL)
        now = self._now()
        self._raise_for(await self._team.disable_user(caller.org_id, user_id, now))
        revoked = await self._sessions.revoke_for_user(user_id, now)
        logger.info("user removed %s user=%s sessions_revoked=%d", caller.label, user_id, revoked)

    async def create_invite(self, caller: Caller, request: InviteRequest) -> CreatedInviteResponse:
        """Invite someone. Nothing is granted until they open the link and accept it.

        A new invite for the same email replaces the earlier one.

        Returns:
            The invite and its token, shown this once (the UI builds the link from it).

        Raises:
            NotAllowedError: An admin inviting an owner.
            ConflictError: The email already has an account.
            InvalidRequestError: No project picked, or a project isn't in the organization.
        """
        if request.role is Role.OWNER and caller.role is not Role.OWNER:
            raise NotAllowedError(OWNER_ONLY_DETAIL)
        # Owners and admins always see everything, whatever the form said.
        access = (
            ProjectAccess()
            if request.role in FULL_ACCESS_ROLES
            else ProjectAccess(all_projects=request.all_projects, project_ids=request.project_ids)
        )
        await self._check_access(caller, access)
        email = normalize_email(request.email)
        account = await self._team.find_account(email)
        # A removed user of this organization may come back; any other account can't.
        if account is not None and not (account.disabled and account.org_id == caller.org_id):
            raise ConflictError(ACCOUNT_EXISTS_DETAIL)
        token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        now = self._now()
        invite = await self._team.insert_invite(
            caller.org_id,
            email,
            request.role,
            access,
            hash_api_key(token),
            self._acting_user(caller),
            now,
            now + INVITE_LIFETIME,
        )
        logger.info("invite created %s invite=%s role=%s", caller.label, invite.id, invite.role)
        return CreatedInviteResponse(token=token, item=invite)

    async def list_invites(
        self, caller: Caller, cursor: str | None, limit: int
    ) -> InviteListResponse:
        """One page of invites that can still be accepted.

        Raises:
            InvalidRequestError: The cursor is not valid.
        """
        after_id = parse_id_cursor(cursor) if cursor else None
        rows = await self._team.list_open_invites(caller.org_id, self._now(), after_id, limit + 1)
        page = rows[:limit]
        has_more = len(rows) > limit
        logger.info("invites listed %s rows=%d", caller.label, len(page))
        return InviteListResponse(
            data=page, next_cursor=str(page[-1].id) if has_more else None, has_more=has_more
        )

    async def cancel_invite(self, caller: Caller, invite_id: UuidV7) -> None:
        """Cancel a pending invite; its link stops working.

        Raises:
            NotFoundError: No pending invite with this id in the caller's organization.
        """
        if not await self._team.cancel_invite(caller.org_id, invite_id, self._now()):
            raise NotFoundError(NO_INVITE_DETAIL)
        logger.info("invite cancelled %s invite=%s", caller.label, invite_id)

    async def _changeable(self, caller: Caller, user_id: UuidV7) -> UserItem:
        """The target user, if the caller may change them at all."""
        if user_id == caller.user_id:
            raise NotAllowedError(SELF_CHANGE_DETAIL)
        target = await self._team.find_user(caller.org_id, user_id)
        if target is None:
            raise NotFoundError(NO_USER_DETAIL)
        return target

    async def _check_access(self, caller: Caller, access: ProjectAccess) -> None:
        """Limited access needs at least one project, all of them in the caller's org."""
        if access.all_projects:
            return
        unique_ids = list(set(access.project_ids))
        if not unique_ids:
            raise InvalidRequestError(PICK_PROJECTS_DETAIL)
        if await self._team.count_org_projects(caller.org_id, unique_ids) != len(unique_ids):
            raise InvalidRequestError(UNKNOWN_PROJECTS_DETAIL)

    def _acting_user(self, caller: Caller) -> UuidV7:
        """Who is acting; people management needs a signed-in person, never a key."""
        if caller.user_id is None:
            raise NotSignedInError(NOT_SIGNED_IN_DETAIL)
        return caller.user_id

    def _raise_for(self, outcome: TeamChange) -> None:
        """Turn the store's answer into the matching error, if any."""
        match outcome:
            case TeamChange.NOT_FOUND:
                raise NotFoundError(NO_USER_DETAIL)
            case TeamChange.LAST_OWNER:
                raise ConflictError(LAST_OWNER_DETAIL)
            case TeamChange.DONE:
                return
