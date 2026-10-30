"""Reads and changes an organization's users and invites. Every query is scoped to one org."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from spanport_server.core.ids import UuidV7, new_id
from spanport_server.models import Invite, User
from spanport_server.repositories.postgres.project_access import (
    member_projects,
    org_project_ids,
    replace_member_projects,
    visible_projects,
)
from spanport_server.schemas.auth import Role
from spanport_server.schemas.team import (
    AccountOwner,
    InviteItem,
    ProjectAccess,
    TeamChange,
    UserItem,
)

INVITER = aliased(User)
INVITE_ITEM = select(
    Invite.id,
    Invite.email,
    Invite.role,
    INVITER.name,
    Invite.created_at,
    Invite.expires_at,
    Invite.all_projects,
    Invite.project_ids,
).outerjoin(INVITER, INVITER.id == Invite.invited_by)
USER_COLUMNS = select(User.id, User.name, User.email, User.role, User.created_at, User.all_projects)


def to_invite_item(row: Any) -> InviteItem:
    """A row of INVITE_ITEM as the API item."""
    invite_id, email, role, inviter, created_at, expires_at, all_projects, project_ids = row
    return InviteItem(
        id=invite_id,
        email=email,
        role=Role(role),
        invited_by=inviter,
        created_at=created_at,
        expires_at=expires_at,
        all_projects=all_projects,
        project_ids=list(project_ids),
    )


async def to_user_items(session: AsyncSession, rows: Sequence[Any]) -> list[UserItem]:
    """Rows of USER_COLUMNS as API items, with each user's projects."""
    projects = await member_projects(session, [row[0] for row in rows])
    items = []
    for user_id, name, email, role, created_at, all_projects in rows:
        visible = visible_projects(role, all_projects, projects[user_id])
        items.append(
            UserItem(
                id=user_id,
                name=name,
                email=email,
                role=Role(role),
                created_at=created_at,
                all_projects=visible is None,
                project_ids=sorted(visible or []),
            )
        )
    return items


def open_invites(org_id: UuidV7, now: datetime) -> Select[UuidV7]:
    """Invites of the org that can still be accepted."""
    return select(Invite.id).where(
        Invite.org_id == org_id,
        Invite.accepted_at.is_(None),
        Invite.cancelled_at.is_(None),
        Invite.expires_at > now,
    )


class TeamRepository:
    """users (as a team) and invites table access."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Create the repository.

        Args:
            sessionmaker: Opens Postgres sessions.
        """
        self._sessionmaker = sessionmaker

    async def list_users(
        self, org_id: UuidV7, after_id: UuidV7 | None, limit: int
    ) -> list[UserItem]:
        """One page of the org's active users, oldest first, with the projects they see."""
        query = (
            USER_COLUMNS.where(User.org_id == org_id, User.disabled_at.is_(None))
            .order_by(User.id)
            .limit(limit)
        )
        if after_id is not None:
            query = query.where(User.id > after_id)
        async with self._sessionmaker() as session:
            return await to_user_items(session, (await session.execute(query)).all())

    async def find_user(self, org_id: UuidV7, user_id: UuidV7) -> UserItem | None:
        """One active user of the org, or None."""
        query = USER_COLUMNS.where(
            User.org_id == org_id, User.id == user_id, User.disabled_at.is_(None)
        )
        async with self._sessionmaker() as session:
            items = await to_user_items(session, (await session.execute(query)).all())
        return items[0] if items else None

    async def set_project_access(
        self, org_id: UuidV7, user_id: UuidV7, all_projects: bool, project_ids: list[UuidV7]
    ) -> bool:
        """Give an active user all projects, or only `project_ids`. False when no such user."""
        async with self._sessionmaker.begin() as session:
            updated = await session.scalar(
                update(User)
                .where(User.org_id == org_id, User.id == user_id, User.disabled_at.is_(None))
                .values(all_projects=all_projects)
                .returning(User.id)
            )
            if updated is None:
                return False
            await replace_member_projects(
                session, org_id, user_id, [] if all_projects else project_ids
            )
        return True

    async def count_org_projects(self, org_id: UuidV7, project_ids: list[UuidV7]) -> int:
        """How many of `project_ids` are projects of this org."""
        async with self._sessionmaker() as session:
            return len(await org_project_ids(session, org_id, project_ids))

    async def change_role(self, org_id: UuidV7, user_id: UuidV7, role: Role) -> TeamChange:
        """Give an active user a new role, unless that leaves the org without an active owner.

        The org's owners are locked for the transaction, so two changes at once can't both
        remove the last owner.
        """
        async with self._sessionmaker.begin() as session:
            outcome = await self._check_owner_kept(session, org_id, user_id, role)
            if outcome is TeamChange.DONE:
                await session.execute(
                    update(User).where(User.org_id == org_id, User.id == user_id).values(role=role)
                )
            return outcome

    async def disable_user(self, org_id: UuidV7, user_id: UuidV7, now: datetime) -> TeamChange:
        """Remove an active user (they can't sign in), unless they are the org's last owner.

        The row stays, so alert history still shows who handled what.
        """
        async with self._sessionmaker.begin() as session:
            outcome = await self._check_owner_kept(session, org_id, user_id, None)
            if outcome is TeamChange.DONE:
                await session.execute(
                    update(User)
                    .where(User.org_id == org_id, User.id == user_id)
                    .values(disabled_at=now)
                )
            return outcome

    async def _check_owner_kept(
        self, session: AsyncSession, org_id: UuidV7, user_id: UuidV7, new_role: Role | None
    ) -> TeamChange:
        """Lock the org's active owners and say whether the change keeps at least one.

        Args:
            new_role: The user's new role, or None when the user is being removed.
        """
        owners = set(
            await session.scalars(
                select(User.id)
                .where(User.org_id == org_id, User.role == Role.OWNER, User.disabled_at.is_(None))
                .with_for_update()
            )
        )
        exists = await session.scalar(
            select(User.id).where(
                User.org_id == org_id, User.id == user_id, User.disabled_at.is_(None)
            )
        )
        if exists is None:
            return TeamChange.NOT_FOUND
        if owners == {user_id} and new_role is not Role.OWNER:
            return TeamChange.LAST_OWNER
        return TeamChange.DONE

    async def find_account(self, email: str) -> AccountOwner | None:
        """The org an email's account belongs to (accounts are unique by email), or None."""
        async with self._sessionmaker() as session:
            row = (
                await session.execute(
                    select(User.org_id, User.disabled_at).where(User.email == email)
                )
            ).first()
        return None if row is None else AccountOwner(org_id=row[0], disabled=row[1] is not None)

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
    ) -> InviteItem:
        """Store an invite with the access it grants, cancelling the org's earlier open invites
        for the same email.
        """
        invite_id = new_id()
        async with self._sessionmaker.begin() as session:
            await session.execute(
                update(Invite)
                .where(Invite.id.in_(open_invites(org_id, now)), Invite.email == email)
                .values(cancelled_at=now)
            )
            session.add(
                Invite(
                    id=invite_id,
                    org_id=org_id,
                    email=email,
                    role=role,
                    token_hash=token_hash,
                    invited_by=invited_by,
                    expires_at=expires_at,
                    all_projects=access.all_projects,
                    project_ids=access.project_ids,
                )
            )
        async with self._sessionmaker() as session:
            row = (await session.execute(INVITE_ITEM.where(Invite.id == invite_id))).one()
        return to_invite_item(row.tuple())

    async def list_open_invites(
        self, org_id: UuidV7, now: datetime, after_id: UuidV7 | None, limit: int
    ) -> list[InviteItem]:
        """One page of the org's invites that can still be accepted, oldest first."""
        query = (
            INVITE_ITEM.where(Invite.id.in_(open_invites(org_id, now)))
            .order_by(Invite.id)
            .limit(limit)
        )
        if after_id is not None:
            query = query.where(Invite.id > after_id)
        async with self._sessionmaker() as session:
            return [to_invite_item(row.tuple()) for row in await session.execute(query)]

    async def cancel_invite(self, org_id: UuidV7, invite_id: UuidV7, now: datetime) -> bool:
        """Cancel an open invite; its link stops working. False when there is none."""
        async with self._sessionmaker.begin() as session:
            cancelled = await session.scalar(
                update(Invite)
                .where(Invite.id == invite_id, Invite.id.in_(open_invites(org_id, now)))
                .values(cancelled_at=now)
                .returning(Invite.id)
            )
        return cancelled is not None
