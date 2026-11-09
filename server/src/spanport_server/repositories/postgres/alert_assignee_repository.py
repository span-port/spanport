"""Who a project's alerts can be assigned to: active owners, admins and members of the org who
can see the project. Every query is scoped to one organization.
"""

from sqlalchemy import Select, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spanport_server.core.constants import FULL_ACCESS_ROLES, RESPONDER_ROLES
from spanport_server.core.ids import UuidV7
from spanport_server.models import ProjectMember, User
from spanport_server.schemas.alert import AssigneeItem


def assignable_users(org_id: UuidV7, project_id: UuidV7) -> Select[UuidV7, str, str]:
    """SELECT of the people who may handle the project's alerts, by name."""
    sees_project = or_(
        User.role.in_(FULL_ACCESS_ROLES),
        User.all_projects.is_(True),
        exists().where(ProjectMember.project_id == project_id, ProjectMember.user_id == User.id),
    )
    return (
        select(User.id, User.name, User.email)
        .where(
            User.org_id == org_id,
            User.disabled_at.is_(None),
            User.role.in_(RESPONDER_ROLES),
            sees_project,
        )
        .order_by(User.name)
    )


class AlertAssigneeRepository:
    """users (with project_members) read for alert assignment."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Create the repository.

        Args:
            sessionmaker: Opens Postgres sessions.
        """
        self._sessionmaker = sessionmaker

    async def list_assignees(self, org_id: UuidV7, project_id: UuidV7) -> list[AssigneeItem]:
        """Everyone the project's alerts can be assigned to, by name."""
        async with self._sessionmaker() as session:
            rows = (await session.execute(assignable_users(org_id, project_id))).all()
        return [AssigneeItem(id=row[0], name=row[1], email=row[2]) for row in rows]

    async def find_assignee(
        self, org_id: UuidV7, project_id: UuidV7, user_id: UuidV7
    ) -> AssigneeItem | None:
        """This person, if the project's alerts can be assigned to them, else None."""
        query = assignable_users(org_id, project_id).where(User.id == user_id)
        async with self._sessionmaker() as session:
            row = (await session.execute(query)).first()
        return None if row is None else AssigneeItem(id=row[0], name=row[1], email=row[2])
