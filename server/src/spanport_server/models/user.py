"""People who sign in to the UI, their sessions and the first-time setup token."""

from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, UniqueConstraint, Uuid, func, true
from sqlalchemy.orm import Mapped, mapped_column

from spanport_server.core.ids import UuidV7
from spanport_server.models.base import Base


class User(Base):
    """A person in an organization, with a role. Emails are stored lower case."""

    __tablename__ = "users"

    org_id: Mapped[UuidV7] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    password_hash: Mapped[str]
    role: Mapped[str]
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # False limits a member or viewer to the projects in project_members.
    all_projects: Mapped[bool] = mapped_column(server_default=true())


class ProjectMember(Base):
    """A project a member or viewer limited to some projects may see."""

    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)

    org_id: Mapped[UuidV7] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[UuidV7] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UuidV7] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class UserSession(Base):
    """A signed-in browser. Only hashes of the session id and CSRF token are stored."""

    __tablename__ = "user_sessions"

    user_id: Mapped[UuidV7] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(unique=True)
    csrf_hash: Mapped[str]
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Invite(Base):
    """An invitation to join an organization with a role. The account is created only when the
    invited person accepts; until then nobody has access. Only the token's hash is stored.
    """

    __tablename__ = "invites"

    org_id: Mapped[UuidV7] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str]
    role: Mapped[str]
    token_hash: Mapped[str] = mapped_column(unique=True)
    invited_by: Mapped[UuidV7 | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The access the account gets on accepting: all projects, or only project_ids.
    all_projects: Mapped[bool] = mapped_column(server_default=true())
    project_ids: Mapped[list[UuidV7]] = mapped_column(ARRAY(Uuid), server_default="{}")


class LoginFailure(Base):
    """A wrong password for an email, kept for the sign-in rate limit's window only.

    The email is stored as its SHA-256, so the table doesn't collect addresses people typed.
    """

    __tablename__ = "login_failures"

    email_hash: Mapped[str] = mapped_column(index=True)


class SetupToken(Base):
    """A one-time link that creates the first user. Single use, short-lived, stored hashed."""

    __tablename__ = "setup_tokens"

    token_hash: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
