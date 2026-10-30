"""Lists, creates, renames, archives and restores the projects of the caller's organization."""

import logging
from datetime import UTC, datetime
from typing import Protocol

from spanport_server.core.constants import (
    ACTIVE_PROJECT_DELETE_DETAIL,
    NO_PROJECT_DETAIL,
    PROJECT_EXISTS_DETAIL,
)
from spanport_server.core.errors import ConflictError, NotFoundError
from spanport_server.core.ids import UuidV7
from spanport_server.schemas.auth import Caller
from spanport_server.schemas.tenant import (
    CreateProjectRequest,
    ProjectItem,
    ProjectListResponse,
    UpdateProjectRequest,
)
from spanport_server.services.id_cursor import parse_id_cursor

logger = logging.getLogger(__name__)


class ProjectStore(Protocol):
    """Reads and creates projects."""

    async def list_projects(
        self,
        org_id: UuidV7,
        after_id: UuidV7 | None,
        limit: int,
        only_ids: frozenset[UuidV7] | None = None,
    ) -> list[ProjectItem]:
        """Up to `limit` projects of the organization after `after_id` (only `only_ids` when
        given), ordered by id.
        """
        ...

    async def create_project(
        self, org_id: UuidV7, client_slug: str, project_slug: str, environment: str
    ) -> ProjectItem | None:
        """The new project, or None when it already exists."""
        ...

    async def update_project(
        self, org_id: UuidV7, project_id: UuidV7, project_slug: str, environment: str
    ) -> ProjectItem | None:
        """The renamed project, or None when there is no such project; ConflictError on a clash."""
        ...

    async def set_archived(
        self, org_id: UuidV7, project_id: UuidV7, archived_at: datetime | None
    ) -> ProjectItem | None:
        """The archived (or restored) project, or None when there is no such project."""
        ...

    async def find_project(self, org_id: UuidV7, project_id: UuidV7) -> ProjectItem | None:
        """One project of this organization, archived or not, or None."""
        ...

    async def delete_project(self, org_id: UuidV7, project_id: UuidV7) -> bool:
        """Delete the project and its keys; False when there is no such project."""
        ...


class ProjectData(Protocol):
    """Removes a project's telemetry: its logs and spans."""

    async def delete_project_data(self, org_id: UuidV7, project_id: UuidV7) -> None:
        """Delete every log and span of the project; StorageUnavailableError if storage is down."""
        ...


class ProjectService:
    """Pages through, adds, changes and deletes an organization's projects."""

    def __init__(self, projects: ProjectStore, logs: ProjectData) -> None:
        """Create the service.

        Args:
            projects: Project storage (Postgres).
            logs: Telemetry storage (ClickHouse), for deleting a project's logs and spans.
        """
        self._projects = projects
        self._logs = logs

    async def list_projects(
        self, caller: Caller, cursor: str | None, limit: int
    ) -> ProjectListResponse:
        """One page of the caller's organization's projects (only the ones they may see).

        Args:
            caller: The signed-in person or admin key; it decides the organization.
            cursor: `next_cursor` from the previous page, or None.
            limit: Page size.

        Returns:
            The page and, when there are more, the cursor for the next one.

        Raises:
            InvalidRequestError: The cursor is not valid.
        """
        after_id = parse_id_cursor(cursor) if cursor else None
        rows = await self._projects.list_projects(
            caller.org_id, after_id, limit + 1, caller.project_ids
        )
        page = rows[:limit]
        has_more = len(rows) > limit
        logger.info(
            "projects listed %s org=%s rows=%d has_more=%s",
            caller.label,
            caller.org_id,
            len(page),
            has_more,
        )
        return ProjectListResponse(
            data=page, next_cursor=str(page[-1].id) if has_more else None, has_more=has_more
        )

    async def create_project(self, caller: Caller, request: CreateProjectRequest) -> ProjectItem:
        """Add a project (one client's app in one environment) to the caller's organization.

        The client is created too if the organization doesn't have it yet.

        Raises:
            ConflictError: The client already has this project in this environment.
        """
        project = await self._projects.create_project(
            caller.org_id, request.client, request.project, request.environment
        )
        if project is None:
            raise ConflictError(PROJECT_EXISTS_DETAIL)
        logger.info(
            "project created %s id=%s client=%s project=%s environment=%s",
            caller.label,
            project.id,
            project.client,
            project.project,
            project.environment,
        )
        return project

    async def update_project(
        self, caller: Caller, project_id: UuidV7, request: UpdateProjectRequest
    ) -> ProjectItem:
        """Rename a project or move it to another environment. Its keys and logs stay with it.

        Raises:
            NotFoundError: No such project in the caller's organization.
            ConflictError: The client already has a project with this name in this environment.
        """
        project = await self._projects.update_project(
            caller.org_id, project_id, request.project, request.environment
        )
        if project is None:
            raise NotFoundError(NO_PROJECT_DETAIL)
        logger.info(
            "project updated %s id=%s project=%s environment=%s",
            caller.label,
            project_id,
            project.project,
            project.environment,
        )
        return project

    async def set_archived(self, caller: Caller, project_id: UuidV7, archived: bool) -> ProjectItem:
        """Archive a project (its data keys stop working, its logs stay) or restore it.

        Raises:
            NotFoundError: No such project in the caller's organization.
        """
        archived_at = datetime.now(UTC) if archived else None
        project = await self._projects.set_archived(caller.org_id, project_id, archived_at)
        if project is None:
            raise NotFoundError(NO_PROJECT_DETAIL)
        logger.info(
            "project %s %s id=%s", "archived" if archived else "restored", caller.label, project_id
        )
        return project

    async def delete_project(self, caller: Caller, project_id: UuidV7) -> None:
        """Delete an archived project for good: its logs, then its keys and the project itself.

        Logs go first, so if ClickHouse is down nothing is lost and the delete can be retried.

        Raises:
            NotFoundError: No such project in the caller's organization.
            ConflictError: The project isn't archived yet.
            StorageUnavailableError: ClickHouse is down.
        """
        project = await self._projects.find_project(caller.org_id, project_id)
        if project is None:
            raise NotFoundError(NO_PROJECT_DETAIL)
        if not project.archived:
            raise ConflictError(ACTIVE_PROJECT_DELETE_DETAIL)
        await self._logs.delete_project_data(caller.org_id, project_id)
        if not await self._projects.delete_project(caller.org_id, project_id):
            raise NotFoundError(NO_PROJECT_DETAIL)
        logger.info(
            "project deleted %s id=%s client=%s project=%s environment=%s",
            caller.label,
            project_id,
            project.client,
            project.project,
            project.environment,
        )
