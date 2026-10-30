"""Log alert rules and the alerts they fire."""

from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from spanport_server.core.ids import UuidV7
from spanport_server.models.base import Base


class AlertRule(Base):
    """More than `threshold` matching log lines in the last `window_minutes` fires an alert,
    emailed to `email_recipients`.
    """

    __tablename__ = "alert_rules"

    org_id: Mapped[UuidV7] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[UuidV7] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str]
    query: Mapped[str]
    threshold: Mapped[int]
    window_minutes: Mapped[int]
    email_recipients: Mapped[list[str]] = mapped_column(ARRAY(String))
    enabled: Mapped[bool]
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlertEvent(Base):
    """One alert: firing, then acknowledged (someone is on it), then resolved.

    `created_at` is when it fired. A resolved alert with no `resolved_by` resolved itself.
    """

    __tablename__ = "alert_events"

    org_id: Mapped[UuidV7] = mapped_column(ForeignKey("organizations.id"), index=True)
    rule_id: Mapped[UuidV7] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="CASCADE"), index=True
    )
    state: Mapped[str]
    matched_count: Mapped[int]
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[UuidV7 | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[UuidV7 | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
