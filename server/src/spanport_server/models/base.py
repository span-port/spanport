"""Declarative base and columns shared by every table."""

from datetime import datetime

from sqlalchemy import DateTime, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from spanport_server.core.ids import UuidV7, new_id


class Base(DeclarativeBase):
    """Base class for all tables. Primary keys are UUIDv7; timestamps are UTC.

    The app sets ids with new_id(); Postgres 18's uuidv7() covers rows inserted any other way.
    """

    id: Mapped[UuidV7] = mapped_column(
        primary_key=True, default=new_id, server_default=text("uuidv7()")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
