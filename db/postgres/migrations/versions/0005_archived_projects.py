"""Archived projects: their data keys stop working, their logs stay until they expire.

Revision ID: 0005
"""

import sqlalchemy
from alembic import op as schema_operations

# Alembic reads these four names; they must keep exactly these names.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add projects.archived_at; NULL means the project is in use."""
    schema_operations.add_column(
        "projects",
        sqlalchemy.Column("archived_at", sqlalchemy.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Drop the column; archived projects become active again and their keys work again."""
    schema_operations.drop_column("projects", "archived_at")
