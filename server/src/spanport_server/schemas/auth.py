"""Sign-in requests and responses, and who is calling an endpoint."""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from spanport_server.core.constants import (
    EMAIL_PATTERN,
    MAX_EMAIL_LENGTH,
    MAX_NAME_LENGTH,
    MAX_ORG_NAME_LENGTH,
    MAX_PASSWORD_LENGTH,
)
from spanport_server.core.ids import UuidV7


class Role(StrEnum):
    """What a person may do. Only owners and admins manage users, providers and admin keys."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


@dataclass(frozen=True)
class UserRecord:
    """A person who can sign in, with their organization."""

    id: UuidV7
    org_id: UuidV7
    org_slug: str
    email: str
    name: str
    role: Role
    # The projects a member or viewer may see; None means every project of the org.
    project_ids: frozenset[UuidV7] | None = None


@dataclass(frozen=True)
class SignedIn:
    """A new session. The raw tokens go into cookies once and are stored only as hashes."""

    user: UserRecord
    session_token: str
    csrf_token: str


@dataclass(frozen=True)
class Caller:
    """Who is calling a data endpoint: a signed-in person or an admin key.

    Every query is scoped to `org_id`. `label` names the caller in log lines without secrets,
    e.g. "user=0193..." or "key=...a1b2". `user_id` is set for a signed-in person, so actions
    such as acknowledging an alert can record who did them, and `role` decides what they may
    change; both are None for an admin key. `project_ids` limits a member or viewer to some
    projects; None (owners, admins, admin keys, "all projects" users) means every project.
    """

    org_id: UuidV7
    label: str
    user_id: UuidV7 | None = None
    role: Role | None = None
    project_ids: frozenset[UuidV7] | None = None

    def can_see(self, project_id: UuidV7) -> bool:
        """Whether this caller may see the project (its logs, alerts and rules)."""
        return self.project_ids is None or project_id in self.project_ids


class SetupRequest(BaseModel):
    """The first-time setup form: creates the owner and their organization."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    email: str = Field(max_length=MAX_EMAIL_LENGTH, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    organization: str = Field(min_length=1, max_length=MAX_ORG_NAME_LENGTH)


class LoginRequest(BaseModel):
    """Email and password."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=MAX_EMAIL_LENGTH)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class CurrentUserResponse(BaseModel):
    """The signed-in person, as the UI shows them."""

    id: UuidV7
    name: str
    email: str
    role: Role
    organization: str
