"""Reads and writes organizations, clients and projects."""

from datetime import datetime
from typing import Any

from sqlalchemy import Select, delete, select, update
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spanport_server.core.constants import PROJECT_EXISTS_DETAIL
from spanport_server.core.errors import ConflictError
from spanport_server.core.ids import UuidV7, new_id
from spanport_server.models import ApiKey, Client, Organization, Project
from spanport_server.schemas.tenant import ProjectItem, ProjectRef

# A project with its client's slug; every project read goes through this.
PROJECT_ITEM = select(
    Project.id, Client.slug, Project.slug, Project.environment, Project.archived_at
).join(Client, Client.id == Project.client_id)


async def insert_or_get_id(
    session: AsyncSession, insert_row: Insert, find_id: Select[UuidV7]
) -> UuidV7:
    """Insert a row unless it already exists, then return its id. Safe if run twice at once."""
    await session.execute(insert_row.on_conflict_do_nothing())
    return (await session.execute(find_id)).scalar_one()


class TenantRepository:
    """organizations, clients and projects table access."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Create the repository.

        Args:
            sessionmaker: Opens Postgres sessions.
        """
        self._sessionmaker = sessionmaker

    async def get_or_create_project(
        self, org_slug: str, client_slug: str, project_slug: str, environment: str
    ) -> ProjectRef:
        """Find a project by its slugs, creating the organization, client and project if missing.

        Args:
            org_slug: Organization slug.
            client_slug: Client slug within the organization.
            project_slug: Project slug within the client.
            environment: Environment name, e.g. "production".

        Returns:
            The organization and project ids.
        """
        async with self._sessionmaker.begin() as session:
            org_id = await insert_or_get_id(
                session,
                insert(Organization).values(new_row(slug=org_slug)),
                select(Organization.id).where(Organization.slug == org_slug),
            )
            client_id = await insert_or_get_id(
                session,
                insert(Client).values(new_row(org_id=org_id, slug=client_slug)),
                select(Client.id).where(Client.org_id == org_id, Client.slug == client_slug),
            )
            project_id = await insert_or_get_id(
                session,
                insert(Project).values(
                    new_row(
                        org_id=org_id,
                        client_id=client_id,
                        slug=project_slug,
                        environment=environment,
                    )
                ),
                select(Project.id).where(
                    Project.org_id == org_id,
                    Project.client_id == client_id,
                    Project.slug == project_slug,
                    Project.environment == environment,
                ),
            )
        return ProjectRef(org_id=org_id, project_id=project_id)

    async def create_project(
        self, org_id: UuidV7, client_slug: str, project_slug: str, environment: str
    ) -> ProjectItem | None:
        """Create a project in an organization, creating its client if missing.

        Args:
            org_id: The organization.
            client_slug: Client slug; created if the organization has no such client yet.
            project_slug: Project slug within the client.
            environment: Environment name, e.g. "production".

        Returns:
            The new project, or None when the client already has it in this environment.
        """
        async with self._sessionmaker.begin() as session:
            client_id = await insert_or_get_id(
                session,
                insert(Client).values(new_row(org_id=org_id, slug=client_slug)),
                select(Client.id).where(Client.org_id == org_id, Client.slug == client_slug),
            )
            project_id = await session.scalar(
                insert(Project)
                .values(
                    new_row(
                        org_id=org_id,
                        client_id=client_id,
                        slug=project_slug,
                        environment=environment,
                    )
                )
                .on_conflict_do_nothing()
                .returning(Project.id)
            )
        if project_id is None:
            return None
        return ProjectItem(
            id=project_id, client=client_slug, project=project_slug, environment=environment
        )

    async def find_org_id(self, org_slug: str) -> UuidV7 | None:
        """Return the id of the organization with this slug, or None."""
        async with self._sessionmaker() as session:
            return await session.scalar(
                select(Organization.id).where(Organization.slug == org_slug)
            )

    async def list_projects(
        self,
        org_id: UuidV7,
        after_id: UuidV7 | None,
        limit: int,
        only_ids: frozenset[UuidV7] | None = None,
    ) -> list[ProjectItem]:
        """One page of an organization's projects with their client, ordered by id.

        Args:
            org_id: The organization.
            after_id: Continue after this project id; None for the first page.
            limit: Most rows to return.
            only_ids: Only these projects (a member limited to some); None for all.

        Returns:
            Up to `limit` projects.
        """
        query = PROJECT_ITEM.where(Project.org_id == org_id).order_by(Project.id).limit(limit)
        if after_id is not None:
            query = query.where(Project.id > after_id)
        if only_ids is not None:
            query = query.where(Project.id.in_(list(only_ids)))
        async with self._sessionmaker() as session:
            return [to_project_item(*row) for row in await session.execute(query)]

    async def find_project(self, org_id: UuidV7, project_id: UuidV7) -> ProjectItem | None:
        """One project of this organization, archived or not, or None."""
        async with self._sessionmaker() as session:
            row = (
                await session.execute(
                    PROJECT_ITEM.where(Project.org_id == org_id, Project.id == project_id)
                )
            ).first()
        return None if row is None else to_project_item(*row)

    async def update_project(
        self, org_id: UuidV7, project_id: UuidV7, project_slug: str, environment: str
    ) -> ProjectItem | None:
        """Rename a project or move it to another environment; its client stays the same.

        Returns:
            The updated project, or None when the organization has no such project.

        Raises:
            ConflictError: The client already has a project with this name in this environment.
        """
        try:
            async with self._sessionmaker.begin() as session:
                updated = await session.scalar(
                    update(Project)
                    .where(Project.org_id == org_id, Project.id == project_id)
                    .values(slug=project_slug, environment=environment)
                    .returning(Project.id)
                )
        except IntegrityError as error:
            raise ConflictError(PROJECT_EXISTS_DETAIL) from error
        return None if updated is None else await self.find_project(org_id, project_id)

    async def set_archived(
        self, org_id: UuidV7, project_id: UuidV7, archived_at: datetime | None
    ) -> ProjectItem | None:
        """Archive a project (a time) or restore it (None).

        Returns:
            The project, or None when the organization has no such project.
        """
        async with self._sessionmaker.begin() as session:
            updated = await session.scalar(
                update(Project)
                .where(Project.org_id == org_id, Project.id == project_id)
                .values(archived_at=archived_at)
                .returning(Project.id)
            )
        return None if updated is None else await self.find_project(org_id, project_id)

    async def delete_project(self, org_id: UuidV7, project_id: UuidV7) -> bool:
        """Delete a project and its API keys in one transaction.

        Returns:
            False when the organization has no such project.
        """
        async with self._sessionmaker.begin() as session:
            await session.execute(
                delete(ApiKey).where(ApiKey.org_id == org_id, ApiKey.project_id == project_id)
            )
            deleted = await session.scalar(
                delete(Project)
                .where(Project.org_id == org_id, Project.id == project_id)
                .returning(Project.id)
            )
        return deleted is not None

    async def project_exists(self, org_id: UuidV7, project_id: UuidV7) -> bool:
        """Whether this project exists and belongs to this organization."""
        async with self._sessionmaker() as session:
            found = await session.scalar(
                select(Project.id).where(Project.org_id == org_id, Project.id == project_id)
            )
        return found is not None


def to_project_item(
    project_id: UuidV7,
    client: str,
    project: str,
    environment: str,
    archived_at: datetime | None,
) -> ProjectItem:
    """A row of PROJECT_ITEM as the item services and the API use."""
    return ProjectItem(
        id=project_id,
        client=client,
        project=project,
        environment=environment,
        archived=archived_at is not None,
    )


def new_row(**values: Any) -> dict[str, Any]:
    """Column values for a new row, with a fresh UUIDv7 id."""
    return {"id": new_id(), **values}
