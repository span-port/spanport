"""Alerts wait for a person: who an alert is assigned to, when its logs went back to normal,
and the note left when it was resolved.

Revision ID: 0010
"""

import sqlalchemy
from alembic import op as schema_operations

# Alembic reads these four names; they must keep exactly these names.
revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add alert_events.assigned_to (indexed; a removed user's alerts become unassigned),
    recovered_at and resolution_note. Existing alerts keep their state.
    """
    schema_operations.add_column(
        "alert_events",
        sqlalchemy.Column(
            "assigned_to",
            sqlalchemy.Uuid(),
            sqlalchemy.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    schema_operations.create_index(
        "ix_alert_events_assigned_to", "alert_events", ["assigned_to"]
    )
    schema_operations.add_column(
        "alert_events",
        sqlalchemy.Column("recovered_at", sqlalchemy.DateTime(timezone=True), nullable=True),
    )
    schema_operations.add_column(
        "alert_events", sqlalchemy.Column("resolution_note", sqlalchemy.Text(), nullable=True)
    )


def downgrade() -> None:
    """Drop the assignment, back-to-normal time and resolution notes."""
    schema_operations.drop_column("alert_events", "resolution_note")
    schema_operations.drop_column("alert_events", "recovered_at")
    schema_operations.drop_index("ix_alert_events_assigned_to", table_name="alert_events")
    schema_operations.drop_column("alert_events", "assigned_to")
