"""Who the data belongs to: organization → client → project (one app in one environment)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from spanport_server.core.ids import UuidV7
from spanport_server.models.base import Base


class Organization(Base):
    """The company running Spanport."""

    __tablename__ = "organizations"

    slug: Mapped[str] = mapped_column(unique=True)


class Client(Base):
    """A customer the organization works for."""

    __tablename__ = "clients"
    __table_args__ = (UniqueConstraint("org_id", "slug"),)

    org_id: Mapped[UuidV7] = mapped_column(ForeignKey("organizations.id"))
    slug: Mapped[str]


class Project(Base):
    """One client app in one environment, e.g. hr-portal in production."""

    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("client_id", "slug", "environment"),)

    org_id: Mapped[UuidV7] = mapped_column(ForeignKey("organizations.id"), index=True)
    client_id: Mapped[UuidV7] = mapped_column(ForeignKey("clients.id"))
    slug: Mapped[str]
    environment: Mapped[str]
    # Set when archived: its data keys stop working; its logs stay until they expire.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
