"""Which projects a member or viewer may see (project_members), shared by the user repositories.

Every function runs inside the caller's session, so it joins that transaction.
"""

from collections.abc import Iterable

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from spanport_server.core.constants import FULL_ACCESS_ROLES
from spanport_server.core.ids import UuidV7, new_id
from spanport_server.models import Project, ProjectMember


def visible_projects(
    role: str, all_projects: bool, project_ids: Iterable[UuidV7]
) -> frozenset[UuidV7] | None:
    """The projects a user may see; None means every project (owners, admins, "all projects")."""
    if role in FULL_ACCESS_ROLES or all_projects:
        return None
    return frozenset(project_ids)


async def member_projects(
    session: AsyncSession, user_ids: Iterable[UuidV7]
) -> dict[UuidV7, list[UuidV7]]:
    """Each user's listed projects (empty for users with none)."""
    wanted = list(user_ids)
    projects: dict[UuidV7, list[UuidV7]] = {user_id: [] for user_id in wanted}
    rows = await session.execute(
        select(ProjectMember.user_id, ProjectMember.project_id)
        .where(ProjectMember.user_id.in_(wanted))
        .order_by(ProjectMember.project_id)
    )
    for user_id, project_id in rows:
        projects[user_id].append(project_id)
    return projects


async def org_project_ids(
    session: AsyncSession, org_id: UuidV7, project_ids: Iterable[UuidV7]
) -> set[UuidV7]:
    """Those of `project_ids` that are projects of this org."""
    return set(
        await session.scalars(
            select(Project.id).where(Project.org_id == org_id, Project.id.in_(list(project_ids)))
        )
    )


async def replace_member_projects(
    session: AsyncSession, org_id: UuidV7, user_id: UuidV7, project_ids: Iterable[UuidV7]
) -> None:
    """Set the user's listed projects to `project_ids`, skipping any not in the org."""
    await session.execute(delete(ProjectMember).where(ProjectMember.user_id == user_id))
    kept = await org_project_ids(session, org_id, project_ids)
    if kept:
        await session.execute(
            insert(ProjectMember),
            [
                {"id": new_id(), "org_id": org_id, "project_id": project_id, "user_id": user_id}
                for project_id in kept
            ],
        )
