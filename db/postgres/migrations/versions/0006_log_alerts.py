"""Log alerts: rules (what to watch and who to email) and the alerts they fire.

Revision ID: 0006
"""

from typing import Any

import sqlalchemy
from alembic import op as schema_operations
from sqlalchemy.dialects import postgresql

# Alembic reads these four names; they must keep exactly these names.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

UUIDV7_DEFAULT = sqlalchemy.text("uuidv7()")


def id_and_created_at() -> list[sqlalchemy.Column[Any]]:
    """Columns every table starts with: a UUIDv7 primary key and a UTC creation time."""
    return [
        sqlalchemy.Column("id", sqlalchemy.Uuid(), primary_key=True, server_default=UUIDV7_DEFAULT),
        sqlalchemy.Column(
            "created_at",
            sqlalchemy.DateTime(timezone=True),
            nullable=False,
            server_default=sqlalchemy.func.now(),
        ),
    ]


def foreign_key(name: str, target: str, on_delete: str | None = None) -> sqlalchemy.Column[Any]:
    """A UUID column pointing at `target`, e.g. "projects.id"."""
    return sqlalchemy.Column(
        name,
        sqlalchemy.Uuid(),
        sqlalchemy.ForeignKey(target, ondelete=on_delete),
        nullable=on_delete == "SET NULL",
    )


def optional_time(name: str) -> sqlalchemy.Column[Any]:
    """A nullable UTC timestamp column."""
    return sqlalchemy.Column(name, sqlalchemy.DateTime(timezone=True), nullable=True)


def upgrade() -> None:
    """Create alert_rules and alert_events. Each foreign key has an index.

    Deleting a project deletes its rules, and deleting a rule deletes its alerts. At most one
    alert per rule is open (not resolved) at a time.
    """
    schema_operations.create_table(
        "alert_rules",
        *id_and_created_at(),
        foreign_key("org_id", "organizations.id"),
        foreign_key("project_id", "projects.id", on_delete="CASCADE"),
        sqlalchemy.Column("name", sqlalchemy.String(), nullable=False),
        sqlalchemy.Column("query", sqlalchemy.String(), nullable=False),
        sqlalchemy.Column("threshold", sqlalchemy.Integer(), nullable=False),
        sqlalchemy.Column("window_minutes", sqlalchemy.Integer(), nullable=False),
        sqlalchemy.Column(
            "email_recipients", postgresql.ARRAY(sqlalchemy.String()), nullable=False
        ),
        sqlalchemy.Column("enabled", sqlalchemy.Boolean(), nullable=False),
        sqlalchemy.Column("next_check_at", sqlalchemy.DateTime(timezone=True), nullable=False),
        sqlalchemy.CheckConstraint("threshold >= 0", name="ck_alert_rules_threshold"),
        sqlalchemy.CheckConstraint(
            "window_minutes BETWEEN 1 AND 60", name="ck_alert_rules_window_minutes"
        ),
        sqlalchemy.CheckConstraint(
            "cardinality(email_recipients) BETWEEN 1 AND 10", name="ck_alert_rules_recipients"
        ),
    )
    schema_operations.create_index("ix_alert_rules_org_id", "alert_rules", ["org_id"])
    schema_operations.create_index("ix_alert_rules_project_id", "alert_rules", ["project_id"])
    # The check job looks for enabled rules that are due.
    schema_operations.create_index(
        "ix_alert_rules_due",
        "alert_rules",
        ["org_id", "next_check_at"],
        postgresql_where=sqlalchemy.text("enabled"),
    )
    schema_operations.create_table(
        "alert_events",
        *id_and_created_at(),
        foreign_key("org_id", "organizations.id"),
        foreign_key("rule_id", "alert_rules.id", on_delete="CASCADE"),
        sqlalchemy.Column("state", sqlalchemy.String(), nullable=False),
        sqlalchemy.Column("matched_count", sqlalchemy.Integer(), nullable=False),
        optional_time("acknowledged_at"),
        foreign_key("acknowledged_by", "users.id", on_delete="SET NULL"),
        optional_time("resolved_at"),
        foreign_key("resolved_by", "users.id", on_delete="SET NULL"),
        sqlalchemy.CheckConstraint(
            "state IN ('firing', 'acknowledged', 'resolved')", name="ck_alert_events_state"
        ),
    )
    schema_operations.create_index("ix_alert_events_org_id", "alert_events", ["org_id"])
    schema_operations.create_index("ix_alert_events_rule_id", "alert_events", ["rule_id"])
    schema_operations.create_index(
        "ix_alert_events_acknowledged_by", "alert_events", ["acknowledged_by"]
    )
    schema_operations.create_index("ix_alert_events_resolved_by", "alert_events", ["resolved_by"])
    schema_operations.create_index(
        "ux_alert_events_one_open_per_rule",
        "alert_events",
        ["rule_id"],
        unique=True,
        postgresql_where=sqlalchemy.text("state <> 'resolved'"),
    )


def downgrade() -> None:
    """Drop both tables; every alert rule and alert history is lost."""
    schema_operations.drop_table("alert_events")
    schema_operations.drop_table("alert_rules")
