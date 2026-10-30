"""API keys, stored only as a SHA-256 hash plus the last 4 characters."""

from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from spanport_server.core.ids import UuidV7
from spanport_server.models.base import Base


class ApiKey(Base):
    """A key that lets an app, script or person call Spanport.

    Data keys belong to one project. Admin keys belong to the organization, carry scopes and
    must expire; database checks enforce both.
    """

    __tablename__ = "api_keys"

    org_id: Mapped[UuidV7] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[UuidV7 | None] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str | None]
    key_type: Mapped[str]
    key_hash: Mapped[str] = mapped_column(unique=True)
    last_four: Mapped[str]
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
