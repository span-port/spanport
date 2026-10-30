"""Tenant identifiers passed between layers, and the projects list response."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from spanport_server.core.constants import SLUG_PATTERN
from spanport_server.core.ids import UuidV7


@dataclass(frozen=True)
class ProjectRef:
    """The organization and project a key or log belongs to."""

    org_id: UuidV7
    project_id: UuidV7


class ProjectItem(BaseModel):
    """One project: a client's app in one environment."""

    id: UuidV7
    client: str
    project: str
    environment: str
    archived: bool = False


class CreateProjectRequest(BaseModel):
    """A new project. Each part is a slug: lower-case letters, digits and dashes."""

    model_config = ConfigDict(extra="forbid")

    client: str = Field(pattern=SLUG_PATTERN)
    project: str = Field(pattern=SLUG_PATTERN)
    environment: str = Field(pattern=SLUG_PATTERN)


class UpdateProjectRequest(BaseModel):
    """A project's new name and environment, as slugs. The client stays the same."""

    model_config = ConfigDict(extra="forbid")

    project: str = Field(pattern=SLUG_PATTERN)
    environment: str = Field(pattern=SLUG_PATTERN)


class ProjectListResponse(BaseModel):
    """A page of projects. Pass `next_cursor` back to get the next page."""

    data: list[ProjectItem]
    next_cursor: str | None
    has_more: bool
