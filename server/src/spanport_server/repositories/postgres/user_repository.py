"""Reads and writes users and first-time setup tokens."""

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from spanport_server.core.ids import UuidV7, new_id
from spanport_server.models import Invite, LoginFailure, Organization, SetupToken, User
from spanport_server.repositories.postgres.project_access import (
    member_projects,
    replace_member_projects,
    visible_projects,
)
from spanport_server.repositories.postgres.tenant_repository import insert_or_get_id, new_row
from spanport_server.schemas.auth import Role, UserRecord
from spanport_server.schemas.team import InviteDetails

INVITER = aliased(User)
USER_WITH_ORG = select(User, Organization.slug).join(Organization, Organization.id == User.org_id)


def to_record(user: User, org_slug: str, project_ids: Iterable[UuidV7] = ()) -> UserRecord:
    """The record services work with, with the projects the user may see; never carries the
    password hash.
    """
    return UserRecord(
        id=user.id,
        org_id=user.org_id,
        org_slug=org_slug,
        email=user.email,
        name=user.name,
        role=Role(user.role),
        project_ids=visible_projects(user.role, user.all_projects, project_ids),
    )


async def record_with_projects(session: AsyncSession, user: User, org_slug: str) -> UserRecord:
    """to_record, after loading the user's listed projects in `session`."""
    projects = await member_projects(session, [user.id])
    return to_record(user, org_slug, projects[user.id])


class UserRepository:
    """users and setup_tokens table access."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Create the repository.

        Args:
            sessionmaker: Opens Postgres sessions.
        """
        self._sessionmaker = sessionmaker

    async def count_users(self) -> int:
        """How many users exist (setup is open only while this is 0)."""
        async with self._sessionmaker() as session:
            return await session.scalar(select(func.count()).select_from(User)) or 0

    async def insert_setup_token(self, token_hash: str, expires_at: datetime) -> None:
        """Store a new setup token's hash."""
        async with self._sessionmaker.begin() as session:
            session.add(SetupToken(id=new_id(), token_hash=token_hash, expires_at=expires_at))

    async def create_owner(
        self,
        token_hash: str,
        now: datetime,
        org_slug: str,
        name: str,
        email: str,
        password_hash: str,
    ) -> UserRecord | None:
        """Use up a setup token and create the first user as the organization's owner.

        One transaction: the token is marked used only if the owner is created too. The
        organization is created, or joined if one with this slug already exists.

        Args:
            token_hash: Hash of the setup token the person pasted.
            now: The current time; the token must not have expired by then.
            org_slug: The organization's slug.
            name: The owner's name.
            email: The owner's email, lower case.
            password_hash: The Argon2 hash of the owner's password.

        Returns:
            The new owner, or None when the token is unknown, used or expired, or a user exists.
        """
        async with self._sessionmaker.begin() as session:
            used = await session.scalar(
                update(SetupToken)
                .where(
                    SetupToken.token_hash == token_hash,
                    SetupToken.used_at.is_(None),
                    SetupToken.expires_at > now,
                )
                .values(used_at=now)
                .returning(SetupToken.id)
            )
            users = await session.scalar(select(func.count()).select_from(User))
            if used is None or users:
                await session.rollback()
                return None
            org_id = await insert_or_get_id(
                session,
                insert(Organization).values(new_row(slug=org_slug)),
                select(Organization.id).where(Organization.slug == org_slug),
            )
            owner = User(
                id=new_id(),
                org_id=org_id,
                email=email,
                name=name,
                password_hash=password_hash,
                role=Role.OWNER.value,
            )
            session.add(owner)
        return to_record(owner, org_slug)

    async def find_for_login(self, email: str) -> tuple[UserRecord, str] | None:
        """An enabled user and their password hash, by lower-case email, or None."""
        async with self._sessionmaker() as session:
            row = (
                await session.execute(
                    USER_WITH_ORG.where(User.email == email, User.disabled_at.is_(None))
                )
            ).first()
            if row is None:
                return None
            user, org_slug = row
            return await record_with_projects(session, user, org_slug), user.password_hash

    async def find_by_id(self, user_id: UuidV7) -> UserRecord | None:
        """An enabled user by id, or None."""
        async with self._sessionmaker() as session:
            row = (
                await session.execute(
                    USER_WITH_ORG.where(User.id == user_id, User.disabled_at.is_(None))
                )
            ).first()
            return None if row is None else await record_with_projects(session, *row)

    async def find_open_invite(self, token_hash: str, now: datetime) -> InviteDetails | None:
        """What an invite that can still be accepted is for, or None."""
        async with self._sessionmaker() as session:
            row = (
                await session.execute(
                    select(Invite.email, Invite.role, Organization.slug, INVITER.name)
                    .join(Organization, Organization.id == Invite.org_id)
                    .outerjoin(INVITER, INVITER.id == Invite.invited_by)
                    .where(
                        Invite.token_hash == token_hash,
                        Invite.accepted_at.is_(None),
                        Invite.cancelled_at.is_(None),
                        Invite.expires_at > now,
                    )
                )
            ).first()
        if row is None:
            return None
        return InviteDetails(
            email=row[0], role=Role(row[1]), organization=row[2], invited_by=row[3]
        )

    async def accept_invite(
        self, token_hash: str, now: datetime, name: str, password_hash: str
    ) -> UserRecord | None:
        """Use up an invite and create its account, in one transaction.

        A user removed from the same organization gets their account back with the new role,
        name and password.

        Returns:
            The new (or restored) user, or None when the invite can't be accepted or the email
            already has an account (active, or in another organization).
        """
        async with self._sessionmaker.begin() as session:
            invite = (
                await session.execute(
                    update(Invite)
                    .where(
                        Invite.token_hash == token_hash,
                        Invite.accepted_at.is_(None),
                        Invite.cancelled_at.is_(None),
                        Invite.expires_at > now,
                    )
                    .values(accepted_at=now)
                    .returning(
                        Invite.org_id,
                        Invite.email,
                        Invite.role,
                        Invite.all_projects,
                        Invite.project_ids,
                    )
                )
            ).first()
            if invite is None:
                return None
            org_id, email, role, all_projects, project_ids = invite
            existing = await session.scalar(
                select(User).where(User.email == email).with_for_update()
            )
            if existing is None:
                user = User(
                    id=new_id(),
                    org_id=org_id,
                    email=email,
                    name=name,
                    password_hash=password_hash,
                    role=role,
                )
                session.add(user)
            elif existing.org_id == org_id and existing.disabled_at is not None:
                user = existing
                user.name, user.password_hash, user.role = name, password_hash, role
                user.disabled_at = None
            else:
                await session.rollback()
                return None
            user.all_projects = all_projects
            await session.flush()
            await replace_member_projects(
                session, org_id, user.id, [] if all_projects else project_ids
            )
            org_slug = await session.scalar(
                select(Organization.slug).where(Organization.id == org_id)
            )
            return await record_with_projects(session, user, org_slug or "")

    async def recent_login_failures(self, email_hash: str, since: datetime) -> list[datetime]:
        """When this email's wrong passwords happened after `since`, oldest first."""
        async with self._sessionmaker() as session:
            return list(
                await session.scalars(
                    select(LoginFailure.created_at)
                    .where(LoginFailure.email_hash == email_hash, LoginFailure.created_at > since)
                    .order_by(LoginFailure.created_at)
                )
            )

    async def record_login_failure(
        self, email_hash: str, now: datetime, forget_before: datetime
    ) -> None:
        """Store a wrong password, and drop every failure older than the window."""
        async with self._sessionmaker.begin() as session:
            await session.execute(
                delete(LoginFailure).where(LoginFailure.created_at < forget_before)
            )
            session.add(LoginFailure(id=new_id(), email_hash=email_hash, created_at=now))

    async def clear_login_failures(self, email_hash: str) -> None:
        """Forget this email's failures after a successful sign-in."""
        async with self._sessionmaker.begin() as session:
            await session.execute(delete(LoginFailure).where(LoginFailure.email_hash == email_hash))

    async def set_password(self, email: str, password_hash: str) -> UuidV7 | None:
        """Replace a user's password hash.

        Returns:
            The user's id, or None when no user has this email.
        """
        async with self._sessionmaker.begin() as session:
            return await session.scalar(
                update(User)
                .where(User.email == email)
                .values(password_hash=password_hash)
                .returning(User.id)
            )
