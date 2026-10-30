"""The people in an organization and invitations to join it."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from spanport_server.core.constants import (
    EMAIL_PATTERN,
    MAX_EMAIL_LENGTH,
    MAX_NAME_LENGTH,
    MAX_PASSWORD_LENGTH,
    MAX_PROJECTS_LIMIT,
)
from spanport_server.core.ids import UuidV7
from spanport_server.schemas.auth import Role


class ProjectAccess(BaseModel):
    """Which projects a member or viewer sees: all, or only `project_ids`."""

    model_config = ConfigDict(extra="forbid")

    all_projects: bool = True
    project_ids: list[UuidV7] = Field(default_factory=list, max_length=MAX_PROJECTS_LIMIT)


class UserItem(BaseModel):
    """A person in the organization, as the Users page shows them."""

    id: UuidV7
    name: str
    email: str
    role: Role
    created_at: datetime
    all_projects: bool
    project_ids: list[UuidV7]


class UserListResponse(BaseModel):
    """A page of users. Pass `next_cursor` back to get the next page."""

    data: list[UserItem]
    next_cursor: str | None
    has_more: bool


class ChangeRoleRequest(BaseModel):
    """A user's new role."""

    model_config = ConfigDict(extra="forbid")

    role: Role


class InviteRequest(ProjectAccess):
    """Who to invite, with which role and (for members and viewers) which projects."""

    email: str = Field(max_length=MAX_EMAIL_LENGTH, pattern=EMAIL_PATTERN)
    role: Role


class InviteItem(BaseModel):
    """A pending invite. `invited_by` is the inviter's name, or None if they were removed."""

    id: UuidV7
    email: str
    role: Role
    invited_by: str | None
    created_at: datetime
    expires_at: datetime
    all_projects: bool
    project_ids: list[UuidV7]


class InviteListResponse(BaseModel):
    """A page of pending invites. Pass `next_cursor` back to get the next page."""

    data: list[InviteItem]
    next_cursor: str | None
    has_more: bool


class CreatedInviteResponse(BaseModel):
    """A new invite. `token` goes into the invite link and is shown only this once."""

    token: str
    item: InviteItem


class InviteTokenRequest(BaseModel):
    """The token from an invite link."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)


class InviteDetails(BaseModel):
    """What an invite is for, shown before the person accepts it."""

    email: str
    role: Role
    organization: str
    invited_by: str | None


class AcceptInviteRequest(InviteTokenRequest):
    """Accept an invite: the new account's name and password."""

    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class TeamChange(StrEnum):
    """What happened to a role change or removal."""

    DONE = "done"
    NOT_FOUND = "not_found"
    LAST_OWNER = "last_owner"


@dataclass(frozen=True)
class AccountOwner:
    """The organization an email's account belongs to, and whether it was removed."""

    org_id: UuidV7
    disabled: bool
